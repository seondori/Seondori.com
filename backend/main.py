from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yfinance as yf
import json
import os
import glob
import re
import pandas as pd
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# [수정] 파일 경로 안전하게 찾기 (실행 위치 에러 방지)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def get_data_file():
    files = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))
    if files: return sorted(files)[-1]
    return os.path.join(BASE_DIR, "ram_price_backup_20260203_003807.json")

DATA_PATH = get_data_file()

# --- 기존 코드 (유지) ---
TICKERS = {
    "indices": {"^KS11": "🇰🇷 코스피", "^DJI": "🇺🇸 다우존스", "^GSPC": "🇺🇸 S&P 500", "^IXIC": "🇺🇸 나스닥"},
    "macro": {"CL=F": "🛢️ WTI 원유", "GC=F": "👑 금", "^VIX": "😱 VIX", "HG=F": "🏭 구리"},
    "forex": {"KRW=X": "🇰🇷 원/달러", "JPYKRW=X": "🇯🇵 원/엔 (100엔)", "DX-Y.NYB": "🌎 달러 인덱스"},
    "bonds": {"ZT=F": "🇺🇸 미국 2년", "^TNX": "🇺🇸 미국 10년"} 
}

def get_period_str(period_option):
    if period_option == "5일": return "5d", "90m"
    if period_option == "1개월": return "1mo", "1d"
    if period_option == "6개월": return "6mo", "1d"
    return "1y", "1d"

@app.get("/api/market-data")
async def get_market_data(period: str = "1개월"):
    p, i = get_period_str(period)
    all_symbols = []
    for cat in TICKERS.values():
        all_symbols.extend(cat.keys())
    all_symbols.append("CNY=X")

    try:
        data = yf.download(all_symbols, period=p, interval=i, progress=False, group_by='ticker')
    except Exception as e:
        return {"error": str(e)}

    result = {}
    def process_ticker(symbol, name):
        try:
            df = data[symbol] if symbol in data else data
            if 'Close' not in df.columns: return None
            hist = df['Close'].dropna()
            if hist.empty: return None
            current = float(hist.iloc[-1])
            prev = float(hist.iloc[-2]) if len(hist) > 1 else current
            if symbol == "JPYKRW=X": 
                current *= 100; prev *= 100; hist = hist * 100
            chart_data = [{"time": t.strftime('%Y-%m-%d %H:%M'), "value": float(v)} for t, v in hist.items()]
            return {"name": name, "current": current, "delta": current - prev, "pct": ((current - prev) / prev) * 100 if prev != 0 else 0, "chart": chart_data}
        except: return None

    for cat_name, symbols in TICKERS.items():
        result[cat_name] = []
        for sym, name in symbols.items():
            info = process_ticker(sym, name)
            if info: result[cat_name].append(info)

    try:
        krw = data["KRW=X"]['Close'].dropna(); cny = data["CNY=X"]['Close'].dropna()
        combined = pd.DataFrame({"KRW": krw, "CNY": cny}).dropna()
        cny_krw_hist = combined["KRW"] / combined["CNY"]
        current = float(cny_krw_hist.iloc[-1])
        prev = float(cny_krw_hist.iloc[-2])
        chart_data = [{"time": t.strftime('%Y-%m-%d'), "value": float(v)} for t, v in cny_krw_hist.items()]
        result["forex"].insert(1, {"name": "🇨🇳 원/위안", "current": current, "delta": current - prev, "pct": ((current - prev) / prev) * 100, "chart": chart_data})
    except: pass
    return result

@app.get("/api/ram-data")
async def get_ram_data():
    if not os.path.exists(DATA_PATH): return {"error": "No data file"}
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    product_history = {}
    raw_history = json_data.get("price_history", {})
    sorted_dates = sorted(raw_history.keys())

    for date in sorted_dates:
        categories = raw_history[date]
        for cat, items in categories.items():
            for item in items:
                p_name = item['product']
                if p_name not in product_history: product_history[p_name] = []
                product_history[p_name].append({"date": date, "price": item['price']})

    # [중요] trends 키 사용
    return {
        "current": json_data.get("price_data", {}),
        "trends": product_history, 
        "total_days": len(sorted_dates),
        "date_range": f"{sorted_dates[0]} ~ {sorted_dates[-1]}" if sorted_dates else ""
    }

# --- [추가됨] 관리자 기능 ---
class UpdateRequest(BaseModel):
    date: str
    time: str
    text: str

def parse_price_data(price_text):
    prices = {}
    current_ram_type = None
    patterns = {
        'ddr5': r'삼성\s*D5\s*(\d+G)[^\d]*([\d]+)\s*[\[\(]?[\d,\.]*[\]\)]?\s*-\s*([\d,\.]+)\s*원',
        'ddr4': r'삼성\s*(\d+G)\s*PC4[- ]?([\d]+)\s*[\[\(]?[\d,\.]*[Mm]?[Hh]?[Zz]?[\]\)]?\s*-\s*([\d,\.]+)\s*원',
        'ddr3': r'삼성\s*(\d+G)\s*PC3[- ]?([\d]+)\s*-\s*([\d,\.]+)\s*원',
    }
    for line in price_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('*'): continue
        if '데스크탑' in line: current_ram_type = '데스크탑'; continue
        if '노트북' in line: current_ram_type = '노트북'; continue
        parts = line.split(',')
        for part in parts:
            try:
                for p_name, p_regex in patterns.items():
                    m = re.search(p_regex, part)
                    if m:
                        cap, spd, pr = m.groups()
                        dtype = "DDR" + p_name[-1]
                        if '5' in p_name: suffix = f" {spd}MHz"
                        elif '4' in p_name: suffix = f" PC4-{spd}"
                        else: suffix = f" PC3-{spd}"
                        cat = f"{dtype.upper()} RAM ({current_ram_type})"
                        prod = f"삼성 {dtype.upper()} {cap}{suffix}{' (노트북)' if current_ram_type == '노트북' else ''}"
                        price = int(pr.replace(',', '').replace('.', ''))
                        if cat not in prices: prices[cat] = []
                        prices[cat].append({"product": prod, "price": price, "price_formatted": f"{price:,}원"})
                        break
            except: continue
    return prices

@app.post("/api/admin/update")
async def update_data(req: UpdateRequest):
    parsed = parse_price_data(req.text)
    if not parsed: return {"status": "error", "message": "파싱 실패"}
    
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f: full = json.load(f)
    
    key = f"{req.date} {req.time}"
    full["price_history"][key] = parsed
    if sorted(full["price_history"].keys())[-1] == key: full["price_data"] = parsed
        
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    return {"status": "success", "count": sum(len(v) for v in parsed.values())}

@app.get("/api/admin/download")
async def download():
    if os.path.exists(DATA_PATH):
        return FileResponse(DATA_PATH, filename=f"backup_{datetime.now().strftime('%Y%m%d')}.json")
    return {"error": "No file"}