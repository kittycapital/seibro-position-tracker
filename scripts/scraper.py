#!/usr/bin/env python3
"""
세이브로(SEIBro) 외화증권 종목별 결제내역 TOP50 스크래퍼
- 전체/미국/홍콩/중국/일본/베트남 국가별 수집
- 순매수결제 기준 (결제금액)
- GitHub Actions daily cron 용

사용법:
  python scripts/scraper.py              # 샘플 데이터 생성
  python scripts/scraper.py --real       # 실제 세이브로 수집
"""

import requests
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# 프로젝트 루트 기준 경로
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
CUMULATIVE_DIR = os.path.join(DATA_DIR, "cumulative")

# ─── 세이브로 API 설정 (cURL에서 추출) ───
SEIBRO_URL = "https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp"

HEADERS = {
    "Accept": "application/xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": 'application/xml; charset="UTF-8"',
    "Origin": "https://seibro.or.kr",
    "Referer": "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/ovsSec/BIP_CNTS10013V.xml&menuNo=921",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "submissionid": "submission_getImptFrcurStkSetlAmtList",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# 국가 코드 매핑
COUNTRY_CODES = {
    "전체": "ALL",
    "미국": "US",
    "홍콩": "HK",
    "중국": "CN",
    "일본": "JP",
    "베트남": "VN"
}

# S_TYPE: 1=보관금액, 2=결제금액
# D_TYPE: 1=매수결제, 2=매도결제, 3=매수+매도결제, 4=순매수결제
S_TYPE = "2"
D_TYPE = "4"

CSV_FIELDS = [
    "date", "period", "country_filter", "rank", "country",
    "isin", "name", "buy_amount", "sell_amount", "net_buy_amount"
]


def get_date_range(period="1M"):
    """조회 기간 계산"""
    end_date = datetime.now()
    if period == "1W":
        start_date = end_date - timedelta(days=7)
    elif period == "1M":
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=30)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def build_xml_payload(country_code="ALL", start_dt="20260207", end_dt="20260306"):
    """세이브로 요청 XML 생성"""
    return (
        '<reqParam action="getImptFrcurStkSetlAmtList" '
        'task="ksd.safe.bip.cnts.OvsSec.process.OvsSecIsinPTask">'
        '<MENU_NO value="921"/>'
        '<CMM_BTN_ABBR_NM value="total_search,openall,print,hwp,word,pdf,seach,"/>'
        '<W2XPATH value="/IPORTAL/user/ovsSec/BIP_CNTS10013V.xml"/>'
        '<PG_START value="1"/>'
        '<PG_END value="50"/>'
        f'<START_DT value="{start_dt}"/>'
        f'<END_DT value="{end_dt}"/>'
        f'<S_TYPE value="{S_TYPE}"/>'
        f'<S_COUNTRY value="{country_code}"/>'
        f'<D_TYPE value="{D_TYPE}"/>'
        '</reqParam>'
    )


def fetch_seibro_data(country_code="ALL", period="1M"):
    """세이브로 외화증권 종목별 결제내역 TOP50 조회"""
    start_dt, end_dt = get_date_range(period)
    payload = build_xml_payload(country_code, start_dt, end_dt)

    try:
        resp = requests.post(
            SEIBRO_URL,
            data=payload.encode("utf-8"),
            headers=HEADERS,
            timeout=30
        )
        resp.raise_for_status()

        # 응답이 XML인지 확인
        content = resp.text.strip()
        if not content.startswith("<"):
            print(f"  [WARN] 비정상 응답 (첫 200자): {content[:200]}")
            return None

        return parse_xml_response(content)

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] 요청 실패 ({country_code}): {e}")
        return None


def parse_xml_response(xml_text):
    """
    세이브로 XML 응답 파싱

    실제 응답 구조:
    <data vectorkey="0" type="Document">
      <result>
        <RNUM value="1"/>
        <NATION_NM value="미국"/>
        <ISIN value="US25459W4583"/>
        <KOR_SECN_NM value="DIREXION DAILY SEMICONDUCTORS BULL 3X SHS ETF"/>
        <SUM_FRSEC_BUY_AMT value="1493437711"/>
        <SUM_FRSEC_SELL_AMT value="471083798"/>
        <SUM_FRSEC_NET_BUY_AMT value="1022353913"/>
        <SUM_FRSEC_TOT_AMT value="1"/>
      </result>
      <result>...</result>
      ...
    </data>
    """
    results = []

    try:
        root = ET.fromstring(xml_text)

        # <result> 태그가 각 종목 행
        rows = root.findall(".//result")

        if not rows:
            print(f"  [WARN] <result> 태그 없음")
            print(f"  [DEBUG] 응답 첫 500자:\n{xml_text[:500]}")
            return results

        for row in rows:
            # 각 하위 요소의 value 속성에서 값 추출
            def val(tag_name):
                el = row.find(tag_name)
                if el is not None:
                    return el.get("value", "").strip()
                return ""

            isin = val("ISIN")
            name = val("KOR_SECN_NM")

            if not isin and not name:
                continue

            results.append({
                "rank": val("RNUM") or str(len(results) + 1),
                "country": val("NATION_NM"),
                "isin": isin,
                "name": name,
                "buy_amount": parse_amount(val("SUM_FRSEC_BUY_AMT")),
                "sell_amount": parse_amount(val("SUM_FRSEC_SELL_AMT")),
                "net_buy_amount": parse_amount(val("SUM_FRSEC_NET_BUY_AMT"))
            })

        print(f"  [OK] {len(results)}개 종목 파싱")

    except ET.ParseError as e:
        print(f"  [ERROR] XML 파싱 에러: {e}")
        print(f"  [DEBUG] 응답 첫 300자:\n{xml_text[:300]}")

    return results


def parse_amount(value):
    """금액 문자열 → 정수"""
    if not value:
        return 0
    try:
        return int(str(value).replace(",", "").replace(" ", ""))
    except ValueError:
        return 0


def save_snapshot(all_data, period, today):
    """일별 스냅샷 CSV 저장"""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    filepath = os.path.join(HISTORY_DIR, f"{today}_{period}.csv")

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for country_filter, records in all_data.items():
            if records:
                for record in records:
                    row = {**record, "date": today, "period": period, "country_filter": country_filter}
                    writer.writerow(row)

    count = sum(len(r) for r in all_data.values() if r)
    print(f"  [OK] 스냅샷: {os.path.basename(filepath)} ({count}개 레코드)")


def append_cumulative(all_data, period, today):
    """누적 히스토리 CSV에 append"""
    os.makedirs(CUMULATIVE_DIR, exist_ok=True)
    filepath = os.path.join(CUMULATIVE_DIR, f"{period}_history.csv")
    file_exists = os.path.exists(filepath)

    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        for country_filter, records in all_data.items():
            if records:
                for record in records:
                    row = {**record, "date": today, "period": period, "country_filter": country_filter}
                    writer.writerow(row)

    print(f"  [OK] 누적: {os.path.basename(filepath)}")


def collect_real_data():
    """실제 세이브로 데이터 수집"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"세이브로 외화증권 결제내역 수집 - {today}")
    print(f"{'='*60}")

    import time

    for period in ["1W", "1M"]:
        print(f"\n--- {period} 데이터 수집 ---")
        all_data = {}
        for country_name, country_code in COUNTRY_CODES.items():
            print(f"  수집: {country_name} ({country_code})")
            data = fetch_seibro_data(country_code, period)
            all_data[country_name] = data if data else []
            time.sleep(2)  # 요청 간 2초 딜레이

        save_snapshot(all_data, period, today)
        append_cumulative(all_data, period, today)

    print(f"\n[완료] 수집 완료!")


def generate_sample_data():
    """샘플 데이터 생성 (테스트/개발용)"""
    import random
    random.seed(42)

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    sample_stocks = {
        "미국": [
            ("US25461A3876", "DIREXION SHARES ETF TRUST DAILY MSCI S"),
            ("US5949181045", "MICROSOFT CORP"),
            ("US0231351067", "AMAZON.COM INC"),
            ("US4613886492", "INVESCO NASDAQ 100 ETF"),
            ("US74347X8314", "PROSHARES ULTRAPRO QQQ ETF"),
            ("US4642867729", "ISHARES MSCI SOUTH KOREA ETF"),
            ("US8085247976", "SCHWAB US DIVIDEND EQUITY ETF"),
            ("US46654Q2030", "JP MORGAN NASDAQ EQUITY PREMIUM IN"),
            ("US1725731079", "Circle Internet"),
            ("CA85207K1075", "SPROTT PHYSICAL SILVER TRUST"),
            ("US92864M7983", "VOLATILITY SHARES TRUST 2X ETHER ETF"),
            ("US9229083632", "VANGUARD SP 500 ETF"),
            ("US68389X1054", "ORACLE CORP"),
            ("US74347R2067", "PROSHARES ULTRA QQQ ETF"),
            ("US8740391003", "TAIWAN SEMICONDUCTOR MFG"),
            ("US46222L1089", "IONQ INC"),
            ("US19247G1076", "II-VI INCORPORATED"),
            ("US30231G1022", "EXXON MOBIL CORP"),
            ("US67079K1007", "NUSCALE POWER CORP"),
            ("US03823U1025", "APPLIED OPTOELECTRONICS INC"),
            ("US3463751087", "FORMFACTOR INC"),
            ("US88160R1014", "TESLA INC"),
            ("US0378331005", "APPLE INC"),
            ("US67066G1040", "NVIDIA CORP"),
            ("US30303M1027", "META PLATFORMS INC"),
            ("US02079K3059", "ALPHABET INC CL A"),
            ("US5951121038", "MICRON TECHNOLOGY INC"),
            ("US4581401001", "INTEL CORP"),
            ("US09075V1026", "BROADCOM INC"),
            ("US64110L1061", "NETFLIX INC"),
        ],
        "홍콩": [
            ("HK0000069689", "TENCENT HOLDINGS"),
            ("HK0941009539", "CHINA MOBILE"),
            ("HK0700880927", "ALIBABA GROUP"),
            ("HK0388045442", "HKEX"),
            ("HK0005004626", "HSBC HOLDINGS"),
        ],
        "일본": [
            ("JP3633400001", "TOYOTA MOTOR CORP"),
            ("JP3435000009", "SONY GROUP CORP"),
            ("JP3756600007", "NINTENDO CO LTD"),
            ("JP3902900004", "SOFTBANK GROUP CORP"),
            ("JP3371200001", "KEYENCE CORP"),
        ],
        "중국": [
            ("CNE100000296", "KWEICHOW MOUTAI CO"),
            ("CNE0000018R8", "CATL"),
            ("CNE100003662", "BYD COMPANY LTD"),
        ],
        "베트남": [
            ("VN000000VNM4", "VINAMILK"),
            ("VN000000VHM1", "VINHOMES JSC"),
        ],
    }

    for period in ["1W", "1M"]:
        mult = 0.3 if period == "1W" else 1.0
        current_all = {}
        for country_filter in COUNTRY_CODES:
            if country_filter == "전체":
                pool = [(c, isin, nm) for c, stocks in sample_stocks.items() for isin, nm in stocks]
            else:
                pool = [(country_filter, isin, nm) for isin, nm in sample_stocks.get(country_filter, [])]
            records = []
            for country, isin, name in pool[:50]:
                buy = int(random.uniform(80_000_000, 1_500_000_000) * mult)
                sell = int(buy * random.uniform(0.15, 0.85))
                records.append({"rank": "", "country": country, "isin": isin,
                    "name": name, "buy_amount": buy, "sell_amount": sell,
                    "net_buy_amount": buy - sell})
            records.sort(key=lambda x: x["net_buy_amount"], reverse=True)
            for i, r in enumerate(records): r["rank"] = str(i + 1)
            current_all[country_filter] = records
        save_snapshot(current_all, period, today)
        append_cumulative(current_all, period, today)

        prev_all = {}
        for cf, records in current_all.items():
            prev = []
            for r in records:
                pr = r.copy()
                pr["buy_amount"] = int(r["buy_amount"] * random.uniform(0.6, 1.5))
                pr["sell_amount"] = int(r["sell_amount"] * random.uniform(0.6, 1.5))
                pr["net_buy_amount"] = pr["buy_amount"] - pr["sell_amount"]
                prev.append(pr)
            if len(prev) > 8:
                rm = random.sample(range(3, len(prev)), min(3, len(prev)-3))
                prev = [r for i, r in enumerate(prev) if i not in rm]
            prev.sort(key=lambda x: x["net_buy_amount"], reverse=True)
            for i, r in enumerate(prev): r["rank"] = str(i+1)
            prev_all[cf] = prev
        save_snapshot(prev_all, period, yesterday)
        append_cumulative(prev_all, period, yesterday)

    print(f"\n[완료] 샘플 생성 완료! ({today}, {yesterday})")


if __name__ == "__main__":
    if "--real" in sys.argv:
        collect_real_data()
    else:
        print("[INFO] 샘플 모드 (--real 플래그로 실제 수집)")
        generate_sample_data()
