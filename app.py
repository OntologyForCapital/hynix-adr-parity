"""
SK Hynix KOSPI vs NASDAQ ADR parity dashboard.

Korean HTS-style candlesticks (상승 빨강 / 하락 파랑) for price charts.
Parity ratio remains a line chart.
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from charts import candle_figure, line_figure
from config import (
    ADR_NAME,
    ADR_TO_COMMON,
    ADR_TICKER,
    CACHE_TTL_SECONDS,
    DEFAULT_INTERVAL_LABEL,
    DEFAULT_PERIOD_BY_INTERVAL,
    FX_NAME,
    FX_TICKER,
    INTERVAL_META,
    INTERVAL_OPTIONS,
    KR_NAME,
    KR_TICKER,
    PERIOD_OPTIONS_BY_INTERVAL,
    RATIO_NAME,
)
from data import add_moving_averages, build_panel, latest_snapshot, series_for_chart


st.set_page_config(
    page_title="하이닉스 본주 vs ADR 패리티",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="시세 불러오는 중…")
def load_all(period: str, interval: str):
    return build_panel(period=period, interval=interval)


def main() -> None:
    with st.sidebar:
        st.header("설정")
        interval_label = st.selectbox(
            "봉 간격",
            options=list(INTERVAL_OPTIONS.keys()),
            index=list(INTERVAL_OPTIONS.keys()).index(DEFAULT_INTERVAL_LABEL),
            help="30분봉 / 1시간봉 / 일봉. Yahoo 보관 기간이 봉마다 다릅니다.",
        )
        interval = INTERVAL_OPTIONS[interval_label]
        meta = INTERVAL_META[interval]

        period_map = PERIOD_OPTIONS_BY_INTERVAL[interval]
        default_period_label = DEFAULT_PERIOD_BY_INTERVAL.get(interval, list(period_map.keys())[0])
        default_idx = (
            list(period_map.keys()).index(default_period_label)
            if default_period_label in period_map
            else 0
        )
        period_label = st.selectbox(
            "조회 기간",
            options=list(period_map.keys()),
            index=default_idx,
        )
        period = period_map[period_label]

        st.markdown("**이동평균**")
        ma_choices = st.multiselect(
            "표시할 MA",
            options=[5, 20, 60, 120],
            default=[5, 20, 60],
            help="네이버·HTS 기본에 가까운 단순이동평균(종가 기준)",
        )
        show_volume = st.checkbox("거래량 표시", value=True)

        if st.button("데이터 새로고침", use_container_width=True):
            load_all.clear()
            st.rerun()

        st.markdown("---")
        st.markdown(
            f"""
**비율 정의**

`ratio = P_KR / (P_ADR × {ADR_TO_COMMON} × USD/KRW)`

- ≈ **1.0** : 본주와 ADR 패키지 공정 패리티  
- **> 1** : 본주가 ADR 대비 상대적으로 비쌈  
- **< 1** : ADR 패키지가 본주 대비 상대적으로 비쌈  

**캔들 색** (한국 관례)  
- 상승: 빨강 · 하락: 파랑  

데이터: Yahoo Finance (`yfinance`).  
{meta["history_note"]}
"""
        )

    st.title(f"SK하이닉스 본주 · ADR 패리티 ({meta['title_suffix']})")
    st.caption(
        f"KOSPI `{KR_TICKER}` · NASDAQ ADR `{ADR_TICKER}` · 환율 `{FX_TICKER}` · "
        f"교환비율 **{ADR_TO_COMMON} ADR = 1 본주** · "
        f"봉 **{interval_label}** · 기간 **{period_label}** · "
        f"차트 **캔들(HTS 스타일)**"
    )

    try:
        panel, kr_ohlcv, adr_ohlcv = load_all(period, interval)
    except Exception as exc:  # noqa: BLE001
        st.error(f"데이터 로드 실패: {exc}")
        st.stop()

    if (panel is None or panel.empty) and (kr_ohlcv is None or kr_ohlcv.empty):
        st.warning("조회된 데이터가 없습니다. 봉/기간을 바꿔 보거나 잠시 후 다시 시도하세요.")
        st.stop()

    snap = latest_snapshot(panel) if panel is not None else None
    ma_windows = tuple(sorted(ma_choices)) if ma_choices else ()

    c1, c2, c3, c4 = st.columns(4)
    if snap:
        c1.metric(KR_NAME, f"{snap['kr_close']:,.0f} 원")
        c2.metric(ADR_NAME, f"${snap['adr_close']:,.2f}")
        c3.metric(FX_NAME, f"{snap['usdkrw']:,.2f}")
        c4.metric(
            "패리티 비율",
            f"{snap['parity_ratio']:.4f}",
            help="1.0 = 본주와 ADR×10이 환율 환산 시 동일",
        )
        st.caption(
            f"기준 시각 KST `{snap['ts_kst']}` · ET `{snap['ts_et']}` · "
            f"ADR×10 원화 환산 `{snap['adr_package_krw']:,.0f}` 원 · "
            f"본주 달러 환산 `${snap['kr_in_usd']:,.2f}`"
        )
    else:
        st.info("최신 스냅샷을 만들 수 없습니다. (ADR·본주·환율 중 일부 결측)")

    chart_cfg = {
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
    }

    # ---- Chart 1: KR candles ----
    # 제목은 Streamlit 쪽에 두어 Plotly MA 범례와 겹치지 않게 함
    st.markdown(f"### ① {KR_NAME} · {meta['title_suffix']}")
    if kr_ohlcv is None or kr_ohlcv.empty:
        st.warning("한국 시장 가격 데이터가 없습니다.")
    else:
        kr_plot = add_moving_averages(kr_ohlcv, windows=ma_windows or (5, 20, 60))
        st.plotly_chart(
            candle_figure(
                kr_plot,
                y_title="원 (KRW)",
                interval=interval,
                ma_windows=ma_windows or (5, 20, 60),
                show_volume=show_volume,
                price_decimals=0,
            ),
            use_container_width=True,
            config=chart_cfg,
        )

    st.markdown("")  # 차트 간 여백
    # ---- Chart 2: ADR candles ----
    st.markdown(f"### ② {ADR_NAME} · {meta['title_suffix']}")
    if adr_ohlcv is None or adr_ohlcv.empty:
        st.warning("미국 ADR 가격 데이터가 없습니다. (SKHY 상장 직후면 기간을 짧게 잡아 보세요.)")
    else:
        adr_plot = add_moving_averages(adr_ohlcv, windows=ma_windows or (5, 20, 60))
        st.plotly_chart(
            candle_figure(
                adr_plot,
                y_title="달러 (USD)",
                interval=interval,
                ma_windows=ma_windows or (5, 20, 60),
                show_volume=show_volume,
                price_decimals=2,
            ),
            use_container_width=True,
            config=chart_cfg,
        )

    st.markdown("")
    # ---- Chart 3: parity ratio (line) ----
    st.markdown(f"### ③ {RATIO_NAME} · {meta['title_suffix']}")
    if panel is None or panel.empty:
        st.warning("패리티 비율을 계산할 수 없습니다.")
    else:
        ratio_df = series_for_chart(panel, "parity_ratio", observed_only=False)
        if ratio_df.empty:
            st.warning("패리티 비율을 계산할 수 없습니다.")
        else:
            st.plotly_chart(
                line_figure(
                    ratio_df["time"],
                    ratio_df["value"],
                    y_title="비율 (1.0 = 패리티)",
                    color="#54A24B",
                    interval=interval,
                    hline=1.0,
                    hline_label="패리티 1.0",
                ),
                use_container_width=True,
            )

    with st.expander("보조: 환율 · 본주 달러환산 · ADR×10 원화환산"):
        if panel is None or panel.empty:
            st.write("데이터 없음")
        else:
            fx_df = series_for_chart(panel, "usdkrw", observed_only=True)
            fig = make_subplots(
                rows=3,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.06,
                subplot_titles=(
                    FX_NAME,
                    "본주 달러 환산 (KR / 환율)",
                    "ADR×10 원화 환산 (ADR×10×환율)",
                ),
            )
            if not fx_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=fx_df["time"],
                        y=fx_df["value"],
                        name="USD/KRW",
                        mode="lines",
                        line=dict(color="#F58518"),
                    ),
                    row=1,
                    col=1,
                )
            usd_df = series_for_chart(panel, "kr_in_usd", observed_only=False)
            if not usd_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=usd_df["time"],
                        y=usd_df["value"],
                        name="KR in USD",
                        mode="lines",
                        line=dict(color="#F04452"),
                    ),
                    row=2,
                    col=1,
                )
            pkg_df = series_for_chart(panel, "adr_package_krw", observed_only=False)
            if not pkg_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=pkg_df["time"],
                        y=pkg_df["value"],
                        name="ADR×10 KRW",
                        mode="lines",
                        line=dict(color="#3182F6"),
                    ),
                    row=3,
                    col=1,
                )
            fig.update_layout(height=720, template="plotly_white", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("원본 테이블 (최근 200행 · 패리티 패널)"):
        if panel is None or panel.empty:
            st.write("데이터 없음")
        else:
            show_cols = [
                "ts_kst",
                "kr_close",
                "adr_close",
                "usdkrw",
                "adr_package_krw",
                "kr_in_usd",
                "parity_ratio",
                "kr_observed",
                "adr_observed",
            ]
            table = panel[show_cols].dropna(how="all").tail(200).copy()
            table = table.reset_index(drop=True)
            st.dataframe(table, use_container_width=True)

    st.markdown("---")
    st.caption(
        "캔들: 한국식 색상(상승 빨강·하락 파랑) · 휴장 구간 제거(카테고리 축) · MA는 종가 단순이동평균. "
        "패리티 비율은 직전 유효 호가(forward-fill). 투자 권유가 아닙니다. "
        f"{meta['history_note']}"
    )


if __name__ == "__main__":
    main()
