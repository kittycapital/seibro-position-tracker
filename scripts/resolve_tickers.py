#!/usr/bin/env python3
"""
ISIN → 티커 변환 스크립트
- 수집된 CSV에서 ISIN 추출
- yfinance로 티커 조회
- data/ticker_map.json 생성/업데이트

사용법:
  pip install yfinance
  python scripts/resolve_tickers.py
"""

import json
import csv
import os
import glob
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT_DIR, "data", "history")
MAP_PATH = os.path.join(ROOT_DIR, "data", "ticker_map.json")


def load_existing_map():
    """기존 ticker_map.json 로드"""
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def collect_isins():
    """히스토리 CSV에서 모든 고유 ISIN 수집"""
    isins = set()
    for filepath in glob.glob(os.path.join(HISTORY_DIR, "*.csv")):
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                isin = row.get("isin", "").strip()
                if isin:
                    isins.add(isin)
    return isins


def resolve_ticker_yfinance(isin):
    """yfinance로 ISIN → 티커 변환"""
    try:
        import yfinance as yf
        ticker = yf.utils.get_ticker_by_isin(isin)
        if ticker and ticker != isin:
            return ticker
    except Exception as e:
        pass
    return None


def resolve_ticker_prefix(isin):
    """
    ISIN 접두사 기반 간단 추론 (yfinance 실패 시 폴백)
    US ISIN의 경우 CUSIP 기반이라 직접 변환은 어렵지만,
    일부 패턴은 추론 가능
    """
    # 홍콩: HK + 10자리 → 앞 4자리가 종목코드
    if isin.startswith("HK") and len(isin) == 12:
        code = isin[2:6].lstrip("0")
        if code:
            return f"{code}.HK"

    # 일본: JP + 10자리
    if isin.startswith("JP") and len(isin) == 12:
        return None  # 일본은 yfinance에 맡김

    return None


def main():
    print("=" * 50)
    print("ISIN → 티커 변환")
    print("=" * 50)

    # 기존 맵 로드
    ticker_map = load_existing_map()
    print(f"기존 매핑: {len(ticker_map)}개")

    # ISIN 수집
    isins = collect_isins()
    print(f"수집된 ISIN: {len(isins)}개")

    # 미매핑 ISIN 찾기
    unmapped = [isin for isin in isins if isin not in ticker_map]
    print(f"미매핑: {len(unmapped)}개")

    if not unmapped:
        print("[OK] 모든 ISIN이 매핑되어 있습니다.")
        save_map(ticker_map)
        return

    # yfinance 설치 확인
    try:
        import yfinance
        use_yf = True
        print("[OK] yfinance 사용 가능")
    except ImportError:
        use_yf = False
        print("[WARN] yfinance 미설치 (pip install yfinance)")
        print("[INFO] 접두사 기반 추론만 사용")

    # 변환
    resolved = 0
    for i, isin in enumerate(unmapped):
        print(f"  [{i+1}/{len(unmapped)}] {isin}...", end=" ")

        # 1) yfinance 시도
        ticker = None
        if use_yf:
            ticker = resolve_ticker_yfinance(isin)
            if ticker:
                print(f"→ {ticker} (yfinance)")
                ticker_map[isin] = ticker
                resolved += 1
                time.sleep(0.5)  # rate limit
                continue

        # 2) 접두사 추론
        ticker = resolve_ticker_prefix(isin)
        if ticker:
            print(f"→ {ticker} (prefix)")
            ticker_map[isin] = ticker
            resolved += 1
            continue

        print("→ (미확인)")

    print(f"\n새로 매핑: {resolved}개")
    print(f"총 매핑: {len(ticker_map)}개")
    print(f"미확인: {len(unmapped) - resolved}개")

    save_map(ticker_map)


def save_map(ticker_map):
    """ticker_map.json 저장"""
    os.makedirs(os.path.dirname(MAP_PATH), exist_ok=True)
    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(ticker_map, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[OK] 저장: {MAP_PATH}")


if __name__ == "__main__":
    main()
