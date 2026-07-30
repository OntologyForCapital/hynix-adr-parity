"""Korean HTS-style candlestick charts (상승 빨강 / 하락 파랑)."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Naver/HTS 한국 관례: 상승=빨강, 하락=파랑
UP_COLOR = "#F04452"  # red
DOWN_COLOR = "#3182F6"  # blue
UP_VOLUME = "rgba(240, 68, 82, 0.55)"
DOWN_VOLUME = "rgba(49, 130, 246, 0.55)"
MA_COLORS = {
    5: "#FFB300",
    20: "#8B5CF6",
    60: "#10B981",
    120: "#F97316",
}


def _time_labels(ohlcv: pd.DataFrame, interval: str) -> list:
    """Category labels so trading bars sit equally (no weekend gap)."""
    ts = ohlcv["ts_kst"] if "ts_kst" in ohlcv.columns else ohlcv.index
    if interval == "1d":
        return [t.strftime("%Y-%m-%d") for t in ts]
    return [t.strftime("%m-%d %H:%M") for t in ts]


def candle_figure(
    ohlcv: pd.DataFrame,
    title: str = "",
    y_title: str = "",
    interval: str = "30m",
    ma_windows: Sequence[int] = (5, 20, 60),
    show_volume: bool = True,
    price_decimals: int = 0,
) -> go.Figure:
    """
    HTS-like candle + volume + MA.

    Title is intentionally light/empty here — Streamlit renders the section
    title above the figure so MA legend never collides with page headings.
    """
    if ohlcv is None or ohlcv.empty:
        fig = go.Figure()
        fig.update_layout(
            title=title or "데이터 없음",
            height=360,
            margin=dict(l=16, r=48, t=40, b=40),
        )
        return fig

    df = ohlcv.copy()
    x = _time_labels(df, interval)
    n = len(df)

    rows = 2 if show_volume else 1
    row_heights = [0.76, 0.24] if show_volume else [1.0]
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10 if show_volume else 0.04,
        row_heights=row_heights,
    )

    fig.add_trace(
        go.Candlestick(
            x=x,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="캔들",
            increasing=dict(line=dict(color=UP_COLOR, width=1), fillcolor=UP_COLOR),
            decreasing=dict(line=dict(color=DOWN_COLOR, width=1), fillcolor=DOWN_COLOR),
            whiskerwidth=0.4,
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    for w in ma_windows:
        col = f"ma{w}"
        if col not in df.columns:
            df[col] = df["Close"].rolling(window=w, min_periods=1).mean()
        if df[col].notna().sum() == 0:
            continue
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col],
                mode="lines",
                name=f"MA{w}",
                line=dict(color=MA_COLORS.get(w, "#999"), width=1.4),
                hovertemplate=f"MA{w}: %{{y:,.{price_decimals}f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    if show_volume and "Volume" in df.columns:
        colors = [
            UP_VOLUME if c >= o else DOWN_VOLUME
            for c, o in zip(df["Close"].tolist(), df["Open"].tolist())
        ]
        fig.add_trace(
            go.Bar(
                x=x,
                y=df["Volume"],
                name="거래량",
                marker_color=colors,
                showlegend=False,
                hovertemplate="거래량: %{y:,.0f}<extra></extra>",
            ),
            row=2,
            col=1,
        )

    if n > 80:
        step = max(n // 12, 1)
    elif n > 40:
        step = max(n // 10, 1)
    else:
        step = max(n // 8, 1) if n else 1
    tickvals = x[::step] if x else []

    # MA 범례: 차트 바깥 하단 중앙 (제목·캔들과 완전 분리)
    fig.update_layout(
        height=560 if show_volume else 460,
        margin=dict(l=12, r=68, t=28, b=78),
        template="plotly_white",
        hovermode="x unified",
        showlegend=bool(ma_windows),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.14 if show_volume else -0.12,
            x=0.0,
            xanchor="left",
            bgcolor="rgba(255,255,255,0)",
            borderwidth=0,
            font=dict(size=12, color="#374151"),
            itemsizing="constant",
            itemwidth=40,
            traceorder="normal",
        ),
        xaxis_rangeslider_visible=False,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        dragmode="pan",
    )

    # 가격 패널: 우측 축 + 상단 살짝 여유 (라인 잘림 방지)
    fig.update_yaxes(
        title_text=y_title,
        title_standoff=12,
        row=1,
        col=1,
        side="right",
        showgrid=True,
        gridcolor="#EEF1F5",
        zeroline=False,
        tickformat=",." + ("0f" if price_decimals == 0 else f"{price_decimals}f"),
        automargin=True,
        fixedrange=False,
    )
    fig.update_xaxes(
        type="category",
        tickmode="array",
        tickvals=tickvals,
        showgrid=False,
        row=1,
        col=1,
        rangeslider_visible=False,
        showticklabels=not show_volume,
        automargin=True,
    )

    if show_volume:
        fig.update_yaxes(
            title_text="거래량",
            title_standoff=12,
            row=2,
            col=1,
            side="right",
            showgrid=True,
            gridcolor="#EEF1F5",
            zeroline=False,
            automargin=True,
        )
        fig.update_xaxes(
            type="category",
            tickmode="array",
            tickvals=tickvals,
            title_text="시간 (KST)" if interval != "1d" else "날짜",
            title_standoff=14,
            showgrid=False,
            row=2,
            col=1,
            automargin=True,
        )
    else:
        fig.update_xaxes(
            title_text="시간 (KST)" if interval != "1d" else "날짜",
            title_standoff=14,
            row=1,
            col=1,
            automargin=True,
        )

    return fig


def line_figure(
    times: Iterable,
    values: Iterable,
    title: str = "",
    y_title: str = "",
    color: str = "#54A24B",
    interval: str = "30m",
    hline: Optional[float] = None,
    hline_label: Optional[str] = None,
) -> go.Figure:
    """Simple line chart (parity ratio etc.). Title rendered by Streamlit."""
    t_list = list(times)
    v_list = list(values)
    n = len(v_list)

    if n and hasattr(t_list[0], "strftime"):
        if interval == "1d":
            x = [t.strftime("%Y-%m-%d") for t in t_list]
        else:
            x = [t.strftime("%m-%d %H:%M") for t in t_list]
    else:
        x = t_list

    mode = "lines" if n > 150 else "lines+markers"
    fig = go.Figure(
        data=[
            go.Scatter(
                x=x,
                y=v_list,
                mode=mode,
                name="비율",
                line=dict(color=color, width=2),
                marker=dict(size=4) if mode != "lines" else None,
                hovertemplate="%{x}<br>%{y:.4f}<extra></extra>",
                showlegend=False,
            )
        ]
    )
    if hline is not None:
        fig.add_hline(
            y=hline,
            line_dash="dash",
            line_color="#9CA3AF",
            annotation_text=hline_label or str(hline),
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color="#6B7280",
            annotation_yshift=8,
        )
    fig.update_layout(
        height=400,
        margin=dict(l=12, r=68, t=24, b=56),
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        xaxis=dict(
            type="category",
            showgrid=False,
            automargin=True,
            title_text="시간 (KST)" if interval != "1d" else "날짜",
            title_standoff=14,
        ),
        yaxis=dict(
            title=y_title,
            title_standoff=12,
            side="right",
            gridcolor="#EEF1F5",
            automargin=True,
        ),
    )
    return fig
