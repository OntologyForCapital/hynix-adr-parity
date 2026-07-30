"""Fetch and align OHLCV for KR Hynix, US ADR, and USD/KRW (30m / 1h / 1d)."""

from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

from config import (
    ADR_TICKER,
    ADR_TO_COMMON,
    FX_TICKER,
    KR_TICKER,
)

OHLCV_COLS = ("Open", "High", "Low", "Close", "Volume")


def _ensure_utc_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx, utc=True)
    elif idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    return idx


def _flatten_field(df: pd.DataFrame, field: str, ticker: str) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64", name=field)

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        level0 = out.columns.get_level_values(0)
        if field in level0:
            block = out[field]
            if isinstance(block, pd.DataFrame):
                if ticker in block.columns:
                    s = block[ticker]
                else:
                    s = block.iloc[:, 0]
            else:
                s = block
        else:
            return pd.Series(dtype="float64", name=field)
    else:
        if field not in out.columns:
            return pd.Series(dtype="float64", name=field)
        s = out[field]

    s = pd.to_numeric(s, errors="coerce")
    s.name = field
    s.index = _ensure_utc_index(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def fetch_ohlcv(ticker: str, period: str, interval: str = "30m") -> pd.DataFrame:
    """Download OHLCV for one ticker. Index is UTC; adds ts_kst for display."""
    raw = yf.download(
        ticker,
        period=period,
        interval=interval,
        progress=False,
        auto_adjust=True,
        threads=False,
    )
    if raw is None or raw.empty:
        return pd.DataFrame(columns=list(OHLCV_COLS) + ["ts_kst", "ts_et"])

    frames = {field: _flatten_field(raw, field, ticker) for field in OHLCV_COLS}
    ohlcv = pd.DataFrame(frames).dropna(subset=["Open", "High", "Low", "Close"], how="any")
    if ohlcv.empty:
        return pd.DataFrame(columns=list(OHLCV_COLS) + ["ts_kst", "ts_et"])

    ohlcv["Volume"] = ohlcv["Volume"].fillna(0)
    ohlcv["ts_kst"] = ohlcv.index.tz_convert("Asia/Seoul")
    ohlcv["ts_et"] = ohlcv.index.tz_convert("America/New_York")
    return ohlcv


def fetch_close_series(ticker: str, period: str, interval: str = "30m") -> pd.Series:
    """Close-only series (used for FX)."""
    ohlcv = fetch_ohlcv(ticker, period, interval)
    if ohlcv.empty:
        return pd.Series(dtype="float64", name=ticker)
    s = ohlcv["Close"].copy()
    s.name = ticker
    return s


def build_panel(period: str = "10d", interval: str = "30m") -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns (parity_panel, kr_ohlcv, adr_ohlcv).

    Parity ratio:
        ratio = KR_Close / (ADR_Close × ADR_TO_COMMON × USD_KRW)
    """
    kr = fetch_ohlcv(KR_TICKER, period, interval)
    adr = fetch_ohlcv(ADR_TICKER, period, interval)
    fx = fetch_close_series(FX_TICKER, period, interval)

    kr_close = kr["Close"] if not kr.empty else pd.Series(dtype="float64")
    adr_close = adr["Close"] if not adr.empty else pd.Series(dtype="float64")

    idx = kr_close.index.union(adr_close.index).union(fx.index).sort_values()
    if len(idx) == 0:
        empty = pd.DataFrame(
            columns=[
                "kr_close",
                "adr_close",
                "usdkrw",
                "adr_package_krw",
                "parity_ratio",
                "kr_in_usd",
                "adr_package_usd",
                "ts_kst",
                "ts_et",
            ]
        )
        return empty, kr, adr

    panel = pd.DataFrame(index=idx)
    panel["kr_close"] = kr_close.reindex(idx)
    panel["adr_close"] = adr_close.reindex(idx)
    panel["usdkrw"] = fx.reindex(idx)

    filled = panel.ffill()
    filled["adr_package_usd"] = filled["adr_close"] * ADR_TO_COMMON
    filled["adr_package_krw"] = filled["adr_package_usd"] * filled["usdkrw"]
    filled["kr_in_usd"] = filled["kr_close"] / filled["usdkrw"]
    filled["parity_ratio"] = filled["kr_close"] / filled["adr_package_krw"]

    filled["kr_observed"] = panel["kr_close"].notna()
    filled["adr_observed"] = panel["adr_close"].notna()
    filled["fx_observed"] = panel["usdkrw"].notna()

    filled["ts_utc"] = filled.index
    filled["ts_kst"] = filled.index.tz_convert("Asia/Seoul")
    filled["ts_et"] = filled.index.tz_convert("America/New_York")
    filled["interval"] = interval

    return filled, kr, adr


def latest_snapshot(panel: pd.DataFrame) -> Optional[dict]:
    """Most recent row with both KR and ADR (after ffill) available."""
    if panel is None or panel.empty:
        return None
    ok = panel.dropna(subset=["kr_close", "adr_close", "usdkrw", "parity_ratio"])
    if ok.empty:
        return None
    row = ok.iloc[-1]
    return {
        "ts_utc": row.name,
        "ts_kst": row["ts_kst"],
        "ts_et": row["ts_et"],
        "kr_close": float(row["kr_close"]),
        "adr_close": float(row["adr_close"]),
        "usdkrw": float(row["usdkrw"]),
        "adr_package_krw": float(row["adr_package_krw"]),
        "kr_in_usd": float(row["kr_in_usd"]),
        "parity_ratio": float(row["parity_ratio"]),
        "kr_observed": bool(row["kr_observed"]),
        "adr_observed": bool(row["adr_observed"]),
    }


def series_for_chart(panel: pd.DataFrame, col: str, observed_only: bool = False) -> pd.DataFrame:
    """Two-column frame: time (KST) + value (for ratio / FX lines)."""
    if panel is None or panel.empty or col not in panel.columns:
        return pd.DataFrame(columns=["time", "value"])

    df = panel.copy()
    if observed_only:
        flag = {
            "kr_close": "kr_observed",
            "adr_close": "adr_observed",
            "usdkrw": "fx_observed",
        }.get(col)
        if flag and flag in df.columns:
            df = df[df[flag]]

    out = pd.DataFrame(
        {
            "time": df["ts_kst"] if "ts_kst" in df.columns else df.index,
            "value": df[col],
        }
    ).dropna(subset=["value"])
    return out


def add_moving_averages(ohlcv: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    """Attach simple MAs on Close (same as typical HTS defaults)."""
    if ohlcv is None or ohlcv.empty:
        return ohlcv
    out = ohlcv.copy()
    for w in windows:
        out[f"ma{w}"] = out["Close"].rolling(window=w, min_periods=1).mean()
    return out
