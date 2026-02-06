"""
네이버 카페 RAM 시세 자동 크롤러 (쿠키 기반 로그인)
- 미리 저장된 쿠키를 사용해서 로그인
- GitHub Actions 환경에서도 안정적으로 작동
"""

import os
import json
import time
import re
import base64
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import glob

# ============================================
# 설정
# ============================================
CAFE_URL = "https://cafe.naver.com/joonggonara"
SEARCH_KEYWORD = "베스트코리아컴 BKC"
TARGET_TITLE_KEYWORD = "구입]채굴기"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================
# 파싱 함수 (기존과 동일)
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
    
    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data
    
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
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 데이터 저장 완료: {history_key}")
    return True


def setup_driver():
    """Selenium WebDriver 설정 (webdriver-manager 사용)"""
    options = Options()
    
    # GitHub Actions 환경 감지
    if os.environ.get('GITHUB_ACTIONS'):
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        print("🔍 GitHub Actions 환경 감지됨")
    
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    print("📥 webdriver-manager로 ChromeDriver 다운로드 중...")
    try:
        # webdriver-manager를 사용해서 현재 Chrome 버전과 맞는 ChromeDriver 자동 다운로드
        driver_path = ChromeDriverManager().install()
        print(f"✅ ChromeDriver 경로: {driver_path}")
        
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        print("✅ WebDriver 생성 성공")
        return driver
    except Exception as e:
        print(f"❌ WebDriver 생성 실패: {e}")
        raise


def load_cookies_from_env():
    """환경변수에서 쿠키 로드 (GitHub Actions)"""
    cookies_json = os.environ.get('NAVER_COOKIES')
    
    if not cookies_json:
        print("❌ NAVER_COOKIES 환경변수가 설정되지 않았습니다")
        return None
    
    try:
        # Base64로 인코딩된 경우 디코딩
        if cookies_json.startswith('base64:'):
            cookies_json = base64.b64decode(cookies_json[7:]).decode('utf-8')
        
        cookies = json.loads(cookies_json)
        print(f"✅ 쿠키 로드 완료: {len(cookies)}개 쿠키")
        return cookies
    except Exception as e:
        print(f"❌ 쿠키 파싱 실패: {e}")
        return None


def load_cookies_from_file(filepath):
    """파일에서 쿠키 로드 (로컬 테스트)"""
    if not os.path.exists(filepath):
        print(f"❌ 쿠키 파일을 찾을 수 없습니다: {filepath}")
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        print(f"✅ 쿠키 파일 로드 완료: {len(cookies)}개 쿠키")
        return cookies
    except Exception as e:
        print(f"❌ 쿠키 파일 파싱 실패: {e}")
        return None


def add_cookies_to_driver(driver, cookies):
    """드라이버에 쿠키 추가"""
    if not cookies:
        return False
    
    try:
        # 먼저 네이버 페이지에 방문해야 쿠키 설정 가능
        driver.get("https://naver.com")
        time.sleep(2)
        
        for cookie in cookies:
            try:
                # 필요한 필드만 추출
                cookie_dict = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.naver.com'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False),
                }
                
                # httpOnly나 sameSite 속성이 있으면 제거 (Selenium에서 설정 불가)
                driver.add_cookie(cookie_dict)
            except Exception as e:
                # 일부 쿠키 추가 실패는 무시
                continue
        
        print(f"✅ {len(cookies)}개의 쿠키를 드라이버에 추가")
        return True
    except Exception as e:
        print(f"❌ 쿠키 추가 실패: {e}")
        return False


def verify_login(driver):
    """로그인 상태 확인"""
    try:
        driver.get("https://naver.com")
        time.sleep(2)
        
        # 프로필 아이콘이나 로그인 상태 확인
        cookies = driver.get_cookies()
        has_nid_auth = any(c['name'] in ['NID_AUT', 'NID_SES'] for c in cookies)
        
        if has_nid_auth:
            print("✅ 로그인 상태 확인됨")
            return True
        else:
            print("❌ 로그인 상태 미확인 (NID_AUT/NID_SES 쿠키 없음)")
            return False
    except Exception as e:
        print(f"❌ 로그인 확인 실패: {e}")
        return False


def search_cafe_post(driver):
    """카페에서 최신 RAM 시세 글 검색"""
    print("🔍 카페 글 검색 중...")
    
    driver.get(CAFE_URL)
    time.sleep(3)
    
    try:
        # 검색창 찾기 (여러 방식 시도)
        search_selectors = [
            "input[placeholder*='검색']",
            "#topLayerQueryInput",
            "input[class*='search']",
            "input[type='text'][placeholder*='검색']"
        ]
        
        search_input = None
        for selector in search_selectors:
            try:
                search_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if search_input:
                    break
            except:
                continue
        
        if not search_input:
            print("❌ 검색창을 찾을 수 없습니다")
            return None
        
        search_input.send_keys(SEARCH_KEYWORD)
        search_input.send_keys(Keys.RETURN)
        time.sleep(3)
        
        # iframe 전환 시도
        try:
            driver.switch_to.frame("cafe_main")
        except:
            pass
        
        # 검색 결과에서 글 찾기
        articles = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.article, a[class*='article']"))
        )
        
        found_url = None
        for article in articles:
            title = article.text.strip()
            if TARGET_TITLE_KEYWORD in title:
                found_url = article.get_attribute("href")
                print(f"📄 찾은 글: {title}")
                break
        
        # iframe 나가기
        try:
            driver.switch_to.default_content()
        except:
            pass
        
        if not found_url:
            print("❌ 해당 글을 찾을 수 없습니다")
            return None
        
        return found_url
        
    except Exception as e:
        print(f"❌ 글 검색 실패: {e}")
        try:
            driver.switch_to.default_content()
        except:
            pass
        return None


def get_article_content(driver, article_url):
    """게시글 내용 가져오기"""
    print("📖 게시글 내용 가져오는 중...")
    
    driver.get(article_url)
    time.sleep(3)
    
    try:
        # iframe 전환 시도
        try:
            driver.switch_to.frame("cafe_main")
        except:
            pass
        
        # 여러 셀렉터 시도
        selectors = [
            ".se-main-container",
            "#postContent",
            ".article-body",
            "[class*='content']",
            ".se-component"
        ]
        
        content = None
        for selector in selectors:
            try:
                content_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                content = content_element.text.strip()
                if content and len(content) > 50:
                    print(f"✅ 내용 가져옴 ({len(content)} 글자)")
                    break
            except:
                continue
        
        # iframe 나가기
        try:
            driver.switch_to.default_content()
        except:
            pass
        
        if not content:
            print("❌ 내용을 찾을 수 없습니다")
            return None
        
        return content
        
    except Exception as e:
        print(f"❌ 내용 가져오기 실패: {e}")
        try:
            driver.switch_to.default_content()
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
    print("=" * 60)
    print("🚀 RAM 시세 자동 크롤러 (쿠키 기반)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    driver = None
    try:
        driver = setup_driver()
        
        # 1. 쿠키 로드
        print("\n📥 쿠키 로드 중...")
        cookies = None
        
        # GitHub Actions 환경에서는 환경변수에서 로드
        if os.environ.get('GITHUB_ACTIONS'):
            cookies = load_cookies_from_env()
        else:
            # 로컬 환경에서는 파일에서 로드
            cookies = load_cookies_from_file(os.path.join(BASE_DIR, "naver_cookies.json"))
        
        if not cookies:
            print("❌ 쿠키를 로드할 수 없습니다")
            return False
        
        # 2. 드라이버에 쿠키 추가
        if not add_cookies_to_driver(driver, cookies):
            return False
        
        # 3. 로그인 상태 확인
        if not verify_login(driver):
            print("❌ 로그인 상태를 확인할 수 없습니다")
            return False
        
        # 4. 카페 글 검색
        article_url = search_cafe_post(driver)
        if not article_url:
            return False
        
        # 5. 글 내용 가져오기
        content = get_article_content(driver, article_url)
        if not content:
            return False
        
        # 6. 파싱
        parsed = parse_price_data(content)
        if not parsed:
            print("❌ 파싱 실패 - 인식된 제품 없음")
            return False
        
        print(f"✅ 파싱 완료: {sum(len(v) for v in parsed.values())}개 제품")
        
        # 7. 저장
        today = datetime.now().strftime("%Y-%m-%d")
        time_slot = get_current_time_slot()
        save_data(parsed, today, time_slot)
        
        print("=" * 60)
        print("🎉 크롤링 완료!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
