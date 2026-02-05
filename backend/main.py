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
    return os.path.join(BASE_DIR, "ram_price_backup.json")

DATA_PATH = get_data_file()

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
    """
    네이버 카페 RAM 시세 글 형식 파싱
    
    구조:
    - "데스크탑 DDR3", "데스크탑용 DDR5", "노트북용 DDR4" 등으로 카테고리 구분
    - "삼성 8G PC3 12800 - 3,000원" 형식으로 제품/가격 추출
    """
    prices = {}
    current_category = None
    current_mem_type = "데스크탑"  # 기본값
    
    # 카테고리 감지 패턴들
    # "13.데스크탑 DDR3", "16-1.데스크탑용 DDR5", "노트북용 DDR4" 등
    category_patterns = [
        # 데스크탑
        (r'데스크탑\s*용?\s*DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR3', 'DDR3 RAM (데스크탑)'),
        (r'데스크탑\s+DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s+DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s+DDR3', 'DDR3 RAM (데스크탑)'),
        # 노트북
        (r'노트북\s*용?\s*DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR3', 'DDR3 RAM (노트북)'),
        (r'노트북\s+DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s+DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s+DDR3', 'DDR3 RAM (노트북)'),
    ]
    
    # 제품 가격 패턴들 (다양한 형식 지원)
    # DDR5: "삼성 D5 16G - 5600 [44800] - 220,000원" 또는 "삼성 D5 8G- 5600 - 100,000원"
    # DDR4: "삼성 16G PC4 25600 [3200mhz] - 130.000원" 또는 "삼성 8G PC4 21300 - 49,000원"
    # DDR3: "삼성 8G PC3 12800 - 3,000원"
    
    product_patterns = [
        # DDR5: 삼성 D5 16G - 5600 [44800] - 220,000원  또는 삼성 D5 16G 5600 - 140,000원
        (r'삼성\s*D5\s*(\d+G)\s*[,\-]?\s*(\d{4,5})\s*(?:\[?\d*\]?)?\s*-\s*([\d,\.]+)\s*원', 'DDR5'),
        
        # DDR4 (PC4 있음): 삼성 16G PC4 25600 - 130,000원
        (r'삼성\s*(\d+G)\s*PC4[\s\-]*(\d{5})\s*(?:\[\d+mhz\])?\s*-\s*([\d,\.]+)\s*원', 'DDR4'),
        
        # DDR4 (PC4 없음, 노트북): 삼성 16G 21300[2666mhz] - 82,000원 또는 삼성 8G- 19200 - 40,000원
        (r'삼성\s*(\d+G)\s*-?\s*(\d{5})\s*(?:\[\d+mhz\])?\s*-\s*([\d,\.]+)\s*원', 'DDR4'),
        
        # DDR3: 삼성 8G PC3 12800 - 3,000원
        (r'삼성\s*(\d+G)\s*PC3[\s\-]*(\d{5})\s*-?\s*([\d,\.]+)\s*원', 'DDR3'),
    ]
    
    lines = price_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 1. 카테고리 감지
        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                current_category = cat_name
                # 데스크탑/노트북 타입도 업데이트
                if '노트북' in cat_name:
                    current_mem_type = "노트북"
                else:
                    current_mem_type = "데스크탑"
                print(f"[카테고리 감지] {cat_name}")
                break
        
        # 2. 제품 가격 추출
        if current_category is None:
            continue
            
        for pattern, ddr_type in product_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    capacity, speed, price_str = match.groups()
                    
                    # 가격 파싱 (3,000 / 3.000 / 3000 모두 지원)
                    price_clean = price_str.replace(',', '')
                    if '.' in price_clean:
                        # "3.000" → 3000, "130.000" → 130000
                        parts = price_clean.split('.')
                        if len(parts) == 2 and len(parts[1]) == 3:  # .000 형식
                            price = int(parts[0]) * 1000
                        else:
                            price = int(float(price_clean))
                    else:
                        price = int(price_clean)
                    
                    # 제품명 생성
                    if ddr_type == 'DDR5':
                        product_name = f"삼성 DDR5 {capacity} {speed}MHz"
                    elif ddr_type == 'DDR4':
                        product_name = f"삼성 DDR4 {capacity} PC4-{speed}"
                    else:  # DDR3
                        product_name = f"삼성 DDR3 {capacity} PC3-{speed}"
                    
                    # 노트북용이면 제품명에 표시
                    if current_mem_type == "노트북":
                        product_name += " (노트북)"
                    
                    # 카테고리에 추가
                    if current_category not in prices:
                        prices[current_category] = []
                    
                    # 중복 체크
                    existing = [p['product'] for p in prices[current_category]]
                    if product_name not in existing:
                        prices[current_category].append({
                            "product": product_name,
                            "price": price,
                            "price_formatted": f"{price:,}원"
                        })
                        print(f"  [제품 추가] {product_name} = {price:,}원")
                    
                    break  # 매칭 성공하면 다른 패턴 시도 안 함
                    
                except Exception as e:
                    print(f"[파싱 오류] {line}: {e}")
                    continue
    
    # 결과 요약
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
# [개선] 데이터 업데이트 with 상세 로그
# ============================================
@app.post("/api/admin/update")
async def update_data(req: UpdateRequest):
    print(f"\n{'='*50}")
    print(f"[업데이트 요청] {req.date} {req.time}")
    print(f"[입력 텍스트 길이] {len(req.text)} 글자")
    print(f"{'='*50}")
    
    parsed = parse_price_data(req.text)
    
    if not parsed: 
        return {"status": "error", "message": "파싱 실패 - 인식된 제품이 없습니다"}
    
    # 기존 파일 로드
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f: 
            full = json.load(f)
    
    # 히스토리에 추가 (날짜만 사용, 시간은 같은 날 여러번 업데이트 시 덮어쓰기)
    history_key = req.date  # "2026-02-04" 형식
    full["price_history"][history_key] = parsed
    
    # price_data 병합 (기존 데이터 유지 + 새 데이터 추가/업데이트)
    for category, items in parsed.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []
        
        # 기존 제품 목록
        existing_products = {item['product']: idx for idx, item in enumerate(full["price_data"][category])}
        
        for new_item in items:
            prod_name = new_item['product']
            if prod_name in existing_products:
                # 기존 제품 가격 업데이트
                idx = existing_products[prod_name]
                full["price_data"][category][idx] = new_item
            else:
                # 새 제품 추가
                full["price_data"][category].append(new_item)
    
    # 파일 저장
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
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
    if os.path.exists(DATA_PATH):
        return FileResponse(DATA_PATH, filename=f"backup_{datetime.now().strftime('%Y%m%d')}.json")
    return {"error": "No file"}
<<<<<<< HEAD
=======
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
    return os.path.join(BASE_DIR, "ram_price_backup.json")

DATA_PATH = get_data_file()

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
    """
    네이버 카페 RAM 시세 글 형식 파싱
    
    구조:
    - "데스크탑 DDR3", "데스크탑용 DDR5", "노트북용 DDR4" 등으로 카테고리 구분
    - "삼성 8G PC3 12800 - 3,000원" 형식으로 제품/가격 추출
    """
    prices = {}
    current_category = None
    current_mem_type = "데스크탑"  # 기본값
    
    # 카테고리 감지 패턴들
    # "13.데스크탑 DDR3", "16-1.데스크탑용 DDR5", "노트북용 DDR4" 등
    category_patterns = [
        # 데스크탑
        (r'데스크탑\s*용?\s*DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR3', 'DDR3 RAM (데스크탑)'),
        (r'데스크탑\s+DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s+DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s+DDR3', 'DDR3 RAM (데스크탑)'),
        # 노트북
        (r'노트북\s*용?\s*DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR3', 'DDR3 RAM (노트북)'),
        (r'노트북\s+DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s+DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s+DDR3', 'DDR3 RAM (노트북)'),
    ]
    
    # 제품 가격 패턴들 (다양한 형식 지원)
    # DDR5: "삼성 D5 16G - 5600 [44800] - 220,000원" 또는 "삼성 D5 8G- 5600 - 100,000원"
    # DDR4: "삼성 16G PC4 25600 [3200mhz] - 130.000원" 또는 "삼성 8G PC4 21300 - 49,000원"
    # DDR3: "삼성 8G PC3 12800 - 3,000원"
    
    product_patterns = [
        # DDR5: 삼성 D5 16G - 5600 [44800] - 220,000원  또는 삼성 D5 16G 5600 - 140,000원
        (r'삼성\s*D5\s*(\d+G)\s*[,\-]?\s*(\d{4,5})\s*(?:\[?\d*\]?)?\s*-\s*([\d,\.]+)\s*원', 'DDR5'),
        
        # DDR4 (PC4 있음): 삼성 16G PC4 25600 - 130,000원
        (r'삼성\s*(\d+G)\s*PC4[\s\-]*(\d{5})\s*(?:\[\d+mhz\])?\s*-\s*([\d,\.]+)\s*원', 'DDR4'),
        
        # DDR4 (PC4 없음, 노트북): 삼성 16G 21300[2666mhz] - 82,000원 또는 삼성 8G- 19200 - 40,000원
        (r'삼성\s*(\d+G)\s*-?\s*(\d{5})\s*(?:\[\d+mhz\])?\s*-\s*([\d,\.]+)\s*원', 'DDR4'),
        
        # DDR3: 삼성 8G PC3 12800 - 3,000원
        (r'삼성\s*(\d+G)\s*PC3[\s\-]*(\d{5})\s*-?\s*([\d,\.]+)\s*원', 'DDR3'),
    ]
    
    lines = price_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 1. 카테고리 감지
        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                current_category = cat_name
                # 데스크탑/노트북 타입도 업데이트
                if '노트북' in cat_name:
                    current_mem_type = "노트북"
                else:
                    current_mem_type = "데스크탑"
                print(f"[카테고리 감지] {cat_name}")
                break
        
        # 2. 제품 가격 추출
        if current_category is None:
            continue
            
        for pattern, ddr_type in product_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    capacity, speed, price_str = match.groups()
                    
                    # 가격 파싱 (3,000 / 3.000 / 3000 모두 지원)
                    price_clean = price_str.replace(',', '')
                    if '.' in price_clean:
                        # "3.000" → 3000, "130.000" → 130000
                        parts = price_clean.split('.')
                        if len(parts) == 2 and len(parts[1]) == 3:  # .000 형식
                            price = int(parts[0]) * 1000
                        else:
                            price = int(float(price_clean))
                    else:
                        price = int(price_clean)
                    
                    # 제품명 생성
                    if ddr_type == 'DDR5':
                        product_name = f"삼성 DDR5 {capacity} {speed}MHz"
                    elif ddr_type == 'DDR4':
                        product_name = f"삼성 DDR4 {capacity} PC4-{speed}"
                    else:  # DDR3
                        product_name = f"삼성 DDR3 {capacity} PC3-{speed}"
                    
                    # 노트북용이면 제품명에 표시
                    if current_mem_type == "노트북":
                        product_name += " (노트북)"
                    
                    # 카테고리에 추가
                    if current_category not in prices:
                        prices[current_category] = []
                    
                    # 중복 체크
                    existing = [p['product'] for p in prices[current_category]]
                    if product_name not in existing:
                        prices[current_category].append({
                            "product": product_name,
                            "price": price,
                            "price_formatted": f"{price:,}원"
                        })
                        print(f"  [제품 추가] {product_name} = {price:,}원")
                    
                    break  # 매칭 성공하면 다른 패턴 시도 안 함
                    
                except Exception as e:
                    print(f"[파싱 오류] {line}: {e}")
                    continue
    
    # 결과 요약
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
# [개선] 데이터 업데이트 with 상세 로그
# ============================================
@app.post("/api/admin/update")
async def update_data(req: UpdateRequest):
    print(f"\n{'='*50}")
    print(f"[업데이트 요청] {req.date} {req.time}")
    print(f"[입력 텍스트 길이] {len(req.text)} 글자")
    print(f"{'='*50}")
    
    parsed = parse_price_data(req.text)
    
    if not parsed: 
        return {"status": "error", "message": "파싱 실패 - 인식된 제품이 없습니다"}
    
    # 기존 파일 로드
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f: 
            full = json.load(f)
    
    # 히스토리에 추가 (날짜만 사용, 시간은 같은 날 여러번 업데이트 시 덮어쓰기)
    history_key = req.date  # "2026-02-04" 형식
    full["price_history"][history_key] = parsed
    
    # price_data 병합 (기존 데이터 유지 + 새 데이터 추가/업데이트)
    for category, items in parsed.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []
        
        # 기존 제품 목록
        existing_products = {item['product']: idx for idx, item in enumerate(full["price_data"][category])}
        
        for new_item in items:
            prod_name = new_item['product']
            if prod_name in existing_products:
                # 기존 제품 가격 업데이트
                idx = existing_products[prod_name]
                full["price_data"][category][idx] = new_item
            else:
                # 새 제품 추가
                full["price_data"][category].append(new_item)
    
    # 파일 저장
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
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
    if os.path.exists(DATA_PATH):
        return FileResponse(DATA_PATH, filename=f"backup_{datetime.now().strftime('%Y%m%d')}.json")
    return {"error": "No file"}
>>>>>>> b956001 (App.jsx 업데이트 - 모바일 반응형 및 탭순서 변경)

# ============================================
# [추가] 파싱 테스트 엔드포인트
# ============================================
@app.post("/api/admin/test-parse")
async def test_parse(req: UpdateRequest):
    """파싱 결과만 미리보기 (저장 안 함)"""
    parsed = parse_price_data(req.text)
    
    if not parsed:
        return {"status": "error", "message": "인식된 제품이 없습니다", "data": {}}
    
    return {
        "status": "success",
        "count": sum(len(v) for v in parsed.values()),
        "categories": list(parsed.keys()),
        "data": parsed
<<<<<<< HEAD
    }
=======
    }
>>>>>>> b956001 (App.jsx 업데이트 - 모바일 반응형 및 탭순서 변경)
