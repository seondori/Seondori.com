"""
네이버 카페 RAM 시세 자동 크롤러 (안정화 버전)
- iframe (cafe_main) 인식 오류 대응
- 파싱 로직 및 시간별 데이터 누적 보장
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
from selenium.common.exceptions import NoSuchFrameException, TimeoutException
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
# 파싱 함수
# ============================================
def parse_price_data(price_text):
    log("파싱 프로세스 시작")
    prices = {}
    current_category = None
    
    category_patterns = [(r'DDR5', 'DDR5 RAM'), (r'DDR4', 'DDR4 RAM'), (r'DDR3', 'DDR3 RAM')]
    product_patterns = [
        (r'삼성\s*(?:D5|DDR5)?\s*(\d+G)\s*(\d{4,5})[^\d]*([\d,\.]+)\s*원', 'DDR5'),
        (r'삼성\s*(\d+G)\s*(?:PC4|PC3)?[\s\-]*(\d{5})[^\d]*([\d,\.]+)\s*원', 'DDR4'),
        (r'삼성\s*(\d+G)\s*(\d{4,5})[^\d]*([\d,\.]+)\s*원', 'DDR4'),
    ]
    
    lines = price_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5: continue
        
        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                mem_use = " (노트북)" if "노트북" in line else " (데스크탑)"
                current_category = cat_name + mem_use
                break
        
        if not current_category: continue
            
        for pattern, ddr_type in product_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    capacity, speed, price_raw = match.groups()
                    price_val = re.sub(r'[^\d]', '', price_raw)
                    if not price_val: continue
                    price = int(price_val)
                    
                    is_d5 = 'D5' in line or 'DDR5' in ddr_type or 'DDR5' in current_category
                    prod_prefix = "삼성 DDR5" if is_d5 else "삼성 DDR4"
                    product_name = f"{prod_prefix} {capacity} {speed}"
                    if "노트북" in current_category: product_name += " (노트북)"
                    
                    if current_category not in prices: prices[current_category] = []
                    if not any(p['product'] == product_name for p in prices[current_category]):
                        prices[current_category].append({"product": product_name, "price": price, "price_formatted": f"{price:,}원"})
                    break
                except: continue
    
    log(f"최종 파싱 완료: {sum(len(v) for v in prices.values())}개 제품 발견")
    return prices

def get_data_file():
    files = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))
    return sorted(files)[-1] if files else os.path.join(BASE_DIR, f"ram_{datetime.now().strftime('%Y%m%d')}.json")

def save_data(parsed_data, date_str, time_str):
    data_path = get_data_file()
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f: full = json.load(f)
        except: pass

    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data
    
    for category, items in parsed_data.items():
        if category not in full["price_data"]: full["price_data"][category] = []
        current_prods = {p['product']: i for i, p in enumerate(full["price_data"][category])}
        for item in items:
            name = item['product']
            if name in current_prods: full["price_data"][category][current_prods[name]] = item
            else: full["price_data"][category].append(item)
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    log(f"✅ 데이터 저장 완료: {history_key}")
    return True

# ============================================
# 드라이버 및 안정화된 검색 로직
# ============================================
def setup_driver():
    options = Options()
    if os.environ.get('GITHUB_ACTIONS'):
        options.add_argument('--headless=new')  # 최신 헤드리스 모드
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
        
        # 검색어 입력
        search_box = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#topLayerQueryInput")))
        search_box.send_keys(SEARCH_KEYWORD + Keys.RETURN)
        time.sleep(3)
        
        # iframe 전환 시도 (실패 시 무시하고 진행)
        try:
            WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it("cafe_main"))
            log("iframe (cafe_main) 전환 성공")
        except:
            log("iframe 전환 건너뜀 (이미 모바일 버전이거나 구조가 다름)")

        # 게시글 목록 찾기
        articles = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.article, .article_title")))
        
        target_url = None
        for a in articles:
            if TARGET_TITLE_KEYWORD in a.text:
                target_url = a.get_attribute("href")
                log(f"목표 게시글 발견: {target_url}")
                break
        
        if not target_url: return None
        
        # 게시글 이동
        driver.get(target_url)
        time.sleep(3)
        
        # 게시글 본문 추출 (iframe 재전환 시도)
        try:
            driver.switch_to.default_content()
            WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it("cafe_main"))
        except:
            pass
            
        # 본문 텍스트 가져오기 (여러 셀렉터 시도)
        selectors = [".se-main-container", ".ArticleContentBox", "#postContent", "body"]
        for selector in selectors:
            try:
                content_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                text = content_element.text.strip()
                if len(text) > 100:
                    log(f"본문 추출 성공 (셀렉터: {selector})")
                    return text
            except:
                continue
        return None
    except Exception as e:
        log(f"상세 에러: {str(e)}", "ERROR")
        return None

def main():
    driver = setup_driver()
    try:
        if not load_cookies(driver): return False
        content = search_and_get_content(driver)
        if not content: return False
        
        parsed = parse_price_data(content)
        if not parsed: return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        h = datetime.now().hour
        slot = "10:00" if h < 12 else ("13:00" if h < 16 else "18:00")
        return save_data(parsed, today, slot)
    finally:
        driver.quit()

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
