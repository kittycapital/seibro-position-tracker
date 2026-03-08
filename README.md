# 🐂 외화증권 순매수 포지션 트래커

한국 투자자의 외화증권 결제내역 TOP50을 추적하고, 포지션 변화를 시각화하는 대시보드입니다.

**Live:** [herdvibe.com](https://herdvibe.com) | **Data Source:** [세이브로(SEIBro)](https://seibro.or.kr)

## 기능

- 🏆 **순매수 TOP50 랭킹** — 전체/미국/홍콩/중국/일본/베트남 국가별
- 🔄 **포지션 변화 추적** — 신규 진입, 이탈, 순위 급등/급락 감지
- 📊 **주간/월간 비교** — 탭 전환으로 기간별 변화 확인
- 📋 **상세 테이블** — 매수/매도/순매수 결제금액 + 변동 배지

## 디렉토리 구조

```
seibro-position-tracker/
├── index.html                    # 대시보드 (GitHub Pages)
├── data/
│   ├── dashboard_data.json       # 대시보드 데이터 (current vs previous)
│   ├── history/                  # 일별 스냅샷
│   │   ├── 2026-03-08_1W.csv
│   │   └── 2026-03-08_1M.csv
│   └── cumulative/               # 누적 히스토리
│       ├── 1W_history.csv
│       └── 1M_history.csv
├── scripts/
│   ├── scraper.py                # 세이브로 데이터 수집
│   └── generate_dashboard.py     # 대시보드 JSON 생성
├── .github/workflows/
│   └── daily.yml                 # GitHub Actions (평일 09:30 KST)
└── README.md
```

## 셋업

### 1. 샘플 데이터로 테스트

```bash
python scripts/scraper.py                 # 샘플 데이터 생성
python scripts/generate_dashboard.py      # dashboard_data.json 생성
```

### 2. 실제 데이터 수집

세이브로 페이지에서 XHR 요청 패턴을 확인한 뒤 `scripts/scraper.py`의 payload를 수정합니다.

```bash
python scripts/scraper.py --real          # 실제 세이브로 수집
python scripts/generate_dashboard.py
```

### 3. GitHub Actions 자동화

Push하면 `.github/workflows/daily.yml`이 평일 한국시간 09:30에 자동 실행됩니다.

## XHR 패턴 확인 방법

1. [세이브로 외화증권 종목별내역](https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/ovsSec/BIP_CNTS10013V.xml&menuNo=921) 접속
2. F12 → Network 탭 → 조회 클릭
3. XHR 요청 중 데이터 응답이 있는 것 찾기
4. 우클릭 → Copy as cURL
5. [curlconverter.com](https://curlconverter.com/) 에서 Python 변환
6. `scripts/scraper.py`에 반영

## 라이선스

데이터 출처: 한국예탁결제원 세이브로(SEIBro)
