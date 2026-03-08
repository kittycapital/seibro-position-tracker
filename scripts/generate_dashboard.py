#!/usr/bin/env python3
"""
대시보드용 JSON 생성기
- data/history/ 에서 최신 스냅샷과 직전 스냅샷을 비교
- data/dashboard_data.json 출력
"""

import csv
import json
import os
import glob
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT_DIR, "data", "history")
OUTPUT_PATH = os.path.join(ROOT_DIR, "data", "dashboard_data.json")

PERIODS = ["1W", "1M"]
COUNTRY_FILTERS = ["전체", "미국", "홍콩", "중국", "일본", "베트남"]


def load_snapshot(filepath):
    """CSV 스냅샷을 딕셔너리로 로드"""
    data = {}
    if not os.path.exists(filepath):
        return data

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cf = row["country_filter"]
            if cf not in data:
                data[cf] = []
            data[cf].append({
                "rank": row["rank"],
                "country": row["country"],
                "isin": row["isin"],
                "name": row["name"],
                "buy_amount": int(row["buy_amount"]),
                "sell_amount": int(row["sell_amount"]),
                "net_buy_amount": int(row["net_buy_amount"])
            })

    return data


def find_snapshots(period):
    """해당 period의 스냅샷 파일 목록 (날짜 내림차순)"""
    pattern = os.path.join(HISTORY_DIR, f"*_{period}.csv")
    files = sorted(glob.glob(pattern), reverse=True)
    return files


def generate():
    """dashboard_data.json 생성"""
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "current": {},
        "previous": {}
    }

    for period in PERIODS:
        snapshots = find_snapshots(period)

        if len(snapshots) == 0:
            print(f"  [WARN] {period} 스냅샷 없음")
            output["current"][period] = {}
            output["previous"][period] = {}
            continue

        # 최신 = 첫 번째 파일
        latest = load_snapshot(snapshots[0])
        latest_date = os.path.basename(snapshots[0]).replace(f"_{period}.csv", "")
        print(f"  [OK] {period} 최신: {latest_date} ({len(latest.get('전체', []))} 종목)")

        output["current"][period] = latest

        # 이전 = 두 번째 파일 (있으면)
        if len(snapshots) >= 2:
            prev = load_snapshot(snapshots[1])
            prev_date = os.path.basename(snapshots[1]).replace(f"_{period}.csv", "")
            print(f"  [OK] {period} 이전: {prev_date} ({len(prev.get('전체', []))} 종목)")
            output["previous"][period] = prev
        else:
            print(f"  [INFO] {period} 이전 스냅샷 없음 (첫 수집)")
            output["previous"][period] = latest  # 첫날은 동일 데이터

    # JSON 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[완료] {OUTPUT_PATH} 생성!")
    return output


if __name__ == "__main__":
    print("=" * 50)
    print("대시보드 JSON 생성")
    print("=" * 50)
    generate()
