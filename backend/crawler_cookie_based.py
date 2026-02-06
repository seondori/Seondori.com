"""
네이버 카페 RAM 시세 자동 크롤러 (쿠키 기반 로그인)
- 변경사항: 데이터가 이전과 같더라도 타임슬롯별로 무조건 저장하여 그래프 끊김 방지
"""

import os
import json
import time
import datetime
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

# ============================================
# 파싱 함수
# ============================================
def parse_price_data(price_text):
    """네이버 카페 RAM 시세 글 형식 파싱"""
    prices = {}
    current_category = None
    current_mem_type = "데스크탑"
    
    category_patterns = [
        (r'데스크탑\s*용?\s*DDR5', 'DDR5 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR4', 'DDR4 RAM (데스크탑)'),
        (r'데스크탑\s*용?\s*DDR3', 'DDR3 RAM (데스크탑)'),
        (r'노트북\s*용?\s*DDR5', 'DDR5 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR4', 'DDR4 RAM (노트북)'),
        (r'노트북\s*용?\s*DDR3', 'DDR3 RAM (노트북)'),
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
        if not line: continue
        
        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                current_category = cat_name
                current_mem_type = "노트북" if '노트북' in cat_name else "데스크탑"
                break
        
        if current_category is None: continue
            
        for pattern, ddr_type in product_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    capacity, speed, price_str = match.groups()
                    price_clean = price_str.replace(',', '')
                    if '.' in price_clean:
                        parts = price_clean.split('.')
                        price = int(parts[0]) * 1000 if len(parts[1]) == 3 else int(float(price_clean))
                    else:
                        price = int(price_clean)
                    
                    if ddr_type == 'DDR5': product_name = f"삼성 DDR5 {capacity} {speed}MHz"
                    elif ddr_type == 'DDR4': product_name = f"삼성 DDR4 {capacity} PC4-{speed}"
                    else: product_name = f"삼성 DDR3 {capacity} PC3-{speed}"
                    
                    if current_mem_type == "노트북": product_name += " (노트북)"
                    
                    if current_category not in prices: prices[current_category] = []
                    
                    existing = [p['product'] for p in prices[current_category]]
                    if product_name not in existing:
                        prices[current_category].append({
                            "product": product_name,
                            "price": price,
                            "price_formatted": f"{price:,}원"
                        })
                    break
                except: continue
    return prices

def get_data_file():
    """가장 최근의 ram_*.json 파일을 찾거나 새 파일명 생성"""
    files = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))
    if files:
        # 파일명 기준 정렬하여 가장 최신 파일 반환
        return sorted(files)[-1]
    # 파일이 하나도 없으면 오늘 날짜로 새 파일명 생성
    return os.path.join(BASE_DIR, f"ram_{datetime.now().strftime('%Y%m%d')}.json")

def save_data(parsed_data, date_str, time_str):
    """데이터가 중복되어도 타임슬롯을 추가하여 무조건 저장"""
    data_path = get_data_file()
    
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                full = json.load(f)
        except:
            print("⚠️ 기존 파일 로드 실패, 새로 생성합니다.")

    # 1. 시세 히스토리에 무조건 추가 (그래프용 점 찍기)
    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data
    
    # 2. 최신 시세 정보(현재가) 업데이트
    for category, items in parsed_data.items():
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
    
    # 3. 파일 저장 (수정된 데이터를 항상 기록)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 데이터 저장 완료: {history_key} (JSON 파일 갱신됨)")
    return True

# --- 이하 드라이버 설정 및 크롤링 로직 (동일) ---

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

def load_cookies_from_env():
    cookies_json = os.environ.get('NAVER_COOKIES')
    if not cookies_json: return None
    try:
        if cookies_json.startswith('base64:'):
            cookies_json = base64.b64decode(cookies_json[7:]).decode('utf-8')
        return json.loads(cookies_json)
    except: return None

def add_cookies_to_driver(driver, cookies):
    if not cookies: return False
    try:
        driver.get("https://naver.com")
        time.sleep(2)
        for cookie in cookies:
            try:
                cookie_dict = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.naver.com'),
                    'path': cookie.get('path', '/'),
                }
                driver.add_cookie(cookie_dict)
            except: continue
        return True
    except: return False

def verify_login(driver):
    driver.get("https://naver.com")
    time.sleep(2)
    return any(c['name'] in ['NID_AUT', 'NID_SES'] for c in driver.get_cookies())

def search_cafe_post(driver):
    driver.get(CAFE_URL)
    time.sleep(3)
    try:
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#topLayerQueryInput"))
        )
        search_input.send_keys(SEARCH_KEYWORD)
        search_input.send_keys(Keys.RETURN)
        time.sleep(3)
        driver.switch_to.frame("cafe_main")
        articles = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.article"))
        )
        for article in articles:
            if TARGET_TITLE_KEYWORD in article.text:
                return article.get_attribute("href")
        return None
    except: return None
    finally: driver.switch_to.default_content()

def get_article_content(driver, article_url):
    driver.get(article_url)
    time.sleep(3)
    try:
        driver.switch_to.frame("cafe_main")
        content_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".se-main-container"))
        )
        return content_element.text.strip()
    except: return None
    finally: driver.switch_to.default_content()

def get_current_time_slot():
    hour = datetime.now().hour
    if hour < 12: return "10:00"
    elif hour < 16: return "13:00"
    else: return "18:00"

def main():
    print(f"🚀 크롤러 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    driver = None
    try:
        driver = setup_driver()
        cookies = load_cookies_from_env() if os.environ.get('GITHUB_ACTIONS') else None
        if not cookies:
            with open(os.path.join(BASE_DIR, "naver_cookies.json"), "r") as f:
                cookies = json.load(f)
        
        add_cookies_to_driver(driver, cookies)
        if not verify_login(driver): return False
        
        url = search_cafe_post(driver)
        if not url: return False
        
        content = get_article_content(driver, url)
        if not content: return False
        
        parsed = parse_price_data(content)
        if not parsed: return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        time_slot = get_current_time_slot()
        save_data(parsed, today, time_slot)
        return True
    except Exception as e:
        print(f"❌ 에러: {e}")
        return False
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    exit(0 if main() else 1)
