"""
네이버 카페 RAM 시세 자동 크롤러 (보강 버전)
- 가격 포맷 유연화 (마침표, 쉼표, 공백 대응)
- 중복 데이터 발생 시에도 타임슬롯 기록 유지
"""

import os
import json
import time
import sys
import traceback
import re
import base64
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import glob

# ============================================
# 설정
# ============================================
CAFE_URL = "https://cafe.naver.com/joonggonara"
SEARCH_KEYWORD = "베스트코리아컴 BKC"
TARGET_TITLE_KEYWORD = "구입]채굴기"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)

# ============================================
# 핵심 수정: 파싱 로직 보강
# ============================================
def parse_price_data(price_text):
    log("파싱 프로세스 시작")
    prices = {}
    current_category = None
    
    # 1. 카테고리 감지 패턴 (DDR 타입)
    category_patterns = [
        (r'DDR5', 'DDR5 RAM'),
        (r'DDR4', 'DDR4 RAM'),
        (r'DDR3', 'DDR3 RAM'),
    ]
    
    # 2. 제품 추출 패턴 (가장 유연한 형태)
    # 패턴 설명: 삼성 + (용량) + (속도/클럭) + (기타문자들) + (가격) + 원
    product_patterns = [
        # 삼성 D5 16G 5600 ... 55.000원 또는 55,000원
        (r'삼성\s*(?:D5|DDR5)?\s*(\d+G)\s*(\d{4,5})[^\d]*([\d,\.]+)\s*원', 'DDR5'),
        # 삼성 8G PC4-25600 ... 20.000원
        (r'삼성\s*(\d+G)\s*(?:PC4|PC3)?[\s\-]*(\d{5})[^\d]*([\d,\.]+)\s*원', 'DDR4'),
        # 가장 일반적인 형태 (삼성 16G 3200)
        (r'삼성\s*(\d+G)\s*(\d{4,5})[^\d]*([\d,\.]+)\s*원', 'DDR4'),
    ]
    
    lines = price_text.split('\n')
    log(f"텍스트 데이터 분석 중... (총 {len(lines)}줄)")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5: continue
        
        # 카테고리 전환 확인
        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                mem_use = " (노트북)" if "노트북" in line else " (데스크탑)"
                current_category = cat_name + mem_use
                log(f"현재 카테고리 설정: {current_category}")
                break
        
        if not current_category: continue
            
        # 제품 정보 매칭
        for pattern, ddr_type in product_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    capacity, speed, price_raw = match.groups()
                    
                    # 가격 전처리: 숫자 외 모든 문자 제거 (마침표, 쉼표 대응)
                    price_val = re.sub(r'[^\d]', '', price_raw)
                    if not price_val: continue
                    price = int(price_val)
                    
                    # 제품명 포맷팅
                    is_d5 = 'D5' in line or 'DDR5' in ddr_type or 'DDR5' in current_category
                    prod_prefix = "삼성 DDR5" if is_d5 else "삼성 DDR4"
                    product_name = f"{prod_prefix} {capacity} {speed}"
                    
                    if "노트북" in current_category:
                        product_name += " (노트북)"
                    
                    if current_category not in prices:
                        prices[current_category] = []
                    
                    # 중복 방지
                    if not any(p['product'] == product_name for p in prices[current_category]):
                        prices[current_category].append({
                            "product": product_name,
                            "price": price,
                            "price_formatted": f"{price:,}원"
                        })
                        log(f"  -> 파싱 성공: {product_name} | {price:,}원")
                    break
                except: continue
    
    total = sum(len(v) for v in prices.values())
    log(f"최종 파싱 완료: {total}개 제품 발견")
    return prices

def get_data_file():
    files = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))
    if files:
        return sorted(files)[-1]
    return os.path.join(BASE_DIR, f"ram_{datetime.now().strftime('%Y%m%d')}.json")

def save_data(parsed_data, date_str, time_str):
    log(f"데이터 저장 시작: {date_str} {time_str}")
    data_path = get_data_file()
    
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                full = json.load(f)
        except:
            log("기존 데이터 로드 에러, 초기화 진행", "WARN")

    # 히스토리 기록 (값이 같아도 새 키로 저장)
    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data
    
    # 현재가 정보 업데이트
    for category, items in parsed_data.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []
        
        current_prods = {p['product']: i for i, p in enumerate(full["price_data"][category])}
        for item in items:
            name = item['product']
            if name in current_prods:
                full["price_data"][category][current_prods[name]] = item
            else:
                full["price_data"][category].append(item)
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
    log(f"✅ JSON 저장 완료: {data_path}")
    return True

# ============================================
# 크롤링 프로세스 (Selenium)
# ============================================
def setup_driver():
    options = Options()
    if os.environ.get('GITHUB_ACTIONS'):
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(options=options)

def load_cookies(driver):
    cookies_json = os.environ.get('NAVER_COOKIES')
    if not cookies_json: return False
    try:
        if cookies_json.startswith('base64:'):
            cookies_json = base64.b64decode(cookies_json[7:]).decode('utf-8')
        cookies = json.loads(cookies_json)
        driver.get("https://naver.com")
        time.sleep(2)
        for c in cookies:
            driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.naver.com', 'path': '/'})
        return True
    except: return False

def search_and_get_content(driver):
    try:
        driver.get(CAFE_URL)
        time.sleep(3)
        search = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#topLayerQueryInput")))
        search.send_keys(SEARCH_KEYWORD + Keys.RETURN)
        time.sleep(3)
        
        driver.switch_to.frame("cafe_main")
        articles = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.article")))
        
        target_url = None
        for a in articles:
            if TARGET_TITLE_KEYWORD in a.text:
                target_url = a.get_attribute("href")
                break
        
        if not target_url: return None
        
        driver.get(target_url)
        time.sleep(3)
        driver.switch_to.frame("cafe_main")
        
        # 텍스트 추출 (가장 확실한 방법)
        body = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        return body.text
    except:
        log(traceback.format_exc(), "ERROR")
        return None

def main():
    driver = setup_driver()
    try:
        if not load_cookies(driver):
            log("쿠키 로드 실패", "ERROR")
            return False
        
        content = search_and_get_content(driver)
        if not content:
            log("본문 획득 실패", "ERROR")
            return False
        
        parsed = parse_price_data(content)
        if not parsed:
            log("파싱 결과가 없습니다.", "ERROR")
            return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        # 현재 시간에 맞는 슬롯 결정
        h = datetime.now().hour
        slot = "10:00" if h < 12 else ("13:00" if h < 16 else "18:00")
        
        return save_data(parsed, today, slot)
    finally:
        driver.quit()

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
