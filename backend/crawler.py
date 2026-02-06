"""
네이버 카페 RAM 시세 자동 크롤러
- 중고나라 카페에서 RAM 시세 글을 자동으로 가져옴
- GitHub Actions에서 하루 3번 실행
"""

import os
import json
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import glob

# ============================================
# 설정
# ============================================
NAVER_ID = os.environ.get('NAVER_ID')
NAVER_PW = os.environ.get('NAVER_PW')
CAFE_URL = "https://cafe.naver.com/joonggonara"
SEARCH_KEYWORD = "베스트코리아컴 BKC"
TARGET_TITLE_KEYWORD = "구입]채굴기,채굴장,부품"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================
# 파싱 함수 (main.py와 동일)
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
                    
                    break
                except Exception as e:
                    continue
    
    return prices


def get_data_file():
    """최신 JSON 파일 경로 반환"""
    files = glob.glob(os.path.join(BASE_DIR, "ram_*.json"))
    if files:
        return sorted(files)[-1]
    return os.path.join(BASE_DIR, "ram_price_backup.json")


def save_data(parsed_data, date_str, time_str):
    """파싱된 데이터를 JSON 파일에 저장"""
    data_path = get_data_file()
    
    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            full = json.load(f)
    
    # 히스토리에 추가
    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data
    
    # price_data 업데이트
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
    
    # 저장
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 데이터 저장 완료: {history_key}")
    return True


def setup_driver():
    """Selenium WebDriver 설정"""
    options = Options()
    options.add_argument('--headless')  # 헤드리스 모드
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=options)
    return driver


def naver_login(driver):
    """네이버 로그인"""
    print("🔐 네이버 로그인 시작...")
    
    driver.get("https://nid.naver.com/nidlogin.login")
    time.sleep(2)
    
    # 아이디 입력 (JavaScript 사용 - 보안 키보드 우회)
    driver.execute_script(f"document.getElementById('id').value = '{NAVER_ID}'")
    time.sleep(0.5)
    
    # 비밀번호 입력
    driver.execute_script(f"document.getElementById('pw').value = '{NAVER_PW}'")
    time.sleep(0.5)
    
    # 로그인 버튼 클릭
    login_btn = driver.find_element(By.ID, "log.login")
    login_btn.click()
    
    time.sleep(3)
    
    # 로그인 성공 확인
    if "nid.naver.com" not in driver.current_url:
        print("✅ 로그인 성공!")
        return True
    else:
        print("❌ 로그인 실패")
        return False


def search_cafe_post(driver):
    """카페에서 최신 RAM 시세 글 검색"""
    print("🔍 카페 글 검색 중...")
    
    # 카페 메인 페이지 이동
    driver.get(CAFE_URL)
    time.sleep(3)
    
    # 검색창에 키워드 입력
    try:
        # iframe 처리 (네이버 카페는 iframe 사용)
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "topLayerQueryInput"))
        )
        search_input.clear()
        search_input.send_keys(SEARCH_KEYWORD)
        search_input.send_keys(Keys.RETURN)
        time.sleep(3)
        
    except Exception as e:
        print(f"검색 실패: {e}")
        return None
    
    # 검색 결과에서 첫 번째 글 클릭
    try:
        # iframe으로 전환
        driver.switch_to.frame("cafe_main")
        
        # 글 목록에서 타겟 제목 찾기
        articles = driver.find_elements(By.CSS_SELECTOR, ".article-board .board-list .inner_list a.article")
        
        for article in articles:
            title = article.text
            if TARGET_TITLE_KEYWORD in title:
                article_url = article.get_attribute("href")
                print(f"📄 찾은 글: {title}")
                return article_url
        
        print("❌ 해당 글을 찾을 수 없습니다")
        return None
        
    except Exception as e:
        print(f"글 검색 실패: {e}")
        return None


def get_article_content(driver, article_url):
    """게시글 내용 가져오기"""
    print("📖 게시글 내용 가져오는 중...")
    
    driver.get(article_url)
    time.sleep(3)
    
    try:
        # iframe으로 전환
        driver.switch_to.frame("cafe_main")
        
        # 본문 내용 가져오기
        content_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".se-main-container"))
        )
        
        content = content_element.text
        print(f"✅ 내용 가져옴 ({len(content)} 글자)")
        return content
        
    except Exception as e:
        print(f"내용 가져오기 실패: {e}")
        
        # 대체 셀렉터 시도
        try:
            content_element = driver.find_element(By.CSS_SELECTOR, "#postContent")
            return content_element.text
        except:
            pass
        
        return None


def get_current_time_slot():
    """현재 시간에 맞는 타임슬롯 반환"""
    hour = datetime.now().hour
    
    if hour < 12:
        return "10:00"
    elif hour < 16:
        return "13:00"
    else:
        return "18:00"


def main():
    """메인 실행 함수"""
    print("=" * 50)
    print("🚀 RAM 시세 자동 크롤러 시작")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    if not NAVER_ID or not NAVER_PW:
        print("❌ 환경변수 NAVER_ID, NAVER_PW가 설정되지 않았습니다")
        return False
    
    driver = None
    try:
        driver = setup_driver()
        
        # 1. 네이버 로그인
        if not naver_login(driver):
            return False
        
        # 2. 카페 글 검색
        article_url = search_cafe_post(driver)
        if not article_url:
            return False
        
        # 3. 글 내용 가져오기
        content = get_article_content(driver, article_url)
        if not content:
            return False
        
        # 4. 파싱
        parsed = parse_price_data(content)
        if not parsed:
            print("❌ 파싱 실패 - 인식된 제품 없음")
            return False
        
        print(f"✅ 파싱 완료: {sum(len(v) for v in parsed.values())}개 제품")
        
        # 5. 저장
        today = datetime.now().strftime("%Y-%m-%d")
        time_slot = get_current_time_slot()
        save_data(parsed, today, time_slot)
        
        print("=" * 50)
        print("🎉 크롤링 완료!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False
        
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
