#!/usr/bin/env python3
"""
한미 시장 Daily 대시보드 — 데이터 자동 수집 스크립트
GitHub Actions에서 하루 2번 실행 (오후4시 KST, 오전7시 KST)
"""
import json, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
# 주말이면 마지막 거래일(금요일)로 보정
weekday = NOW.weekday()  # 0=월 ... 6=일
if weekday == 5:  # 토요일
    NOW = NOW - timedelta(days=1)
elif weekday == 6:  # 일요일
    NOW = NOW - timedelta(days=2)
TODAY = NOW.strftime("%Y-%m-%d")
DATA_PATH = "data/market.json"


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [WARN] {url} -> {e}")
        return None


def yahoo(symbol, rng="1mo", interval="1d"):
    """Yahoo Finance OHLCV"""
    raw = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval={interval}")
    if not raw: return None
    try:
        r = raw["chart"]["result"][0]
        meta = r["meta"]
        ts = r["timestamp"]
        closes = r["indicators"]["quote"][0]["close"]
        dates, cl = [], []
        for i, t in enumerate(ts):
            c = closes[i]
            if c is not None:
                dates.append(datetime.fromtimestamp(t, tz=KST).strftime("%m-%d"))
                cl.append(round(c, 2))
        cur = round(meta.get("regularMarketPrice", cl[-1] if cl else 0), 2)
        prev = round(meta.get("chartPreviousClose", meta.get("previousClose", 0)), 2)
        return {"cur": cur, "prev": prev, "dates": dates[-20:], "closes": cl[-20:]}
    except: return None


def load_existing():
    try:
        with open(DATA_PATH, "r") as f: return json.load(f)
    except: return {}


def pct(cur, prev):
    return round((cur - prev) / prev * 100, 2) if prev else 0


def build():
    print(f"[{NOW.strftime('%Y-%m-%d %H:%M KST')}] 수집 시작...")
    ex = load_existing()
    D = {"updated_at": NOW.isoformat(), "date": TODAY}

    # ── 1. 미국 시장 + 크로스마켓 ──
    tickers = {"sp500":"%5EGSPC","nasdaq":"%5EIXIC","vix":"%5EVIX","tnx":"%5ETNX","irx":"%5EIRX","krw":"KRW%3DX","dxy":"DX-Y.NYB"}
    for k, sym in tickers.items():
        print(f"  {k}...")
        r = yahoo(sym)
        if r: D[k] = r
        elif k in ex: D[k] = ex[k]

    # ── 2. KOSPI/KOSDAQ 지수 차트 ──
    for k, sym in [("kospi_chart","%5EKS11"),("kosdaq_chart","%5EKQ11")]:
        print(f"  {k}...")
        r = yahoo(sym)
        if r: D[k] = r
        elif k in ex: D[k] = ex[k]

    # ── 3. 시총 TOP 10 (한국) ──
    kr_kospi = {"삼성전자":"005930.KS","SK하이닉스":"000660.KS","삼성전자우":"005935.KS","현대자동차":"005380.KS","LG에너지솔루션":"373220.KS","삼성바이오로직스":"207940.KS","KB금융":"105560.KS","신한지주":"055550.KS","삼성SDI":"006400.KS","NAVER":"035420.KS"}
    kr_kosdaq = {"에코프로비엠":"247540.KS","알테오젠":"196170.KS","에코프로":"086520.KS","삼천당제약":"000250.KS","리노공업":"058470.KS","HLB":"028300.KS","리가켐바이오":"141080.KS","이오테크닉스":"039030.KS","알지노믹스":"476830.KS","HPSP":"403870.KS"}

    def fetch_stocks(stocks_dict, existing_stocks=None):
        # 기존 데이터에서 mcap/foreign 보존
        ex_map = {}
        if existing_stocks:
            for s in existing_stocks:
                ex_map[s["name"]] = s
        result = []
        for name, sym in stocks_dict.items():
            print(f"  {name}...")
            r = yahoo(sym, rng="5d", interval="1d")
            if r and len(r["closes"]) >= 2:
                cur, prev = r["closes"][-1], r["closes"][-2]
                entry = {"name": name, "price": f"{int(cur):,}", "chg": round(pct(cur, prev), 1)}
                # 기존 mcap/foreign 보존
                if name in ex_map:
                    if "mcap" in ex_map[name]: entry["mcap"] = ex_map[name]["mcap"]
                    if "foreign" in ex_map[name]: entry["foreign"] = ex_map[name]["foreign"]
                result.append(entry)
        return result

    ks = fetch_stocks(kr_kospi, ex.get("kospi_stocks"))
    if ks: D["kospi_stocks"] = ks
    kq = fetch_stocks(kr_kosdaq, ex.get("kosdaq_stocks"))
    if kq: D["kosdaq_stocks"] = kq

    # ── 4. 미국 시총 TOP 10 ──
    us = {"Apple":"AAPL","Microsoft":"MSFT","NVIDIA":"NVDA","Amazon":"AMZN","Alphabet":"GOOGL","Meta":"META","Berkshire":"BRK-B","Broadcom":"AVGO","Tesla":"TSLA","JPMorgan":"JPM"}
    us_stocks = []
    for name, sym in us.items():
        print(f"  {name}...")
        r = yahoo(sym, rng="5d", interval="1d")
        if r and len(r["closes"]) >= 2:
            cur, prev = r["closes"][-1], r["closes"][-2]
            us_stocks.append({"name": f"{name} ({sym})", "price": f"${cur:,.2f}", "chg": round(pct(cur, prev), 1)})
    if us_stocks:
        D["sp500_stocks"] = us_stocks
        D["nasdaq_stocks"] = us_stocks

    # ── 5. 섹터 등락 (섹터 ETF 프록시) ──
    kospi_etfs = {"전기전자":"091230.KS","건설":"117680.KS","금융":"091170.KS","운송장비":"091180.KS",
                  "화학":"117460.KS","제약":"253280.KS","음식료":"117460.KS"}
    sectors_k = []
    for name, sym in kospi_etfs.items():
        r = yahoo(sym, rng="5d", interval="1d")
        if r and len(r["closes"]) >= 2:
            cur, prev = r["closes"][-1], r["closes"][-2]
            sectors_k.append({"name": name, "pct": round(pct(cur, prev), 1)})
    if sectors_k:
        sectors_k.sort(key=lambda x: -x["pct"])
        D["sectors_kospi"] = sectors_k
    elif "sectors_kospi" in ex: D["sectors_kospi"] = ex["sectors_kospi"]

    # KOSDAQ 섹터 (대표종목 프록시)
    kq_proxies = {"IT/반도체":["039030.KS","058470.KS"],"바이오":["196170.KS","028300.KS"],"2차전지":["086520.KS","247540.KS"],"게임/엔터":["263750.KS","035720.KS"],"기계/장비":["257720.KS"]}
    sectors_q = []
    for name, syms in kq_proxies.items():
        pcts = []
        for sym in syms:
            r = yahoo(sym, rng="5d", interval="1d")
            if r and len(r["closes"]) >= 2:
                cur, prev = r["closes"][-1], r["closes"][-2]
                pcts.append(pct(cur, prev))
        sectors_q.append({"name": name, "pct": round(sum(pcts)/len(pcts), 1) if pcts else 0})
    sectors_q.sort(key=lambda x: -x["pct"])
    D["sectors_kosdaq"] = sectors_q

    # ── 6. 거래대금/외국인/신용 (기존 데이터 유지 + 누적) ──
    for key in ["trading_daily","foreign","deposit_weekly","credit","short_kospi","short_kosdaq","top_sector_foreign"]:
        if key in ex: D[key] = ex[key]
        elif key == "credit":
            D[key] = {"kospi":"—","kospi_chg":"업데이트 필요","kosdaq":"—","kosdaq_chg":"업데이트 필요","ratio":"—","deposit":"—","deposit_chg":"업데이트 필요"}
        elif key in ("trading_daily","foreign"):
            D[key] = {"dates":[],"kospi":[],"kosdaq":[]}

    # ── 8. 주간(5영업일) 누적 데이터 자동 계산 ──
    print("  주간 누적 계산...")
    weekly = {}

    # 지수 주간 등락
    for key in ["kospi_chart","kosdaq_chart","sp500","nasdaq","vix","krw","dxy","tnx"]:
        d = D.get(key)
        if d and len(d.get("closes",[])) >= 5:
            c = d["closes"]
            cur, w_ago = c[-1], c[-5]
            weekly[key] = {"cur": cur, "w_ago": w_ago, "chg_pct": round(pct(cur, w_ago), 2)}

    # 종목 주간 등락 (1mo 데이터에서 -5일 vs 현재)
    def weekly_stocks(stocks_dict, label):
        result = []
        for name, sym in stocks_dict.items():
            r = D.get(label, [])  # 이미 수집된 daily 데이터 사용
            # daily에서는 5일치만 있으므로 1mo로 재계산
            rd = yahoo(sym, rng="1mo", interval="1d")
            if rd and len(rd["closes"]) >= 5:
                cur, w_ago = rd["closes"][-1], rd["closes"][-5]
                result.append({"name": name, "price": f"{int(cur):,}", "chg_w": round(pct(cur, w_ago), 1)})
        return result

    wk_kospi = weekly_stocks(kr_kospi, "kospi_stocks")
    if wk_kospi: weekly["kospi_stocks"] = wk_kospi
    wk_kosdaq = weekly_stocks(kr_kosdaq, "kosdaq_stocks")
    if wk_kosdaq: weekly["kosdaq_stocks"] = wk_kosdaq

    # 미국 종목 주간
    wk_us = []
    for name, sym in us.items():
        rd = yahoo(sym, rng="1mo", interval="1d")
        if rd and len(rd["closes"]) >= 5:
            cur, w_ago = rd["closes"][-1], rd["closes"][-5]
            wk_us.append({"name": f"{name} ({sym})", "price": f"${cur:,.2f}", "chg_w": round(pct(cur, w_ago), 1)})
    if wk_us:
        weekly["sp500_stocks"] = wk_us
        weekly["nasdaq_stocks"] = wk_us

    # 섹터 주간 등락 (ETF 프록시)
    wk_sectors_k = []
    for name, sym in kospi_etfs.items():
        rd = yahoo(sym, rng="1mo", interval="1d")
        if rd and len(rd["closes"]) >= 5:
            cur, w_ago = rd["closes"][-1], rd["closes"][-5]
            wk_sectors_k.append({"name": name, "pct": round(pct(cur, w_ago), 1)})
    if wk_sectors_k:
        wk_sectors_k.sort(key=lambda x: -x["pct"])
        weekly["sectors_kospi"] = wk_sectors_k

    # 기존 주간 수동 데이터 유지 (DART/수동 입력 데이터 보존)
    if "weekly" in ex:
        for k in ["sectors_kospi_full","sectors_kosdaq","top_sector_foreign","foreign_weekly",
                   "credit","credit_weekly","foreign_fri"]:
            if k in ex["weekly"]: weekly[k] = ex["weekly"][k]
        # 주간 종목 mcap/foreign_w 보존
        for skey in ["kospi_stocks","kosdaq_stocks"]:
            if skey in ex["weekly"]:
                ex_map = {s["name"]:s for s in ex["weekly"][skey]}
                if skey in weekly:
                    for s in weekly[skey]:
                        if s["name"] in ex_map:
                            for fk in ["mcap","foreign_w"]:
                                if fk in ex_map[s["name"]]: s[fk] = ex_map[s["name"]][fk]

    D["weekly"] = weekly

    return D


if __name__ == "__main__":
    D = build()
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=2)
    print(f"\n[완료] {D['date']} | S&P500: {D.get('sp500',{}).get('cur','N/A')} | VIX: {D.get('vix',{}).get('cur','N/A')} | KRW: {D.get('krw',{}).get('cur','N/A')}")
