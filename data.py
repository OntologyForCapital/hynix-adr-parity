"""Fetch and align OHLCV for KR Hynix, US ADR, and USD/KRW (30m / 1h / 1d).

KR (000660): Naver Finance first (Cloud에서 Yahoo 429/빈응답이 잦음), Yahoo 폴백.
ADR / FX: Yahoo Finance (+ 재시도).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf

from config import (
    ADR_TICKER,
    ADR_TO_COMMON,
    FX_TICKER,
    KR_TICKER,
)

OHLCV_COLS = ("Open", "High", "Low", "Close", "Volume")
KR_CODE = "000660"  # KOSPI bare code for Naver

NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/item/main.naver?code=000660",
    "Accept": "application/json,text/plain,*/*",
}

# Yahoo-style period string -> approximate calendar days
PERIOD_DAYS = {
    "5d": 5,
    "10d": 10,
    "1mo": 31,
    "2mo": 62,
    "3mo": 93,
    "6mo": 186,
    "1y": 370,
    "2y": 740,
    "5y": 1850,
    "max": 3650,
}


def _empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(columns=list(OHLCV_COLS) + ["ts_kst", "ts_et", "source"])


def _ensure_utc_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx, utc=True)
    elif idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    return idx


def _attach_local_times(ohlcv: pd.DataFrame) -> pd.DataFrame:
    if ohlcv is None or ohlcv.empty:
        return _empty_ohlcv()
    out = ohlcv.copy()
    out.index = _ensure_utc_index(out.index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out["ts_kst"] = out.index.tz_convert("Asia/Seoul")
    out["ts_et"] = out.index.tz_convert("America/New_York")
    return out


def _period_start_end(period: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    days = PERIOD_DAYS.get(period, 31)
    end = pd.Timestamp.now(tz="Asia/Seoul")
    start = end - pd.Timedelta(days=days)
    return start, end


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


def _yahoo_download(ticker: str, period: str, interval: str, retries: int = 3) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            raw = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            if raw is not None and not raw.empty:
                frames = {field: _flatten_field(raw, field, ticker) for field in OHLCV_COLS}
                ohlcv = pd.DataFrame(frames).dropna(
                    subset=["Open", "High", "Low", "Close"], how="any"
                )
                if not ohlcv.empty:
                    ohlcv["Volume"] = ohlcv["Volume"].fillna(0)
                    ohlcv["source"] = "yahoo"
                    return _attach_local_times(ohlcv)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.6 * (attempt + 1))
    if last_err:
        # swallow; caller may fallback
        pass
    return _empty_ohlcv()


def _naver_get_json(url: str, retries: int = 3):
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=NAVER_HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            last_err = RuntimeError(f"HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"Naver request failed: {last_err}")


def fetch_kr_naver_daily(period: str) -> pd.DataFrame:
    start, end = _period_start_end(period)
    url = (
        f"https://api.stock.naver.com/chart/domestic/item/{KR_CODE}/day"
        f"?startDateTime={start.strftime('%Y%m%d')}0000"
        f"&endDateTime={end.strftime('%Y%m%d')}2359"
    )
    rows = _naver_get_json(url)
    if not rows:
        return _empty_ohlcv()

    records = []
    for row in rows:
        day = row.get("localDate")
        if not day:
            continue
        ts = pd.Timestamp(datetime.strptime(str(day), "%Y%m%d")).tz_localize("Asia/Seoul")
        records.append(
            {
                "ts": ts,
                "Open": float(row["openPrice"]),
                "High": float(row["highPrice"]),
                "Low": float(row["lowPrice"]),
                "Close": float(row["closePrice"]),
                "Volume": float(row.get("accumulatedTradingVolume") or 0),
            }
        )
    if not records:
        return _empty_ohlcv()

    df = pd.DataFrame(records).set_index("ts").sort_index()
    df.index = df.index.tz_convert("UTC")
    df["source"] = "naver"
    return _attach_local_times(df[list(OHLCV_COLS) + ["source"]])


def fetch_kr_naver_intraday(period: str, interval: str) -> pd.DataFrame:
    """Fetch 1-minute bars from Naver, resample to 30m or 1h."""
    start, end = _period_start_end(period)
    # Naver minute window: request whole range; may truncate if too long
    url = (
        f"https://api.stock.naver.com/chart/domestic/item/{KR_CODE}/minute"
        f"?startDateTime={start.strftime('%Y%m%d')}0900"
        f"&endDateTime={end.strftime('%Y%m%d')}1530"
    )
    try:
        rows = _naver_get_json(url)
    except Exception:
        # fallback: last 10 calendar days only
        start2 = end - timedelta(days=10)
        url = (
            f"https://api.stock.naver.com/chart/domestic/item/{KR_CODE}/minute"
            f"?startDateTime={start2.strftime('%Y%m%d')}0900"
            f"&endDateTime={end.strftime('%Y%m%d')}1530"
        )
        rows = _naver_get_json(url)

    if not rows:
        return _empty_ohlcv()

    records = []
    for row in rows:
        raw_ts = row.get("localDateTime")
        if not raw_ts:
            continue
        ts = pd.Timestamp(datetime.strptime(str(raw_ts), "%Y%m%d%H%M%S")).tz_localize(
            "Asia/Seoul"
        )
        # Naver minute: open/high/low of minute; currentPrice = close
        o = float(row.get("openPrice") or row.get("currentPrice"))
        h = float(row.get("highPrice") or o)
        low = float(row.get("lowPrice") or o)
        c = float(row.get("currentPrice") or o)
        vol = float(row.get("accumulatedTradingVolume") or 0)
        records.append({"ts": ts, "Open": o, "High": h, "Low": low, "Close": c, "Volume": vol})

    if not records:
        return _empty_ohlcv()

    m1 = pd.DataFrame(records).set_index("ts").sort_index()
    m1 = m1[~m1.index.duplicated(keep="last")]

    rule = {"30m": "30min", "1h": "1h"}.get(interval)
    if rule is None:
        return _empty_ohlcv()

    # label='left' matches typical bar start; closed='left' standard
    ohlcv = m1.resample(rule, label="left", closed="left").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    ).dropna(subset=["Open", "High", "Low", "Close"], how="any")

    if ohlcv.empty:
        return _empty_ohlcv()

    ohlcv.index = ohlcv.index.tz_convert("UTC")
    ohlcv["source"] = "naver"
    return _attach_local_times(ohlcv)


def fetch_kr_ohlcv(period: str, interval: str) -> pd.DataFrame:
    """KR primary = Naver, fallback = Yahoo."""
    kr = _empty_ohlcv()
    try:
        if interval == "1d":
            kr = fetch_kr_naver_daily(period)
        elif interval in ("30m", "1h"):
            kr = fetch_kr_naver_intraday(period, interval)
    except Exception:
        kr = _empty_ohlcv()

    if kr is not None and not kr.empty:
        return kr

    # Yahoo fallback (local Mac 등에서는 종종 성공)
    y = _yahoo_download(KR_TICKER, period, interval)
    if not y.empty:
        y["source"] = "yahoo"
    return y


def fetch_ohlcv(ticker: str, period: str, interval: str = "30m") -> pd.DataFrame:
    """Generic OHLCV. KR code/ticker routes to Naver-first path."""
    if ticker in (KR_TICKER, KR_CODE, f"{KR_CODE}.KS"):
        return fetch_kr_ohlcv(period, interval)
    return _yahoo_download(ticker, period, interval)


def fetch_close_series(ticker: str, period: str, interval: str = "30m") -> pd.Series:
    ohlcv = fetch_ohlcv(ticker, period, interval)
    if ohlcv.empty:
        return pd.Series(dtype="float64", name=ticker)
    s = ohlcv["Close"].copy()
    s.name = ticker
    return s


def build_panel(
    period: str = "10d", interval: str = "30m"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    """
    Returns (parity_panel, kr_ohlcv, adr_ohlcv, sources).

    Parity ratio:
        ratio = KR_Close / (ADR_Close × ADR_TO_COMMON × USD_KRW)
    """
    kr = fetch_kr_ohlcv(period, interval)
    adr = _yahoo_download(ADR_TICKER, period, interval)
    fx_ohlcv = _yahoo_download(FX_TICKER, period, interval)
    fx = fx_ohlcv["Close"] if not fx_ohlcv.empty else pd.Series(dtype="float64")

    sources = {
        "kr": (kr["source"].iloc[-1] if (not kr.empty and "source" in kr.columns) else "none"),
        "adr": (adr["source"].iloc[-1] if (not adr.empty and "source" in adr.columns) else "none"),
        "fx": (fx_ohlcv["source"].iloc[-1] if (not fx_ohlcv.empty and "source" in fx_ohlcv.columns) else "none"),
        "kr_bars": str(len(kr)),
        "adr_bars": str(len(adr)),
    }

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
        return empty, kr, adr, sources

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

    return filled, kr, adr, sources


def latest_snapshot(panel: pd.DataFrame) -> Optional[dict]:
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
    if ohlcv is None or ohlcv.empty:
        return ohlcv
    out = ohlcv.copy()
    for w in windows:
        out[f"ma{w}"] = out["Close"].rolling(window=w, min_periods=1).mean()
    return out
