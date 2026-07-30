# SK하이닉스 본주 vs NASDAQ ADR 30분 패리티

코스피 **SK하이닉스(000660)** 와 나스닥 **ADR(SKHY)** 를 **30분 단위**로 불러와 세 그래프를 보여 줍니다.

1. 한국 시장 하이닉스 주가 (KRW)  
2. 미국 시장 하이닉스 ADR 주가 (USD)  
3. 환율 적용 패리티 비율  

\[
\text{ratio} = \frac{P_{\text{KR}}}{P_{\text{ADR}} \times 10 \times S_{\text{USD/KRW}}}
\]

- **10 ADR = 본주 1주** 교환 비율 반영  
- 비율 ≈ 1 → 공정 패리티, >1 → 본주 상대 고평가, <1 → ADR 패키지 상대 고평가  

메인 `kis_hourly_dashboard` 코드는 **수정하지 않는** 사이드 프로젝트입니다.

## 로컬 실행

```bash
cd ~/Desktop/Pilot_Projects/주식API_Grok/hynix_adr_parity
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

브라우저: http://localhost:8501

## GitHub + Streamlit Community Cloud 배포

### 1) 이 폴더를 독립 저장소로 올리기 (권장)

Streamlit Cloud는 **앱 파일이 있는 루트**를 저장소로 두는 편이 단순합니다.

```bash
cd ~/Desktop/Pilot_Projects/주식API_Grok/hynix_adr_parity

git init
git add app.py data.py config.py requirements.txt README.md .gitignore
git commit -m "Initial SK Hynix KR vs ADR 30m parity dashboard"

# GitHub에 빈 저장소 만든 뒤 (예: hynix-adr-parity)
gh repo create hynix-adr-parity --public --source=. --remote=origin --push
# 또는
# git remote add origin https://github.com/<USER>/hynix-adr-parity.git
# git branch -M main
# git push -u origin main
```

### 2) Streamlit Community Cloud 연결

1. https://share.streamlit.io 로그인 (GitHub 연동)  
2. **New app**  
3. Repository: `hynix-adr-parity` (또는 본인 저장소명)  
4. Branch: `main`  
5. Main file path: `app.py`  
6. Deploy  

API 키 없음 → **Secrets 설정 불필요** (Yahoo `yfinance` 공개 시세).

### 3) 모노레포에 둘 경우

상위 `주식API_Grok` 저장소를 쓰는 경우:

- Main file path: `hynix_adr_parity/app.py`  
- Python requirements: `hynix_adr_parity/requirements.txt`  
  (Cloud 고급 설정에서 requirements 경로 지정 가능)

## 파일 구조

```
hynix_adr_parity/
  app.py              # Streamlit UI + 3 charts
  data.py             # yfinance 30m fetch + parity
  config.py           # tickers, ADR ratio=10
  requirements.txt
  README.md
  .gitignore
```

## 데이터 소스 · 한계

| 항목 | 값 |
|------|-----|
| 본주 | `000660.KS` (Yahoo) |
| ADR | `SKHY` (Yahoo / NASDAQ) |
| 환율 | `USDKRW=X` |
| 봉 | 30분 (`interval=30m`) |

- Yahoo 30분봉 보관 기간은 대략 **최근 1–2개월** 수준입니다.  
- 한국·미국 장 시간이 달라 **비율 차트는 직전 유효가 forward-fill** 을 사용합니다.  
- 지연·결측·서스펜드 구간이 있을 수 있습니다. 투자 권유가 아닙니다.

## 메인 프로젝트와의 관계

| | |
|--|--|
| 경로 | `주식API_Grok/hynix_adr_parity/` |
| 기존 SQLite / KIS 수집기 | 사용 안 함 |
| 기존 Streamlit `app.py` | 수정 없음 |
