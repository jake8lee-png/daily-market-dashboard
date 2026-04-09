# 한미 시장 Daily 대시보드

KOSPI · KOSDAQ · S&P 500 · NASDAQ 일일 시장 지표를 자동으로 수집하고 시각화하는 대시보드입니다.

## 기능
- 4개 시장 지수 현황 + 1개월 차트
- 시총 상위 10종목 등락률
- KOSPI/KOSDAQ 섹터별 등락 히트맵
- 신용잔고, 예탁금, 외국인 수급 추이
- VIX, 금리, 환율, DXY 크로스마켓 지표

## 자동 업데이트
GitHub Actions가 하루 2번 실행됩니다:
- **오후 4시 KST** — 한국 장 마감 후
- **오전 7시 KST** — 미국 장 마감 후

## 설정 방법

### 1. GitHub Pages 활성화
1. Settings > Pages > Source: **Deploy from a branch**
2. Branch: `main` / `/ (root)` 선택
3. Save

### 2. Actions 권한 확인
Settings > Actions > General > Workflow permissions:
**Read and write permissions** 체크

### 3. 수동 실행
Actions 탭 > "Update Market Data" > "Run workflow" 클릭

## 데이터 출처
- Yahoo Finance (미국 시장, 크로스마켓, 한국 주가)
- DART 전자공시 (한국 시장 섹터, 공매도)
- 금융투자협회 (신용잔고, 예탁금)
