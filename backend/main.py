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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def get_data_file():
    files = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))
    if files: return sorted(files)[-1]
    return os.path.join(BASE_DIR, "ram_price_backup_20260203_003807.json")

DATA_PATH = get_data_file()

@app.get("/")
async def root():
    return {"status": "ok", "message": "Seondori API Server", "endpoints": ["/api/market-data", "/api/ram-data"]}

class UpdateRequest(BaseModel):
    date: str
    time: str
    text: str

# ============================================
# [핵심 개선 1] 더 유연한 파싱 로직
# ============================================
def parse_price_data(price_text):
    """
    더 관대한 정규표현식으로 다양한 입력 형식 지원
    """
    prices = {}
    current_ram_type = None
    
    # 더 유연한 패턴들 (선택사항 많음)
    patterns = {
        'ddr5': [
            r'삼성\s+D5\s+(\d+G)[^\d]*([\d]+)[^\d]*-\s*([\d,\.]+)\s*원',  # 삼성 D5 16G 7200 - 100,000원
            r'D5\s+(\d+G)[^\d]*([\d]+)[^\d]*-\s*([\d,\.]+)\s*원',        # D5 16G 7200 - 100,000원
        ],
        'ddr4': [
            r'삼성\s+(\d+G)\s+PC4[^\d]*([\d]+)[^\d]*-\s*([\d,\.]+)\s*원', # 삼성 16G PC4-3200 - 80,000원
            r'(\d+G)\s+PC4[^\d]*([\d]+)[^\d]*-\s*([\d,\.]+)\s*원',       # 16G PC4-3200 - 80,000원
        ],
        'ddr3': [
            r'삼성\s+(\d+G)\s+PC3[^\d]*([\d]+)[^\d]*-\s*([\d,\.]+)\s*원', # 삼성 8G PC3-1600 - 50,000원
            r'(\d+G)\s+PC3[^\d]*([\d]+)[^\d]*-\s*([\d,\.]+)\s*원',       # 8G PC3-1600 - 50,000원
        ],
    }
    
    for line in price_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('*'): 
            continue
        
        # 데스크탑/노트북 구분
        if '데스크탑' in line: 
            current_ram_type = '데스크탑'
            continue
        if '노트북' in line: 
            current_ram_type = '노트북'
            continue
        
        # 각 패턴 시도
        for p_name, p_regex_list in patterns.items():
            for p_regex in p_regex_list:
                m = re.search(p_regex, line)
                if m:
                    try:
                        cap, spd, pr = m.groups()
                        
                        # 속도 표기법 결정
                        if '5' in p_name: 
                            suffix = f" {spd}MHz"
                        elif '4' in p_name: 
                            suffix = f" PC4-{spd}"
                        else: 
                            suffix = f" PC3-{spd}"
                        
                        # DDR 타입과 카테고리 결정
                        dtype = "DDR" + p_name[-1]
                        
                        # ✅ DDR 타입과 메모리 타입의 조합
                        if current_ram_type is None:
                            current_ram_type = '데스크탑'  # 기본값
                        
                        cat = f"{dtype.upper()} RAM ({current_ram_type})"
                        prod = f"삼성 {dtype.upper()} {cap}{suffix}"
                        
                        # 가격 정수 변환
                        price = int(pr.replace(',', '').replace('.', ''))
                        
                        if cat not in prices: 
                            prices[cat] = []
                        
                        prices[cat].append({
                            "product": prod, 
                            "price": price, 
                            "price_formatted": f"{price:,}원"
                        })
                        
                        break  # 매칭 성공하면 다른 패턴 시도 안 함
                    except Exception as e:
                        print(f"파싱 에러: {e}")
                        continue
    
    return prices

def format_chart_data(series):
    if series is None or series.empty: return []
    return [{"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in series.items()]

def get_period_str(period_option):
    if period_option == "5일": return "5d", "90m"
    if period_option == "1개월": return "1mo", "1d"
    if period_option == "6개월": return "6mo", "1d"
    return "1y", "1d"

@app.get("/api/market-data")
async def get_market_data(period: str = "1개월"):
    p, i = get_period_str(period)
    TICKERS = {
        "indices": {"^KS11": "🇰🇷 코스피", "^DJI": "🇺🇸 다우존스", "^GSPC": "🇺🇸 S&P 500", "^IXIC": "🇺🇸 나스닥"},
        "macro": {"CL=F": "🛢️ WTI 원유", "GC=F": "👑 금", "^VIX": "😱 VIX", "HG=F": "🏭 구리"},
        "forex": {"KRW=X": "🇰🇷 원/달러", "JPYKRW=X": "🇯🇵 원/엔 (100엔)", "DX-Y.NYB": "🌎 달러 인덱스"},
        "bonds": {"ZT=F": "🇺🇸 미국 2년", "^TNX": "🇺🇸 미국 10년"} 
    }
    all_symbols = [s for cat in TICKERS.values() for s in cat.keys()] + ["CNY=X"]

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
            if symbol == "JPYKRW=X": current *= 100; prev *= 100; hist = hist * 100
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
    if not os.path.exists(DATA_PATH): 
        return {"error": "No data file"}
    
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
                if p_name not in product_history: 
                    product_history[p_name] = []
                product_history[p_name].append({"date": date, "price": item['price']})

    return {
        "current": json_data.get("price_data", {}),
        "trends": product_history,
        "total_days": len(sorted_dates),
        "date_range": f"{sorted_dates[0]} ~ {sorted_dates[-1]}" if sorted_dates else ""
    }

# ============================================
# [핵심 개선 2] 데이터 누적 (병합) 로직
# ============================================
@app.post("/api/admin/update")
async def update_data(req: UpdateRequest):
    parsed = parse_price_data(req.text)
    if not parsed: 
        return {"status": "error", "message": "파싱 실패"}
    
    # 기존 파일 로드
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f: 
            full = json.load(f)
    
    # 히스토리에 추가 (새로운 시간점의 데이터)
    key = f"{req.date} {req.time}"
    full["price_history"][key] = parsed
    
    # ✅ [핵심] price_data 병합 (덮어쓰기 아님)
    # 기존 데이터에 새 데이터를 병합
    for category, items in parsed.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []
        
        # 같은 제품명이 있으면 가격 업데이트, 없으면 추가
        existing_products = {item['product']: idx for idx, item in enumerate(full["price_data"][category])}
        
        for new_item in items:
            prod_name = new_item['product']
            if prod_name in existing_products:
                # 기존 제품 업데이트
                idx = existing_products[prod_name]
                full["price_data"][category][idx] = new_item
            else:
                # 새 제품 추가
                full["price_data"][category].append(new_item)
    
    # 파일 저장
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
    return {
        "status": "success", 
        "count": sum(len(v) for v in parsed.values()),
        "total_categories": len(full["price_data"]),
        "message": f"✅ {req.date} {req.time} 데이터 저장됨"
    }

@app.get("/api/admin/download")
async def download():
    if os.path.exists(DATA_PATH):
        return FileResponse(DATA_PATH, filename=f"backup_{datetime.now().strftime('%Y%m%d')}.json")
    return {"error": "No file"}
