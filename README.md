# 📅 증시 캘린더 데이터 수집기 (Stock Market Calendar Collector)

투자자에게 필수적인 국내외 증시 일정과 경제 지표 데이터를 자동으로 수집하고 통합 관리하는 Python 기반 도구입니다.

---

## 🎯 프로젝트 목적
이 프로젝트는 여러 곳에 흩어져 있는 증시 관련 일정(실적 발표, 공모주 청약, 경제 지표, 휴장일 등)을 하나의 도구로 수집하여, 투자 결정을 돕는 통합 데이터를 제공하는 것을 목적으로 합니다. 수집된 데이터는 JSON이나 Excel 형태로 저장하거나 REST API를 통해 다른 서비스와 연동할 수 있습니다.

## 🛠 기술 스택
- **Language:** Python 3.8+
- **Data Scraping:** `requests`, `BeautifulSoup4`, `lxml`
- **Data Processing:** `pandas`, `openpyxl` (Excel 지원)
- **Market Data:** `pykrx`, `pandas-market-calendars`
- **Web API:** `Flask` (REST API 서버 구축)

## ✨ 핵심 기능
1. **국내외 기업 실적 발표 수집**
   - 🇰🇷 **국내:** DART(전자공시시스템) OpenAPI 기반 공식 데이터 및 금융 포털 데이터 수집
   - 🇺🇸 **미국:** Nasdaq, Earnings Whispers 등 주요 소스를 통한 실적 일정 수집
2. **공모주(IPO) 청약 일정**
   - KRX KIND 시스템을 통해 국내 신규 상장 기업의 청약 시작/종료일 및 공모가 정보 수집
3. **글로벌 및 국내 경제 지표**
   - 한국은행(BOK) ECOS 및 Investing.com을 통해 금리, CPI, GDP 등 주요 지표 발표 일정 수집
4. **국내 증시 휴장일 관리**
   - KRX 데이터를 기반으로 한국 증시의 공휴일 및 휴장 정보 확인
5. **상세 재무제표 요약 (jaemujepyo.py)**
   - 특정 종목코드(예: 삼성전자 005930)와 연도를 입력하여 매출액, 영업이익, 당기순이익 등 주요 재무 지표를 억 원 단위로 요약 추출
6. **다양한 출력 포맷 및 인터페이스**
   - 수집 데이터를 `JSON`, `Excel` 파일로 자동 저장
   - Flask를 이용한 REST API 서버 모드 제공 (실시간 데이터 조회 가능)

## 🚀 설치 및 실행 방법

### 1. 환경 설치
필요한 라이브러리를 설치합니다.
```bash
pip install requests beautifulsoup4 pandas lxml openpyxl flask flask-limiter pykrx pandas-market-calendars OpenDartReader
```

### 2. 기본 실행 (데이터 수집 및 파일 저장)
스크립트를 실행하면 기본적으로 오늘부터 7일간의 일정을 수집하여 JSON/Excel로 저장합니다.
```bash
# 기본 수집 (오늘 ~ 7일 후, JSON 출력)
python market_calendar.py

# 날짜 범위를 지정하여 수집
python market_calendar.py --start 20260301 --end 20260331

# Excel 포맷으로 저장
python market_calendar.py --out excel

# DART API 키를 사용하여 공식 데이터 수집 (권장)
python market_calendar.py --dart YOUR_DART_API_KEY
```

### 3. REST API 서버 모드 실행
데이터를 실시간으로 제공하는 API 서버를 구동할 수 있습니다.
```bash
# 5000번 포트로 서버 실행
python market_calendar.py --mode server --port 5000
```
- **전체 일정 조회:** `GET http://localhost:5000/calendar`
- **국내 실적 조회:** `GET http://localhost:5000/calendar/earnings/kr`
- **공모주 일정 조회:** `GET http://localhost:5000/calendar/ipo`

## 🔑 API 키 발급 안내 (선택 사항)
더 정확하고 풍부한 데이터 수집을 위해 아래 API 키 발급을 권장합니다.
- **DART OpenAPI (국내 실적):** [opendart.fss.or.kr](https://opendart.fss.or.kr/)
- **한국은행 ECOS (경제 지표):** [ecos.bok.or.kr](https://ecos.bok.or.kr/)

---
*본 도구에서 수집된 데이터는 참고용이며, 실제 투자 시에는 공식 공시 자료를 다시 한번 확인하시기 바랍니다.*
