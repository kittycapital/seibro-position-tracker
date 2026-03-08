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
from datetime import datetime, timedelta

# 프로젝트 루트 기준 경로
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
CUMULATIVE_DIR = os.path.join(DATA_DIR, "cumulative")

# 세이브로 WebSquare 내부 API 엔드포인트
# ※ 실제 사용 시 브라우저 Network 탭에서 정확한 URL/파라미터를 확인하세요
SEIBRO_URL = "https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp"

# 국가 코드 매핑 (세이브로 내부 코드)
COUNTRY_CODES = {
    "전체": "",
    "미국": "US",
    "홍콩": "HK",
    "중국": "CN",
    "일본": "JP",
    "베트남": "VN"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/ovsSec/BIP_CNTS10013V.xml&menuNo=921",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://seibro.or.kr"
}

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
    elif period == "3M":
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=30)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def fetch_seibro_data(country_code="", period="1M"):
    """
    세이브로 외화증권 종목별 결제내역 TOP50 조회

    ※ 중요: 아래 payload는 예시 구조입니다.
    실제 사용 시 브라우저 F12 > Network 탭에서
    조회 버튼 클릭 시 발생하는 XHR 요청의
    Request Payload를 정확히 복사해서 사용하세요.

    Copy as cURL → https://curlconverter.com/ 에서
    Python 코드로 변환하면 가장 정확합니다.
    """
    start_date, end_date = get_date_range(period)

    # ============================================================
    # ※ 아래 payload는 WebSquare 구조 기반 예시입니다.
    #    실제 파라미터는 Network 탭에서 확인 필요!
    # ============================================================
    payload = {
        "w2xPath": "/IPORTAL/user/ovsSec/BIP_CNTS10013V.xml",
        "menuNo": "921",
        "sttlStatDvCd": "1",       # 결제금액
        "sttlTpDvCd": "4",         # 순매수결제
        "strtDt": start_date,
        "endDt": end_date,
        "natlCd": country_code,
        "pageIndex": "1",
        "pageUnit": "50"
    }

    try:
        resp = requests.post(SEIBRO_URL, data=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return parse_response(data)
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] 요청 실패 ({country_code}): {e}")
        return None


def parse_response(data):
    """
    세이브로 응답 파싱
    ※ 실제 응답 키 구조에 맞게 수정 필요
    """
    results = []
    try:
        items = data.get("body", {}).get("list", [])
        if not items:
            items = data.get("result", {}).get("list", [])
        if not items:
            items = data if isinstance(data, list) else []

        for item in items:
            results.append({
                "rank": item.get("rank", ""),
                "country": item.get("natlNm", ""),
                "isin": item.get("isinCd", ""),
                "name": item.get("secnNm", ""),
                "buy_amount": int(str(item.get("buyAmt", "0")).replace(",", "")),
                "sell_amount": int(str(item.get("selAmt", "0")).replace(",", "")),
                "net_buy_amount": int(str(item.get("netBuyAmt", "0")).replace(",", ""))
            })
    except Exception as e:
        print(f"  [ERROR] 파싱 실패: {e}")
    return results


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

    print(f"  [OK] 스냅샷: {filepath}")


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

    print(f"  [OK] 누적: {filepath}")


def collect_real_data():
    """실제 세이브로 데이터 수집"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"세이브로 외화증권 결제내역 수집 - {today}")
    print(f"{'='*60}")

    for period in ["1W", "1M"]:
        print(f"\n--- {period} 데이터 수집 ---")
        all_data = {}
        for country_name, country_code in COUNTRY_CODES.items():
            print(f"  수집: {country_name} ({country_code or '전체'})")
            data = fetch_seibro_data(country_code, period)
            all_data[country_name] = data if data else []

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
            ("US02079K3059", "ALPHABET INC CL A"),
            ("US88160R1014", "TESLA INC"),
            ("US5949181045", "MICROSOFT CORP"),
            ("US0378331005", "APPLE INC"),
            ("US0231351067", "AMAZON.COM INC"),
            ("US67066G1040", "NVIDIA CORP"),
            ("US30303M1027", "META PLATFORMS INC"),
            ("US80004C2008", "SANDISK CORP"),
            ("US5951121038", "MICRON TECHNOLOGY INC"),
            ("US46625H1005", "JPMORGAN CHASE & CO"),
            ("US4612021034", "INVESCO NASDAQ 100 ETF"),
            ("US46222L1089", "IONQ INC"),
            ("US4642872349", "ISHARES SILVER TRUST ETF"),
            ("US9220428745", "VANGUARD S&P 500 ETF"),
            ("US74347W3630", "PROSHARES ULTRA SILVER ETF"),
            ("US25461A4482", "DIREXION DAILY PLTR BULL 2X"),
            ("US46654Q2030", "JP MORGAN NASDAQ EQ PREMIUM"),
            ("US02079K1079", "ALPHABET INC CL C"),
            ("US92864M7983", "VOLSHARES 2X ETHER ETF"),
            ("US25460G2865", "DIREXION DAILY TSLA BULL 2X"),
            ("US4581401001", "INTEL CORP"),
            ("US09075V1026", "BROADCOM INC"),
            ("US00724F1012", "ADOBE INC"),
            ("US79466L3024", "SALESFORCE INC"),
            ("US64110L1061", "NETFLIX INC"),
            ("US0846707026", "BERKSHIRE HATHAWAY CL B"),
            ("US2546871060", "WALT DISNEY CO"),
            ("US91324P1021", "UNITEDHEALTH GROUP"),
            ("US5324571083", "ELI LILLY AND CO"),
            ("US7427181091", "PROCTER & GAMBLE CO"),
            ("US4370761029", "HOME DEPOT INC"),
            ("US1101221083", "BRISTOL-MYERS SQUIBB"),
            ("US8725901040", "T-MOBILE US INC"),
            ("US0530151036", "AUTOMATIC DATA PROCESSING"),
            ("US6541061031", "NIKE INC CL B"),
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

        # --- 현재(today) 데이터 생성 ---
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
                net = buy - sell
                records.append({
                    "rank": "", "country": country, "isin": isin,
                    "name": name, "buy_amount": buy, "sell_amount": sell,
                    "net_buy_amount": net
                })

            records.sort(key=lambda x: x["net_buy_amount"], reverse=True)
            for i, r in enumerate(records):
                r["rank"] = str(i + 1)
            current_all[country_filter] = records

        save_snapshot(current_all, period, today)
        append_cumulative(current_all, period, today)

        # --- 이전(yesterday) 데이터 생성 (변화 비교용) ---
        prev_all = {}
        for country_filter, records in current_all.items():
            prev_records = []
            for r in records:
                pr = r.copy()
                pr["buy_amount"] = int(r["buy_amount"] * random.uniform(0.6, 1.5))
                pr["sell_amount"] = int(r["sell_amount"] * random.uniform(0.6, 1.5))
                pr["net_buy_amount"] = pr["buy_amount"] - pr["sell_amount"]
                prev_records.append(pr)

            # 일부 종목 이탈 시뮬레이션 (3개 제거)
            if len(prev_records) > 8:
                remove_indices = random.sample(range(3, len(prev_records)), min(3, len(prev_records) - 3))
                prev_records = [r for i, r in enumerate(prev_records) if i not in remove_indices]

            # 신규 진입 시뮬레이션 (2개 추가)
            extras = [
                ("US", "US9311421039", "WALMART INC"),
                ("US", "US22160K1051", "COSTCO WHOLESALE CORP"),
            ]
            for ec, eisin, ename in extras[:2]:
                buy = int(random.uniform(50_000_000, 300_000_000) * mult)
                sell = int(buy * random.uniform(0.3, 0.7))
                prev_records.append({
                    "rank": "", "country": ec, "isin": eisin, "name": ename,
                    "buy_amount": buy, "sell_amount": sell, "net_buy_amount": buy - sell
                })

            prev_records.sort(key=lambda x: x["net_buy_amount"], reverse=True)
            for i, r in enumerate(prev_records):
                r["rank"] = str(i + 1)
            prev_all[country_filter] = prev_records

        save_snapshot(prev_all, period, yesterday)
        append_cumulative(prev_all, period, yesterday)

    print(f"\n[완료] 샘플 데이터 생성 완료! (today={today}, prev={yesterday})")


if __name__ == "__main__":
    if "--real" in sys.argv:
        collect_real_data()
    else:
        print("[INFO] 샘플 데이터 모드 (--real 플래그로 실제 수집)")
        generate_sample_data()
