"""
네이버 카페 RAM 시세 자동 크롤러 (Self-Hosted Runner용)
- GitHub Actions 환경변수 대신 로컬 Chrome 브라우저의 쿠키를 직접 사용
- Chrome에 네이버 로그인만 유지하면 쿠키 수동 갱신 불필요
- Windows 11 + Self-Hosted Runner 환경 기준
"""

import os
import json
import time
import sys
import traceback
import re
import glob
import shutil
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ============================================
# 설정
# ============================================
CAFE_URL = "https://cafe.naver.com/joonggonara"
SEARCH_KEYWORD = "베스트코리아컴 BKC"
TARGET_TITLE_KEYWORD = "구입]채굴기"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

# ============================================
# 로깅
# ============================================
def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{now}] [{level}] {msg}", flush=True)
    except UnicodeEncodeError:
        # Windows cp949에서 이모지 출력 실패 시
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(f"[{now}] [{level}] {safe_msg}", flush=True)

# ============================================
# Chrome 프로필 경로 찾기 (Windows)
# ============================================
def get_chrome_profile_path():
    # Self-hosted runner에서 서비스 계정으로 실행될 때를 위해 직접 지정
    direct_path = r"C:\Users\stellaaa\AppData\Local\Google\Chrome\User Data"
    if os.path.exists(direct_path):
        log(f"✅ Chrome 프로필 경로: {direct_path}")
        return direct_path

    # 기본 방식 (환경변수)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        local_app_data = os.path.expanduser("~") + "\\AppData\\Local"

    chrome_path = os.path.join(local_app_data, "Google", "Chrome", "User Data")

    if os.path.exists(chrome_path):
        log(f"✅ Chrome 프로필 경로: {chrome_path}")
        return chrome_path
    else:
        log(f"❌ Chrome 프로필 경로 없음: {chrome_path}", "ERROR")
        return None

# ============================================
# 파싱 함수 (기존과 동일)
# ============================================
def parse_price_data(price_text):
    log("파싱 시작")
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
        if not line:
            continue

        for pattern, cat_name in category_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                current_category = cat_name
                current_mem_type = "노트북" if '노트북' in cat_name else "데스크탑"
                log(f"카테고리 발견: {cat_name}")
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
                        price = int(parts[0]) * 1000 if len(parts[1]) == 3 else int(float(price_clean))
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
                        log(f"제품 파싱: {product_name} - {price:,}원")
                    break
                except Exception as e:
                    log(f"제품 파싱 오류: {line} - {str(e)}", "WARN")
                    continue

    total_items = sum(len(items) for items in prices.values())
    log(f"파싱 완료: {len(prices)} 카테고리, {total_items} 제품")
    return prices

# ============================================
# 데이터 저장 (기존과 동일)
# ============================================
def get_data_file():
    files = glob.glob(os.path.join(BASE_DIR, "ram_price_*.json"))
    # ram_new_*.json 제외
    files = [f for f in files if "ram_new_" not in f]
    if files:
        latest = sorted(files)[-1]
        log(f"기존 데이터 파일 사용: {latest}")
        return latest
    new_file = os.path.join(BASE_DIR, f"ram_price_junggo_{datetime.now(KST).strftime('%Y%m%d')}.json")
    log(f"새 데이터 파일 생성: {new_file}")
    return new_file


def save_data(parsed_data, date_str, time_str):
    log(f"데이터 저장 시작: {date_str} {time_str}")
    data_path = get_data_file()

    full = {"price_data": {}, "price_history": {}}
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                full = json.load(f)
            log(f"기존 데이터 로드 완료: {len(full.get('price_history', {}))} 히스토리")
        except Exception as e:
            log(f"기존 파일 로드 실패, 새로 생성: {str(e)}", "WARN")

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

    log(f"✅ 데이터 저장 완료: {history_key}")
    return True

# ============================================
# 드라이버 설정 (Chrome 프로필 사용)
# ============================================
import shutil

def setup_driver():
    log("Chrome 드라이버 설정 중...")
    options = Options()

    chrome_profile = get_chrome_profile_path()

    if chrome_profile:
        temp_profile = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "chrome_crawler_profile")
        if os.path.exists(temp_profile):
            shutil.rmtree(temp_profile, ignore_errors=True)

        os.makedirs(os.path.join(temp_profile, "Default"), exist_ok=True)
        for filename in ["Cookies", "Cookies-journal", "Login Data", "Web Data"]:
            src = os.path.join(chrome_profile, "Default", filename)
            dst = os.path.join(temp_profile, "Default", filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                log(f"  쿠키 파일 복사: {filename}")

        local_state = os.path.join(chrome_profile, "Local State")
        if os.path.exists(local_state):
            shutil.copy2(local_state, os.path.join(temp_profile, "Local State"))

        options.add_argument(r"--user-data-dir=C:\Users\stellaaa\AppData\Local\Google\Chrome\User Data")
        options.add_argument("--profile-directory=Profile 12")
        log("✅ Chrome 프로필 복사 완료")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    log("Chrome 드라이버 초기화 완료")
    return driver

# ============================================
# 로그인 확인
# ============================================
def verify_login(driver):
    """네이버 로그인 상태 확인"""
    log("로그인 상태 확인 중...")
    try:
        driver.get("https://naver.com")
        time.sleep(3)
        cookies = driver.get_cookies()

        naver_cookies = [c['name'] for c in cookies if 'naver.com' in c.get('domain', '')]
        auth_cookies = [c for c in cookies if c['name'] in ['NID_AUT', 'NID_SES']]

        log(f"네이버 쿠키: {len(naver_cookies)}개")

        if auth_cookies:
            log(f"✅ 로그인 확인됨: {[c['name'] for c in auth_cookies]}")
            return True
        else:
            log("❌ NID_AUT/NID_SES 쿠키 없음", "ERROR")
            log(f"현재 쿠키 목록: {naver_cookies}", "DEBUG")
            log("💡 Chrome에서 네이버에 로그인되어 있는지 확인해주세요", "ERROR")
            return False
    except Exception as e:
        log(f"로그인 확인 중 오류: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False

# ============================================
# 카페 검색 & 게시글 가져오기
# ============================================
def search_cafe_post(driver):
    log(f"카페 검색 시작: {SEARCH_KEYWORD}")
    try:
        driver.get(CAFE_URL)
        time.sleep(3)

        log("검색창 찾는 중...")
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#topLayerQueryInput"))
        )

        log(f"검색어 입력: {SEARCH_KEYWORD}")
        search_input.send_keys(SEARCH_KEYWORD)
        search_input.send_keys(Keys.RETURN)
        time.sleep(3)

        log("iframe 전환 중...")
        driver.switch_to.frame("cafe_main")

        log("게시글 목록 찾는 중...")
        articles = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.article"))
        )
        log(f"게시글 {len(articles)}개 발견")

        for article in articles:
            if TARGET_TITLE_KEYWORD in article.text:
                url = article.get_attribute("href")
                log(f"✅ 목표 게시글 발견: {url}")
                return url

        log(f"❌ '{TARGET_TITLE_KEYWORD}' 제목을 찾지 못함", "ERROR")
        return None

    except Exception as e:
        log(f"카페 검색 중 오류: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return None
    finally:
        try:
            driver.switch_to.default_content()
        except:
            pass


def get_article_content(driver, article_url):
    log(f"게시글 내용 가져오는 중: {article_url}")
    try:
        driver.get(article_url)
        time.sleep(3)

        log("iframe 전환 중...")
        driver.switch_to.frame("cafe_main")

        log("본문 찾는 중...")
        content_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".se-main-container"))
        )

        content = content_element.text.strip()
        log(f"✅ 본문 가져오기 완료: {len(content)} 글자")
        return content

    except Exception as e:
        log(f"게시글 내용 가져오기 실패: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return None
    finally:
        try:
            driver.switch_to.default_content()
        except:
            pass


def get_current_time_slot():
    hour = datetime.now(KST).hour
    if hour < 12:
        return "10:00"
    elif hour < 16:
        return "13:00"
    else:
        return "18:00"

# ============================================
# 메인
# ============================================
def main():
    now = datetime.now(KST)
    log("=" * 60)
    log("🚀 RAM 시세 크롤러 (Self-Hosted Runner / Chrome 프로필)")
    log(f"📅 KST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📂 작업 디렉토리: {BASE_DIR}")
    log(f"🐍 Python: {sys.version}")
    log(f"💻 OS: {sys.platform}")
    log("=" * 60)

    driver = None
    try:
        # 1. Chrome 프로필로 드라이버 시작 (로그인 세션 자동 사용)
        driver = setup_driver()

        # 2. 로그인 확인
        if not verify_login(driver):
            log("=" * 60, "ERROR")
            log("❌ 네이버 로그인이 안 되어 있습니다", "ERROR")
            log("💡 이 PC의 Chrome 브라우저에서 네이버에 로그인해주세요", "ERROR")
            log("💡 로그인 후 다시 실행하면 자동으로 쿠키를 사용합니다", "ERROR")
            log("=" * 60, "ERROR")
            return False

        # 3. 게시글 검색
        url = search_cafe_post(driver)
        if not url:
            log("❌ 게시글 검색 실패", "ERROR")
            return False

        # 4. 게시글 내용 가져오기
        content = get_article_content(driver, url)
        if not content:
            log("❌ 게시글 내용 가져오기 실패", "ERROR")
            return False

        # 5. 데이터 파싱
        parsed = parse_price_data(content)
        if not parsed:
            log("❌ 데이터 파싱 실패 (결과 없음)", "ERROR")
            return False

        # 6. 데이터 저장
        today = now.strftime("%Y-%m-%d")
        time_slot = get_current_time_slot()
        save_data(parsed, today, time_slot)

        log("=" * 60)
        log("✅ 크롤러 성공적으로 완료!")
        log("=" * 60)
        return True

    except Exception as e:
        log("=" * 60, "ERROR")
        log(f"❌ 오류 발생: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        log("=" * 60, "ERROR")
        return False
    finally:
        if driver:
            log("브라우저 종료 중...")
            driver.quit()
            log("브라우저 종료 완료")


if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    log(f"프로그램 종료: exit code {exit_code}")
    sys.exit(exit_code)
