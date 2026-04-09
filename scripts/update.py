#!/usr/bin/env python3
"""
한미 시장 Daily 대시보드 — 데이터 자동 수집 스크립트
GitHub Actions에서 하루 2번 실행 (오후4시 KST, 오전7시 KST)
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d")

DATA_PATH = "data/market.json"


def fetch_json(url, timeout=15):
    """URL에서 JSON 데이터 가져오기"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [WARN] fetch failed: {url} -> {e}")
        return None


def yahoo_chart(symbol, rng="1mo", interval="1d"):
    """Yahoo Finance에서 OHLCV 데이터 가져오기"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval={interval}"
    raw = fetch_json(url)
    if not raw:
        return None
    try:
        result = raw["chart"]["result"][0]
        meta = result["meta"]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        volumes = result["indicators"]["quote"][0].get("volume", [])

        dates = []
        clean_closes = []
        clean_volumes = []
        for i, ts in enumerate(timestamps):
            dt = datetime.fromtimestamp(ts, tz=KST)
            c = closes[i]
            v = volumes[i] if i < len(volumes) else 0
            if c is not None:
                dates.append(dt.strftime("%m-%d"))
                clean_closes.append(round(c, 2))
                clean_volumes.append(v or 0)

        return {
            "symbol": symbol,
            "name": meta.get("shortName", symbol),
            "currency": meta.get("currency", ""),
            "current": round(meta.get("regularMarketPrice", clean_closes[-1] if clean_closes else 0), 2),
            "prev_close": round(meta.get("chartPreviousClose", meta.get("previousClose", 0)), 2),
            "dates": dates[-20:],
            "closes": clean_closes[-20:],
            "volumes": clean_volumes[-20:],
        }
    except (KeyError, IndexError) as e:
        print(f"  [WARN] parse failed for {symbol}: {e}")
        return None


def load_existing():
    """기존 데이터 로드 (없으면 빈 딕셔너리)"""
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def build_market_data():
    """전체 시장 데이터 수집"""
    print(f"[{NOW.strftime('%Y-%m-%d %H:%M KST')}] 데이터 수집 시작...")

    existing = load_existing()
    data = {"updated_at": NOW.isoformat(), "date": TODAY}

    # ── 1. 미국 시장 + 크로스마켓 (Yahoo Finance) ──
    tickers = {
        "sp500": "%5EGSPC",
        "nasdaq": "%5EIXIC",
        "vix": "%5EVIX",
        "tnx": "%5ETNX",
        "irx": "%5EIRX",
        "krw": "KRW%3DX",
        "dxy": "DX-Y.NYB",
    }

    for key, symbol in tickers.items():
        print(f"  Fetching {key} ({symbol})...")
        result = yahoo_chart(symbol)
        if result:
            data[key] = result
        elif key in existing:
            print(f"  -> 기존 데이터 유지: {key}")
            data[key] = existing[key]

    # ── 2. 한국 시장 (Yahoo Finance — KOSPI/KOSDAQ ETF 프록시) ──
    # KOSPI: ^KS11, KOSDAQ: ^KQ11
    for key, symbol in [("kospi_chart", "%5EKS11"), ("kosdaq_chart", "%5EKQ11")]:
        print(f"  Fetching {key} ({symbol})...")
        result = yahoo_chart(symbol)
        if result:
            data[key] = result
        elif key in existing:
            data[key] = existing[key]

    # ── 3. 한국 시총 상위 종목 (Yahoo Finance) ──
    kr_stocks = {
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "삼성전자우": "005935.KS",
        "현대자동차": "005380.KS", "LG에너지솔루션": "373220.KS",
        "삼성바이오로직스": "207940.KS", "KB금융": "105560.KS",
        "신한지주": "055550.KS", "삼성SDI": "006400.KS", "NAVER": "035420.KS",
    }
    kospi_stocks = []
    for name, symbol in kr_stocks.items():
        print(f"  Fetching {name} ({symbol})...")
        result = yahoo_chart(symbol, rng="5d", interval="1d")
        if result and len(result["closes"]) >= 2:
            cur = result["closes"][-1]
            prev = result["closes"][-2]
            chg_pct = round((cur - prev) / prev * 100, 1) if prev else 0
            kospi_stocks.append({
                "name": name,
                "price": f"{int(cur):,}",
                "chg": chg_pct,
                "mcap": "",  # 시총은 별도 소스 필요
            })
    if kospi_stocks:
        data["kospi_stocks"] = kospi_stocks

    # KOSDAQ 상위
    kq_stocks = {
        "카카오": "035720.KS", "에코프로": "086520.KS", "에코프로비엠": "247540.KS",
        "알테오젠": "196170.KS", "리노공업": "058470.KS",
        "HLB": "028300.KS", "리가켐바이오": "141080.KS",
        "이오테크닉스": "039030.KS", "펄어비스": "263750.KS", "실리콘투": "257720.KS",
    }
    kosdaq_stocks = []
    for name, symbol in kq_stocks.items():
        print(f"  Fetching {name} ({symbol})...")
        result = yahoo_chart(symbol, rng="5d", interval="1d")
        if result and len(result["closes"]) >= 2:
            cur = result["closes"][-1]
            prev = result["closes"][-2]
            chg_pct = round((cur - prev) / prev * 100, 1) if prev else 0
            kosdaq_stocks.append({
                "name": name,
                "price": f"{int(cur):,}",
                "chg": chg_pct,
                "mcap": "",
            })
    if kosdaq_stocks:
        data["kosdaq_stocks"] = kosdaq_stocks

    # ── 4. 미국 시총 상위 종목 ──
    us_stocks = {
        "Apple": "AAPL", "Microsoft": "MSFT", "NVIDIA": "NVDA",
        "Amazon": "AMZN", "Alphabet": "GOOGL", "Meta": "META",
        "Berkshire": "BRK-B", "Broadcom": "AVGO", "Tesla": "TSLA", "JPMorgan": "JPM",
    }
    sp500_stocks = []
    for name, symbol in us_stocks.items():
        print(f"  Fetching {name} ({symbol})...")
        result = yahoo_chart(symbol, rng="5d", interval="1d")
        if result and len(result["closes"]) >= 2:
            cur = result["closes"][-1]
            prev = result["closes"][-2]
            chg_pct = round((cur - prev) / prev * 100, 1) if prev else 0
            sp500_stocks.append({
                "name": f"{name} ({symbol})",
                "price": f"${cur:,.2f}",
                "chg": chg_pct,
            })
    if sp500_stocks:
        data["sp500_stocks"] = sp500_stocks
        data["nasdaq_stocks"] = sp500_stocks  # 대부분 겹침

    # ── 5. 거래대금/외국인 추이 (기존 데이터에 누적) ──
    # 기존 추이 데이터 유지 + 새 데이터 추가 가능 영역
    for key in ["trading_daily", "foreign", "deposit_weekly", "credit", "sectors_kospi", "sectors_kosdaq", "short_kospi", "short_kosdaq", "top_sector_foreign"]:
        if key in existing:
            data[key] = existing[key]

    return data


def save_data(data):
    """JSON 파일로 저장"""
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> 저장 완료: {DATA_PATH} ({len(json.dumps(data)):,} bytes)")


if __name__ == "__main__":
    data = build_market_data()
    save_data(data)
    print(f"\n[완료] {data['date']} 데이터 수집 완료!")
    print(f"  S&P500: {data.get('sp500', {}).get('current', 'N/A')}")
    print(f"  NASDAQ: {data.get('nasdaq', {}).get('current', 'N/A')}")
    print(f"  VIX:    {data.get('vix', {}).get('current', 'N/A')}")
    print(f"  KRW:    {data.get('krw', {}).get('current', 'N/A')}")
