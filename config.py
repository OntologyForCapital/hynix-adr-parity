"""Ticker and display defaults for SK Hynix KR vs NASDAQ ADR parity."""

# Yahoo Finance symbols
KR_TICKER = "000660.KS"  # SK hynix common share (KOSPI)
ADR_TICKER = "SKHY"  # SK hynix ADR (NASDAQ), 10 ADR = 1 common
FX_TICKER = "USDKRW=X"  # USD/KRW

# 10 ADR exchange into 1 common share
ADR_TO_COMMON = 10

# Bar interval options (label -> Yahoo interval code)
# Yahoo limits: 30m/1h ~ recent months; 1d multi-year.
INTERVAL_OPTIONS = {
    "30분봉": "30m",
    "1시간봉": "1h",
    "일봉": "1d",
}
DEFAULT_INTERVAL_LABEL = "30분봉"

# Lookback options per interval (Yahoo history constraints)
PERIOD_OPTIONS_BY_INTERVAL = {
    "30m": {
        "5일": "5d",
        "10일": "10d",
        "1개월": "1mo",
        "2개월": "2mo",
    },
    "1h": {
        "5일": "5d",
        "10일": "10d",
        "1개월": "1mo",
        "3개월": "3mo",
        "6개월": "6mo",
    },
    "1d": {
        "1개월": "1mo",
        "3개월": "3mo",
        "6개월": "6mo",
        "1년": "1y",
        "2년": "2y",
        "5년": "5y",
        "최대": "max",
    },
}

# Fallback if interval missing
DEFAULT_PERIOD_BY_INTERVAL = {
    "30m": "10일",
    "1h": "1개월",
    "1d": "1년",
}

# Cache TTL for Streamlit (seconds)
CACHE_TTL_SECONDS = 300

# Display names
KR_NAME = "SK하이닉스 (KOSPI · 000660)"
ADR_NAME = "SK하이닉스 ADR (NASDAQ · SKHY)"
FX_NAME = "원/달러 (USDKRW)"
RATIO_NAME = "패리티 비율: KR / (ADR × 10 × 환율)"

# Chart style hints by interval
INTERVAL_META = {
    "30m": {
        "title_suffix": "30분봉",
        "xaxis_title": "시간 (KST)",
        "marker_size": 4,
        "line_mode": "lines+markers",
        "history_note": "30분봉 히스토리는 대략 최근 1–2개월입니다.",
    },
    "1h": {
        "title_suffix": "1시간봉",
        "xaxis_title": "시간 (KST)",
        "marker_size": 3,
        "line_mode": "lines+markers",
        "history_note": "1시간봉은 수개월 조회가 가능합니다(소스 제한 있음).",
    },
    "1d": {
        "title_suffix": "일봉",
        "xaxis_title": "날짜 (KST)",
        "marker_size": 5,
        "line_mode": "lines+markers",
        "history_note": "일봉은 수년치 조회가 가능합니다. ADR(SKHY)은 상장 이후만 있습니다.",
    },
}
