import os
import json
import time
import sys
import traceback
import re
import base64
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import glob

# 설정 및 로그 함수는 기존과 동일...
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAFE_URL = "https://cafe.naver.com/joonggonara"
SEARCH_KEYWORD = "베스트코리아컴 BKC"
TARGET_TITLE_KEYWORD = "구입]채굴기"

def log(msg, level="INFO"):
    timestamp = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)

def parse_price_data(price_text):
    log("파싱 프로세스 시작")
    prices = {}
    current_category = None
    
    lines = price_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5: continue
        
        # 카테고리 감지 (데스크탑/노트북 명시적 구분)
        if "데스크탑" in line or "단가표" in line:
            use_type = " (데스크탑)"
        elif "노트북" in line:
            use_type = " (노트북)"
        else:
            use_type = None

        if "DDR5" in line: cat = "DDR5 RAM"
        elif "DDR4" in line: cat = "DDR4 RAM"
        elif "DDR3" in line: cat = "DDR3 RAM"
        else: cat = None

        if cat and use_type:
            current_category = cat + use_type
            log(f"카테고리 변경: {current_category}")

        if not current_category: continue

        # 제품 정보 매칭 (삼성 제품 대상)
        match = re.search(r'삼성\s*(?:D5|DDR5|PC4|PC3)?\s*(\d+G)\s*(\d{4,5})[^\d]*([\d,\.]+)\s*원', line)
        if match:
            capacity, speed, price_raw = match.groups()
            price = int(re.sub(r'[^\d]', '', price_raw))
            
            # 제품명 통일
            d_ver = "DDR5" if "DDR5" in current_category else "DDR4" if "DDR4" in current_category else "DDR3"
            product_name = f"삼성 {d_ver} {capacity} {speed}"
            if "노트북" in current_category: product_name += " (노트북)"
            
            if current_category not in prices: prices[current_category] = []
            if not any(p['product'] == product_name for p in prices[current_category]):
                prices[current_category].append({
                    "product": product_name,
                    "price": price,
                    "price_formatted": f"{price:,}원"
                })
    return prices

def get_current_time_slot():
    # ✅ 중요: GitHub Actions(UTC) 시간을 한국 시간(KST)으로 변환
    kst_now = datetime.now(timezone.utc) + timedelta(hours=9)
    hour = kst_now.hour
    
    if hour < 12: return "10:00"
    elif hour < 16: return "13:00"
    else: return "18:00"

def save_data(parsed_data, date_str, time_str):
    data_path = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))[-1]
    
    with open(data_path, "r", encoding="utf-8") as f:
        full = json.load(f)

    # 히스토리에 무조건 추가
    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data
    
    # 덮어쓰기 방지를 위해 기존 "YYYY-MM-DD" 형태의 키가 있다면 삭제 권장 (선택사항)
    # if date_str in full["price_history"]: del full["price_history"][date_str]

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    log(f"✅ 데이터 저장 완료: {history_key}")

# ... (main 함수 및 기타 Selenium 로직은 이전과 동일하지만, get_current_time_slot을 활용하도록 수정)
def main():
    driver = setup_driver() # 기존 설정 함수 호출
    try:
        # 1~6단계 생략 (쿠키 로드 및 본문 획득)
        # ...
        content = search_and_get_content(driver)
        if not content: return False
        
        parsed = parse_price_data(content)
        if not parsed: return False
        
        kst_now = datetime.now(timezone.utc) + timedelta(hours=9)
        today = kst_now.strftime("%Y-%m-%d")
        slot = get_current_time_slot()
        
        save_data(parsed, today, slot)
        return True
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
