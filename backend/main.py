from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yfinance as yf
import json
import os
import glob
import re
import requests
import pandas as pd
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GITHUB_RAW = "https://raw.githubusercontent.com/seondori/Seondori.com/main/backend/"

def load_ram_data():
    try:
        url = GITHUB_RAW + "ram_price_backup_20260206.json"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"GitHub에서 RAM 데이터 로드 실패: {e}")
        return None

def load_dram_data():
    try:
        url = GITHUB_RAW + "dram_exchange_data.json"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"GitHub에서 DRAM 데이터 로드 실패: {e}")
        return None

@app.get("/")
async def root():
    return {"status": "ok", "message": "Seondori API Server", "endpoints": ["/api/market-data", "/api/ram-data"]}

class UpdateRequest(BaseModel):
    date: str
    time: str
    text: str

# ============================================
# [완전 재작성] 네이버 카페 글 형식 파싱
# ============================================
def parse_price_data(price_text):
    prices = {}
    current_category = None
    current_mem_type = "데스크탑"
    
    category_patterns = [
        (r'데스크탑\s*용?\s*DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR3', 'DDR3 RAM (데스크탑)'),
        (r'데스크탑\s+DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s+DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s+DDR3', 'DDR3 RAM (데스크탑)'),
        (r'노트북\s*용?\s*DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR3', 'DDR3 RAM (노트북)'),
        (r'노트북\s+DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s+DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s+DDR3', 'DDR3 RAM (노트북)'),
    ]
    
    product_patterns = [
        (r'삼성\s*D5\s*(\d+G)\s*[,\-]?\s*(\d{4,5})\s*(?:\[?\d*\]?)?\s*-\s*([\d,\.]+)\s*원', 'DDR5'),
        (r'삼성\s*(\d+G)\s*PC4[\s\-]*(\d{5})\s*(?:\[\d+mhz\])?\s*-\s*([\d,\.]+)\s*원', 'DDR4'),
        (r'삼성\s*(\d+G)\s*-?\s*(\d{5})\s*(?:\[\d+mhz\])?\s*-\s*([\d,\.]+)\s*원', 'DDR4'),
        (r'삼성\s*(\d+G)\s*PC3[\s\-]*(\d{5})\s*-?\s*([\d,\.]+)\s*원', 'DDR3'),
    ]
    
    lines = price_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                current_category = cat_name
                if '노트북' in cat_name:
                    current_mem_type = "노트북"
                else:
                    current_mem_type = "데스크탑"
                print(f"[카테고리 감지] {cat_name}")
                break
        
        if current_category is None:
            continue
            
        for pattern, ddr_type in product_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    capacity, speed, price_str = match.groups()
                    price_clean = price_str.replace(',', '')
                    if '.' in price_clean:
                        parts = price_clean.split('.')
                        if len(parts) == 2 and len(parts[1]) == 3:
                            price = int(parts[0]) * 1000
                        else:
                            price = int(float(price_clean))
                    else:
                        price = int(price_clean)
                    
                    if ddr_type == 'DDR5':
                        product_name = f"삼성 DDR5 {capacity} {speed}MHz"
                    elif ddr_type == 'DDR4':
                        product_name = f"삼성 DDR4 {capacity} PC4-{speed}"
                    else:
                        product_name = f"삼성 DDR3 {capacity} PC3-{speed}"
                    
                    if current_mem_type == "노트북":
                        product_name += " (노트북)"
                    
                    if current_category not in prices:
                        prices[current_category] = []
                    
                    existing = [p['product'] for p in prices[current_category]]
                    if product_name not in existing:
                        prices[current_category].append({
                            "product": product_name,
                            "price": price,
                            "price_formatted": f"{price:,}원"
                        })
                        print(f"  [제품 추가] {product_name} = {price:,}원")
                    
                    break
                    
                except Exception as e:
                    print(f"[파싱 오류] {line}: {e}")
                    continue
    
    print(f"\n[파싱 완료] 총 {len(prices)}개 카테고리")
    for cat, items in prices.items():
        print(f"  - {cat}: {len(items)}개 제품")
    
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

@app.get("/api/dramexchange-data")
async def get_dramexchange_data():
    """GitHub에서 DRAM Exchange 데이터를 직접 읽어 반환"""
    data = load_dram_data()
    if data is None:
        return {"price_data": {}, "price_history": {}, "error": "데이터 로드 실패"}
    return data

@app.get("/api/ram-data")
async def get_ram_data():
    json_data = load_ram_data()
    if json_data is None:
        return {"error": "데이터 로드 실패"}
    
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

@app.post("/api/admin/update")
async def update_data(req: UpdateRequest):
    print(f"\n{'='*50}")
    print(f"[업데이트 요청] {req.date} {req.time}")
    print(f"[입력 텍스트 길이] {len(req.text)} 글자")
    print(f"{'='*50}")
    
    parsed = parse_price_data(req.text)
    
    if not parsed: 
        return {"status": "error", "message": "파싱 실패 - 인식된 제품이 없습니다"}
    
    full = load_ram_data() or {"price_data": {}, "price_history": {}}
    
    history_key = f"{req.date} {req.time}"
    full["price_history"][history_key] = parsed
    
    for category, items in parsed.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []
        
        existing_products = {item['product']: idx for idx, item in enumerate(full["price_data"][category])}
        
        for new_item in items:
            prod_name = new_item['product']
            if prod_name in existing_products:
                idx = existing_products[prod_name]
                full["price_data"][category][idx] = new_item
            else:
                full["price_data"][category].append(new_item)
    
    total_products = sum(len(v) for v in parsed.values())
    
    return {
        "status": "success", 
        "count": total_products,
        "categories": list(parsed.keys()),
        "total_categories": len(full["price_data"]),
        "message": f"✅ {req.date} 데이터 저장 완료 ({total_products}개 제품)"
    }

@app.get("/api/admin/download")
async def download():
    data = load_ram_data()
    if data:
        tmp_path = "/tmp/backup.json"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return FileResponse(tmp_path, filename=f"backup_{datetime.now().strftime('%Y%m%d')}.json")
    return {"error": "No file"}

@app.post("/api/admin/test-parse")
async def test_parse(req: UpdateRequest):
    parsed = parse_price_data(req.text)
    
    if not parsed:
        return {"status": "error", "message": "인식된 제품이 없습니다", "data": {}}
    
    return {
        "status": "success",
        "count": sum(len(v) for v in parsed.values()),
        "categories": list(parsed.keys()),
        "data": parsed
    }
