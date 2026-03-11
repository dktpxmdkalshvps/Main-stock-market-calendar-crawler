"""
증시 캘린더 데이터 수집기 (Stock Market Calendar Crawler)
==========================================================
수집 항목:
  1. 국내 기업 실적 발표 (DART 공시 기반)
  2. 공모주 청약 일정 (KRX KIND)
  3. 국내 경제 지표 발표 (한국은행 등)
  4. 미국 기업 실적 발표 (Earnings Whispers / Yahoo Finance)
  5. 글로벌 경제 지표 (Investing.com)
  6. 주요 증시 휴장일 (KRX)

설치 필요 패키지:
  pip install requests beautifulsoup4 pandas openpyxl pykrx pandas-market-calendars
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import json
import time
import re
from typing import Optional
import warnings
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────
# 공통 유틸리티
# ─────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://finance.naver.com/",
}


def get_date_range(start: str = None, end: str = None):
    """날짜 범위 반환 (기본: 오늘 ~ 7일 후)"""
    if not start:
        start = datetime.today().strftime("%Y%m%d")
    if not end:
        end = (datetime.today() + timedelta(days=7)).strftime("%Y%m%d")
    return start, end


def safe_get(url: str, params: dict = None, session: requests.Session = None, delay: float = 0.5) -> Optional[requests.Response]:
    """안전한 HTTP GET 요청"""
    try:
        time.sleep(delay)
        s = session or requests.Session()
        resp = s.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"  ⚠️  요청 실패: {url} → {e}")
        return None


# ─────────────────────────────────────────
# 1. 국내 기업 실적 발표 (DART OpenAPI)
# ─────────────────────────────────────────

class DartEarningsCalendar:
    """
    금융감독원 DART OpenAPI를 이용한 실적 발표 일정 수집
    API 키 발급: https://opendart.fss.or.kr/intro/main.do
    """
    BASE_URL = "https://opendart.fss.or.kr/api"
    api_key = ''

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_disclosure_list(self, start_dt: str, end_dt: str, pblntf_ty: str = "I") -> pd.DataFrame:
        """
        공시 목록 조회
        pblntf_ty: A=정기공시, B=주요사항보고, C=발행공시, I=기타 → 실적은 A
        """
        url = f"{self.BASE_URL}/list.json"
        params = {
            "crtfc_key": self.api_key,
            "bgn_de": start_dt,          # 시작일 YYYYMMDD
            "end_de": end_dt,            # 종료일 YYYYMMDD
            "pblntf_ty": "A",            # 정기공시 (사업보고서·분기보고서)
            "page_count": 100,
        }
        resp = safe_get(url, params=params)
        if not resp:
            return pd.DataFrame()

        data = resp.json()
        if data.get("status") != "000":
            print(f"  DART 오류: {data.get('message')}")
            return pd.DataFrame()

        items = data.get("list", [])
        df = pd.DataFrame(items)
        if df.empty:
            return df

        df = df[["rcept_dt", "corp_name", "report_nm", "stock_code"]].copy()
        df.columns = ["발표일", "기업명", "보고서명", "종목코드"]
        df["카테고리"] = "국내 실적 발표"
        df["발표일"] = pd.to_datetime(df["발표일"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return df.sort_values("발표일").reset_index(drop=True)


# ─────────────────────────────────────────
# 2. 국내 기업 실적 발표
#    1차: 와이즈리포트 (wisereport.co.kr) 실적 캘린더
#    2차: FnGuide 실적 발표 검색
#    3차: 연합인포맥스 실적 발표 일정
# ─────────────────────────────────────────

class NaverEarningsCalendar:
    """
    국내 기업 실적 발표 일정 수집 (네이버 금융 URL 폐기 → 대체 소스 사용)
    DART API 키가 있으면 DartEarningsCalendar 사용 권장
    """

    def _get_from_wisereport(self, year: int, month: int) -> pd.DataFrame:
        """와이즈리포트 실적 발표 캘린더 (월별)"""
        url = "https://wisereport.co.kr/etf/index_qf.aspx"
        headers = {**HEADERS, "Referer": "https://wisereport.co.kr/"}
        try:
            time.sleep(0.6)
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = []
            for tr in soup.select("table tr"):
                tds = tr.select("td")
                if len(tds) >= 4:
                    texts = [td.get_text(strip=True) for td in tds]
                    if any(re.search(r'\d{4}[./\-]\d{2}', t) for t in texts):
                        rows.append({
                            "발표일": texts[0], "기업명": texts[1],
                            "분기": texts[2], "매출액(억)": texts[3],
                            "영업이익(억)": texts[4] if len(texts) > 4 else "",
                            "카테고리": "국내 실적 발표",
                        })
            if rows:
                return pd.DataFrame(rows)
        except Exception as e:
            print(f"  ⚠️  와이즈리포트 실패: {e}")
        return pd.DataFrame()

    def _get_from_fnguide(self, year: int, month: int) -> pd.DataFrame:
        """FnGuide Consensus 실적 발표 일정"""
        # FnGuide 실적발표 검색 URL (월별 캘린더)
        url = "https://comp.fnguide.com/SVO2/asp/SVD_Consensus.asp"
        ym  = f"{year}{month:02d}"
        headers = {**HEADERS, "Referer": "https://comp.fnguide.com/"}
        try:
            time.sleep(0.6)
            resp = requests.get(url, params={"yyyymm": ym}, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = []
            for tr in soup.select("table#earnings_calendar tbody tr, table tbody tr"):
                tds = tr.select("td")
                if len(tds) < 3:
                    continue
                texts = [td.get_text(strip=True) for td in tds]
                if texts[0] and re.search(r'\d', texts[0]):
                    rows.append({
                        "발표일": texts[0], "기업명": texts[1] if len(texts) > 1 else "",
                        "분기": texts[2] if len(texts) > 2 else "",
                        "매출액(억)": texts[3] if len(texts) > 3 else "",
                        "영업이익(억)": texts[4] if len(texts) > 4 else "",
                        "카테고리": "국내 실적 발표",
                    })
            if rows:
                return pd.DataFrame(rows)
        except Exception as e:
            print(f"  ⚠️  FnGuide 실패: {e}")
        return pd.DataFrame()

    def _get_from_yonhap(self, year: int, month: int) -> pd.DataFrame:
        """연합인포맥스 실적 발표 일정"""
        url = "https://news.einfomax.co.kr/news/articleList.html"
        params = {"sc_section_code": "S1N6", "view_type": "sm"}
        headers = {**HEADERS, "Referer": "https://news.einfomax.co.kr/"}
        try:
            time.sleep(0.5)
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = []
            for li in soup.select("ul.type2 li, .list-body li"):
                title = li.select_one(".titles a, h4 a")
                date  = li.select_one(".byline em, .dated")
                if title and date:
                    rows.append({
                        "발표일": date.get_text(strip=True),
                        "기업명": title.get_text(strip=True),
                        "분기": "", "매출액(억)": "", "영업이익(억)": "",
                        "카테고리": "국내 실적 발표 (뉴스)",
                    })
            if rows:
                return pd.DataFrame(rows[:30])
        except Exception as e:
            print(f"  ⚠️  연합인포맥스 실패: {e}")
        return pd.DataFrame()

    def get_earnings(self, page: int = 1) -> pd.DataFrame:
        today = datetime.today()
        return self.get_earnings_by_month(today.year, today.month)

    def get_earnings_by_month(self, year: int, month: int) -> pd.DataFrame:
        # 1차
        df = self._get_from_wisereport(year, month)
        if not df.empty:
            return df
        # 2차
        df = self._get_from_fnguide(year, month)
        if not df.empty:
            return df
        # 3차
        df = self._get_from_yonhap(year, month)
        if not df.empty:
            return df
        print("  ℹ️  국내 실적발표: 무료 소스 수집 실패. DART API 키 사용 권장 (무료 발급)")
        return pd.DataFrame()

    def get_all_earnings(self, pages: int = 3) -> pd.DataFrame:
        """이번 달 포함 최근 pages개월 수집"""
        today = datetime.today()
        frames = []
        for i in range(pages):
            dt = today - timedelta(days=30 * i)
            df = self.get_earnings_by_month(dt.year, dt.month)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
        return df.drop_duplicates(subset=["발표일", "기업명"]).reset_index(drop=True)


# ─────────────────────────────────────────
# 3. KRX KIND - 공모주 청약 일정
# ─────────────────────────────────────────

class KindIPOCalendar:
    """
    KRX KIND 시스템에서 공모주 청약 일정 수집
    https://kind.krx.co.kr/public/iposchedulelist.do
    """
    URL = "https://kind.krx.co.kr/public/iposchedulelist.do"

    def get_ipo_schedule(self, start_dt: str = None, end_dt: str = None) -> pd.DataFrame:
        start_dt, end_dt = get_date_range(start_dt, end_dt)
        # KIND는 form-POST 방식
        payload = {
            "method": "searchIpoScheduleList",
            "currentPageSize": "100",
            "pageIndex": "1",
            "searchStartDt": f"{start_dt[:4]}.{start_dt[4:6]}.{start_dt[6:]}",
            "searchEndDt": f"{end_dt[:4]}.{end_dt[4:6]}.{end_dt[6:]}",
        }
        try:
            time.sleep(0.5)
            resp = requests.post(self.URL, data=payload, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  ⚠️  KIND 요청 실패: {e}")
            return pd.DataFrame()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = []
        for tr in soup.select("table tbody tr"):
            tds = tr.select("td")
            if len(tds) < 6:
                continue
            rows.append({
                "청약시작일": tds[0].get_text(strip=True),
                "청약종료일": tds[1].get_text(strip=True),
                "기업명":     tds[2].get_text(strip=True),
                "시장구분":   tds[3].get_text(strip=True),   # KOSPI/KOSDAQ
                "공모가":     tds[4].get_text(strip=True),
                "주간사":     tds[5].get_text(strip=True),
                "카테고리":   "공모주 청약",
            })

        return pd.DataFrame(rows)


# ─────────────────────────────────────────
# 4. 한국은행 경제통계시스템 (ECOS) - 경제 지표 발표 일정
# ─────────────────────────────────────────

class BOKEcoCalendar:
    """
    한국은행 ECOS OpenAPI - 경제통계 발표 일정
    API 키 발급: https://ecos.bok.or.kr/api/
    """
    BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"

    def __init__(self, api_key: str = "sample"):
        self.api_key = api_key  # 'sample'로 제한적 조회 가능

    def get_release_calendar(self, stat_code: str, start_dt: str, end_dt: str) -> pd.DataFrame:
        """
        주요 통계 코드 예시:
          722Y001 - 기준금리
          036Y001 - 소비자물가지수(CPI)
          021Y125 - 국세수입
          511Y002 - 국내총생산(GDP)
        """
        url = f"{self.BASE_URL}/{self.api_key}/json/kr/1/100/{stat_code}/M/{start_dt}/{end_dt}"
        resp = safe_get(url)
        if not resp:
            return pd.DataFrame()
        try:
            data = resp.json()
            items = data.get("StatisticSearch", {}).get("row", [])
            df = pd.DataFrame(items)
            if df.empty:
                return df
            df["카테고리"] = "경제 지표"
            return df
        except Exception as e:
            print(f"  BOK 파싱 오류: {e}")
            return pd.DataFrame()


# ─────────────────────────────────────────
# 5. 미국 기업 실적 발표
#    1차: Nasdaq Earnings Calendar API (JSON, 인증 불필요)
#    2차: Earnings Whispers JSON API
#    3차: StockAnalysis.com 스크래핑
# ─────────────────────────────────────────

class YahooEarningsCalendar:
    """
    미국 기업 실적 발표 캘린더 (Yahoo Finance 대체 소스 사용)
    Yahoo Finance는 JS 렌더링 필요 → Nasdaq/EarningsWhispers/StockAnalysis 사용
    """

    # ── 1차: Nasdaq Earnings Calendar API ──
    NASDAQ_URL = "https://api.nasdaq.com/api/calendar/earnings"

    # ── 2차: Earnings Whispers (earningswhispers.com) ──
    EW_URL = "https://www.earningswhispers.com/api/earningscal"

    # ── 3차: StockAnalysis Earnings Calendar ──
    SA_URL = "https://stockanalysis.com/earnings-calendar/"

    def _get_from_nasdaq(self, date: str) -> pd.DataFrame:
        """Nasdaq 공식 Earnings Calendar JSON API"""
        headers = {
            **HEADERS,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nasdaq.com/",
            "Origin": "https://www.nasdaq.com",
        }
        try:
            time.sleep(0.7)
            resp = requests.get(
                self.NASDAQ_URL,
                params={"date": date},
                headers=headers,
                timeout=12,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ⚠️  Nasdaq API 실패: {e}")
            return pd.DataFrame()

        try:
            rows_raw = (
                data.get("data", {})
                    .get("rows", [])
            )
            if not rows_raw:
                return pd.DataFrame()

            rows = []
            for item in rows_raw:
                rows.append({
                    "발표일":   date,
                    "티커":    item.get("symbol", ""),
                    "기업명":  item.get("name", ""),
                    "발표시간": item.get("time", ""),          # Before Open / After Close
                    "EPS 예상": item.get("eps_forecast", ""),
                    "EPS 실제": item.get("eps_actual", ""),
                    "매출 예상": item.get("revenue_forecast", ""),
                    "매출 실제": item.get("revenue_actual", ""),
                    "카테고리": "미국 실적 발표",
                })
            return pd.DataFrame(rows)
        except Exception as e:
            print(f"  ⚠️  Nasdaq 파싱 오류: {e}")
            return pd.DataFrame()

    def _get_from_stockanalysis(self, date: str) -> pd.DataFrame:
        """StockAnalysis.com 실적 캘린더 스크래핑"""
        url = f"https://stockanalysis.com/earnings-calendar/?date={date}"
        headers = {
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml",
            "Referer": "https://stockanalysis.com/",
        }
        try:
            time.sleep(0.8)
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
        except Exception as e:
            print(f"  ⚠️  StockAnalysis 요청 실패: {e}")
            return pd.DataFrame()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = []
        # StockAnalysis는 테이블 또는 데이터 속성 기반
        for tr in soup.select("table tbody tr"):
            tds = tr.select("td")
            if len(tds) < 3:
                continue
            rows.append({
                "발표일":   date,
                "티커":    tds[0].get_text(strip=True),
                "기업명":  tds[1].get_text(strip=True),
                "발표시간": tds[2].get_text(strip=True) if len(tds) > 2 else "",
                "EPS 예상": tds[3].get_text(strip=True) if len(tds) > 3 else "",
                "EPS 실제": tds[4].get_text(strip=True) if len(tds) > 4 else "",
                "카테고리": "미국 실적 발표",
            })
        return pd.DataFrame(rows)

    def get_earnings(self, date: str = None) -> pd.DataFrame:
        """특정 날짜 실적 발표 수집 (소스 자동 선택)"""
        if not date:
            date = datetime.today().strftime("%Y-%m-%d")

        # 1차: Nasdaq API
        df = self._get_from_nasdaq(date)
        if not df.empty:
            return df

        # 2차: StockAnalysis
        print(f"  ℹ️  Nasdaq 데이터 없음, StockAnalysis 시도 중...")
        df = self._get_from_stockanalysis(date)
        if not df.empty:
            return df

        print(f"  ⚠️  {date} 미국 실적 데이터 수집 실패 (주말/휴장 가능성)")
        return pd.DataFrame()

    def get_week_earnings(self) -> pd.DataFrame:
        """이번 주 월~금 실적 발표 수집"""
        today = datetime.today()
        # 월요일 기준으로 이번 주 시작
        monday = today - timedelta(days=today.weekday())
        frames = []
        for i in range(5):
            d = monday + timedelta(days=i)
            df = self.get_earnings(d.strftime("%Y-%m-%d"))
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["발표일", "티커"]
        ).reset_index(drop=True)


# ─────────────────────────────────────────
# 6. Investing.com 글로벌 경제 지표 캘린더
# ─────────────────────────────────────────

class InvestingEcoCalendar:
    """
    Investing.com 경제 캘린더 API (비공개 엔드포인트)
    주요 경제 지표 발표 일정 수집
    """
    URL = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"

    COUNTRY_IDS = {
        "한국": 11,
        "미국": 5,
        "일본": 35,
        "중국": 37,
        "유럽": 72,
    }

    def get_calendar(
        self,
        start_dt: str = None,
        end_dt: str = None,
        countries: list = None,
        importance: list = None,
    ) -> pd.DataFrame:
        """
        importance: 1=낮음, 2=보통, 3=높음
        """
        start_dt, end_dt = get_date_range(start_dt, end_dt)
        if not countries:
            countries = [5, 11]   # 미국, 한국
        if not importance:
            importance = [2, 3]   # 보통 이상

        # 날짜 형식 변환
        s = f"{start_dt[:4]}-{start_dt[4:6]}-{start_dt[6:]}"
        e = f"{end_dt[:4]}-{end_dt[4:6]}-{end_dt[6:]}"

        payload = {
            "dateFrom": s,
            "dateTo": e,
            "timeZone": "18",      # UTC+9 (서울)
            "timeFilter": "timeRemain",
            "currentTab": "custom",
            "submitFilters": 1,
            "limit_from": 0,
            "country[]": countries,
            "importance[]": importance,
        }
        headers = {
            **HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.investing.com/economic-calendar/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            time.sleep(1.0)
            resp = requests.post(self.URL, data=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ⚠️  Investing.com 요청 실패: {e}")
            return pd.DataFrame()

        html = data.get("data", "")
        if not html:
            return pd.DataFrame()

        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.select("tr.js-event-item"):
            try:
                date  = tr.get("data-event-datetime", "").strip()
                name  = tr.select_one(".event").get_text(strip=True)
                ctry  = tr.select_one(".flagCur").get_text(strip=True)
                imp   = len(tr.select(".grayFullBullishIcon"))  # 중요도 (불 아이콘 수)
                actual   = tr.select_one(".bold").get_text(strip=True) if tr.select_one(".bold") else ""
                forecast = tr.select_one(".fore").get_text(strip=True) if tr.select_one(".fore") else ""
                previous = tr.select_one(".prev").get_text(strip=True) if tr.select_one(".prev") else ""
                rows.append({
                    "발표일시": date,
                    "국가": ctry,
                    "지표명": name,
                    "중요도": "🔴" * imp + "⚪" * (3 - imp),
                    "실제": actual,
                    "예상": forecast,
                    "이전": previous,
                    "카테고리": "글로벌 경제 지표",
                })
            except Exception:
                continue

        return pd.DataFrame(rows)


# ─────────────────────────────────────────
# 7. KRX 증시 휴장일
# ─────────────────────────────────────────

class KRXHolidayCalendar:
    """
    KRX 증시 휴장일 조회
    1차: pandas_market_calendars (안정적, pip install pandas-market-calendars)
    2차: pykrx stock.get_trading_dates() (pip install pykrx)
    3차: KRX OTP 다운로드 방식
    """

    def get_holidays(self, year: int = None) -> pd.DataFrame:
        if not year:
            year = datetime.today().year

        # ── 1차: pandas_market_calendars (가장 안정적) ──
        try:
            import pandas_market_calendars as mcal
            krx      = mcal.get_calendar("XKRX")
            schedule = krx.schedule(
                start_date=f"{year}-01-01",
                end_date=f"{year}-12-31",
            )
            all_bdays = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="B")
            holidays  = all_bdays.difference(schedule.index)
            if len(holidays) > 0:
                df = pd.DataFrame({
                    "날짜":    holidays.strftime("%Y-%m-%d"),
                    "요일":    [d.strftime("%a") for d in holidays],
                    "휴장여부": "Y",
                    "카테고리": "국내 증시 휴장",
                })
                print(f"  ✅  pandas_market_calendars: {year}년 휴장일 {len(df)}건")
                return df.reset_index(drop=True)
        except ImportError:
            print("  ℹ️  pandas_market_calendars 미설치: pip install pandas-market-calendars")
        except Exception as e:
            print(f"  ⚠️  pandas_market_calendars 오류: {e}")

        # ── 2차: pykrx (올바른 메서드명 사용) ──
        try:
            from pykrx import stock as krx_stock
            # pykrx 실제 메서드: get_trading_dates (버전별 이름 다름)
            get_td = (
                getattr(krx_stock, "get_trading_dates", None)
                or getattr(krx_stock, "get_market_trading_dates", None)
            )
            if get_td is None:
                raise AttributeError("pykrx trading date 메서드를 찾을 수 없습니다.")

            biz_days = pd.DatetimeIndex(
                get_td(f"{year}0101", f"{year}1231", market="KOSPI")
            )
            all_bdays = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="B")
            holidays  = all_bdays.difference(biz_days)
            df = pd.DataFrame({
                "날짜":    holidays.strftime("%Y-%m-%d"),
                "요일":    [d.strftime("%a") for d in holidays],
                "휴장여부": "Y",
                "카테고리": "국내 증시 휴장",
            })
            print(f"  ✅  pykrx: {year}년 휴장일 {len(df)}건")
            return df.reset_index(drop=True)
        except ImportError:
            print("  ℹ️  pykrx 미설치: pip install pykrx")
        except Exception as e:
            print(f"  ⚠️  pykrx 오류: {e}")

        # ── 3차: KRX OTP 다운로드 (CSV) ──
        return self._get_from_krx_otp(year)

    def _get_from_krx_otp(self, year: int) -> pd.DataFrame:
        """KRX 정보데이터시스템 - OTP 발급 후 CSV 다운로드"""
        gen_url  = "http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
        down_url = "http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
        headers  = {
            **HEADERS,
            "Referer": "https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT01901.cmd",
        }
        try:
            time.sleep(0.5)
            otp_resp = requests.post(gen_url, headers=headers, data={
                "locale": "ko_KR",
                "calnd_dd_from": f"{year}0101",
                "calnd_dd_to":   f"{year}1231",
                "csvxls_isNo":   "false",
                "name":          "fileDown",
                "url":           "dbms/MDC/STAT/standard/MDCSTAT01901",
            }, timeout=10)
            otp = otp_resp.text.strip()
            if not otp:
                raise ValueError("OTP 빈 응답")

            time.sleep(0.5)
            dl = requests.post(down_url, data={"code": otp}, headers=headers, timeout=15)
            dl.encoding = "EUC-KR"
            from io import StringIO
            df = pd.read_csv(StringIO(dl.text))

            # 컬럼 자동 탐지
            date_col  = next((c for c in df.columns if "일자" in c or "날짜" in c), df.columns[0])
            holdy_col = next((c for c in df.columns if "휴" in c), None)
            df = df.rename(columns={date_col: "날짜"})
            if holdy_col:
                df = df[df[holdy_col] == "Y"].rename(columns={holdy_col: "휴장여부"})
            df["카테고리"] = "국내 증시 휴장"
            print(f"  ✅  KRX OTP: {year}년 데이터 수집 완료")
            return df.reset_index(drop=True)
        except Exception as e:
            print(f"  ⚠️  KRX OTP 실패: {e}")
            print("  💡  해결: pip install pandas-market-calendars")
            return pd.DataFrame()


# ─────────────────────────────────────────
# 8. 종합 캘린더 수집기
# ─────────────────────────────────────────

dart_api_key = ""

class StockMarketCalendar:
    """
    모든 증시 캘린더 데이터를 통합 수집하는 메인 클래스
    """

    def __init__(
        self,
        dart_api_key: str = None,
        bok_api_key: str = "sample",
    ):
        self.naver    = NaverEarningsCalendar()
        self.kind     = KindIPOCalendar()
        self.yahoo    = YahooEarningsCalendar()
        self.investing = InvestingEcoCalendar()
        self.krx      = KRXHolidayCalendar()
        self.dart     = DartEarningsCalendar(dart_api_key) if dart_api_key else None
        self.bok      = BOKEcoCalendar(bok_api_key)

    def fetch_all(
        self,
        start_dt: str = None,
        end_dt: str = None,
        sources: list = None,
    ) -> dict[str, pd.DataFrame]:
        """
        모든 캘린더 데이터 수집
        
        Parameters
        ----------
        start_dt : str  시작일 (YYYYMMDD, 기본: 오늘)
        end_dt   : str  종료일 (YYYYMMDD, 기본: 오늘+7일)
        sources  : list 수집할 소스 목록
                       ["naver", "dart", "kind", "yahoo", "investing", "krx"]
                       None이면 전체 수집
        Returns
        -------
        dict : 소스별 DataFrame
        """
        start_dt, end_dt = get_date_range(start_dt, end_dt)
        all_sources = ["naver", "kind", "yahoo", "investing", "krx"]
        if self.dart:
            all_sources.insert(1, "dart")
        if not sources:
            sources = all_sources

        results = {}

        if "naver" in sources:
            print("📊 [1/5] 네이버 금융 - 국내 실적 발표 수집 중...")
            results["국내_실적발표"] = self.naver.get_all_earnings(pages=3)

        if "dart" in sources and self.dart:
            print("📋 [2/5] DART - 공시 실적 발표 수집 중...")
            results["DART_실적발표"] = self.dart.get_disclosure_list(start_dt, end_dt)

        if "kind" in sources:
            print("🏦 [3/5] KRX KIND - 공모주 청약 일정 수집 중...")
            results["공모주_청약"] = self.kind.get_ipo_schedule(start_dt, end_dt)

        if "yahoo" in sources:
            print("🇺🇸 [4/5] Yahoo Finance - 미국 실적 발표 수집 중...")
            results["미국_실적발표"] = 
          self.yahoo.get_week_earnings()

        if "investing" in sources:
            print("🌐 [5/5] Investing.com - 글로벌 경제 지표 수집 중...")
            results["글로벌_경제지표"] = self.investing.get_calendar(
                start_dt, end_dt, countries=[5, 11]
            )

        if "krx" in sources:
            print("🗓️  KRX - 증시 휴장일 수집 중...")
            results["증시_휴장일"] = self.krx.get_holidays()

        return results

    def to_json(self, data: dict, filepath: str = "market_calendar.json"):
        """JSON으로 저장"""
        output = {}
        for key, df in data.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                output[key] = df.to_dict(orient="records")
            else:
                output[key] = []
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n✅ JSON 저장 완료: {filepath}")

    def to_excel(self, data: dict, filepath: str = "market_calendar.xlsx"):
        """Excel로 저장 (시트별 분류)"""
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            for key, df in data.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df.to_excel(writer, sheet_name=key[:31], index=False)
        print(f"✅ Excel 저장 완료: {filepath}")

    def print_summary(self, data: dict):
        """수집 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📅 증시 캘린더 수집 결과 요약")
        print("=" * 60)
        for key, df in data.items():
            count = len(df) if isinstance(df, pd.DataFrame) else 0
            icon = "✅" if count > 0 else "❌"
            print(f"  {icon}  {key}: {count}건")
        print("=" * 60)


# ─────────────────────────────────────────
# Flask REST API 서버 (선택적 사용)
# ─────────────────────────────────────────

def create_api_server():
    """
    Flask를 이용한 REST API 서버
    pip install flask 필요
    
    엔드포인트:
      GET /calendar              - 전체 캘린더
      GET /calendar/earnings     - 실적 발표만
      GET /calendar/ipo          - 공모주 청약만
      GET /calendar/economic     - 경제 지표만
      GET /calendar/holidays     - 휴장일만
    """
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("Flask가 필요합니다: pip install flask")
        return

    app = Flask(__name__)
    calendar = StockMarketCalendar()

    def df_to_response(df: pd.DataFrame):
        if df is None or df.empty:
            return jsonify({"status": "ok", "count": 0, "data": []})
        return jsonify({
            "status": "ok",
            "count": len(df),
            "data": df.to_dict(orient="records"),
        })

    @app.route("/calendar", methods=["GET"])
    def get_all():
        start = request.args.get("start")
        end   = request.args.get("end")
        data  = calendar.fetch_all(start, end)
        result = {}
        for k, df in data.items():
            result[k] = df.to_dict(orient="records") if not df.empty else []
        return jsonify({"status": "ok", "data": result})

    @app.route("/calendar/earnings/kr", methods=["GET"])
    def get_kr_earnings():
        df = calendar.naver.get_all_earnings(pages=3)
        return df_to_response(df)

    @app.route("/calendar/earnings/us", methods=["GET"])
    def get_us_earnings():
        date = request.args.get("date")
        df   = calendar.yahoo.get_earnings(date)
        return df_to_response(df)

    @app.route("/calendar/ipo", methods=["GET"])
    def get_ipo():
        start = request.args.get("start")
        end   = request.args.get("end")
        df    = calendar.kind.get_ipo_schedule(start, end)
        return df_to_response(df)

    @app.route("/calendar/economic", methods=["GET"])
    def get_economic():
        start      = request.args.get("start")
        end        = request.args.get("end")
        countries  = request.args.getlist("country")
        countries  = [int(c) for c in countries] if countries else [5, 11]
        df         = calendar.investing.get_calendar(start, end, countries=countries)
        return df_to_response(df)

    @app.route("/calendar/holidays", methods=["GET"])
    def get_holidays():
        year = request.args.get("year", type=int)
        df   = calendar.krx.get_holidays(year)
        return df_to_response(df)

    return app


# ─────────────────────────────────────────
# 실행 예시
# ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="증시 캘린더 데이터 수집기")
    parser.add_argument("--mode",  default="fetch", choices=["fetch", "server"], help="실행 모드")
    parser.add_argument("--start", default=None, help="시작일 (YYYYMMDD)")
    parser.add_argument("--end",   default=None, help="종료일 (YYYYMMDD)")
    parser.add_argument("--dart",  default=None, help="DART API 키")
    parser.add_argument("--bok",   default="sample", help="한국은행 ECOS API 키")
    parser.add_argument("--out",   default="json", choices=["json", "excel", "both"], help="출력 형식")
    parser.add_argument("--port",  default=5000, type=int, help="서버 포트 (server 모드)")
    args = parser.parse_args()

    if args.mode == "server":
        print("🚀 증시 캘린더 API 서버 시작...")
        app = create_api_server()
        if app:
            app.run(host="0.0.0.0", port=args.port, debug=False)

    else:
        print("🔍 증시 캘린더 데이터 수집 시작\n")
        cal = StockMarketCalendar(dart_api_key=args.dart, bok_api_key=args.bok)
        data = cal.fetch_all(args.start, args.end)
        cal.print_summary(data)

        if args.out in ("json", "both"):
            cal.to_json(data, "market_calendar.json")
        if args.out in ("excel", "both"):
            cal.to_excel(data, "market_calendar.xlsx")
