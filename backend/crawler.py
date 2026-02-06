"""
네이버 카페 RAM 시세 자동 크롤러 (개선 버전)
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
import glob

NAVER_ID = os.environ.get('NAVER_ID')
NAVER_PW = os.environ.get('NAVER_PW')
CAFE_URL = "https://cafe.naver.com/joonggonara"
SEARCH_KEYWORD = "베스트코리아컴 BKC"
TARGET_TITLE_KEYWORD = "구입]채굴기"  # 더 짧게

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# [기존 parse_price_data, get_data_file, save_data 함수는 동일]

def setup_driver():
    """Selenium WebDriver 설정 (개선)"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=options)
    return driver


def naver_login(driver):
    """네이버 로그인 (Naver API 대신 자동화 불가로 수동 쿠키 사용 권장)"""
    print("🔐 네이버 로그인 시도...")
    
    # ⚠️ GitHub Actions 환경에서는 아래 방식이 작동하지 않을 수 있음
    # 더 나은 방식: 미리 로그인한 쿠키를 저장해두고 사용
    
    driver.get("https://nid.naver.com/nidlogin.login")
    time.sleep(2)
    
    try:
        # 아이디 입력 (명시적 WebDriverWait 사용)
        id_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "id"))
        )
        id_input.send_keys(NAVER_ID)
        time.sleep(0.5)
        
        # 비밀번호 입력
        pw_input = driver.find_element(By.ID, "pw")
        pw_input.send_keys(NAVER_PW)
        time.sleep(0.5)
        
        # 로그인 버튼 클릭
        login_btn = driver.find_element(By.ID, "log.login")
        login_btn.click()
        
        time.sleep(5)  # 로그인 처리 시간
        
        # 로그인 성공 확인 (쿠키 존재 확인)
        cookies = driver.get_cookies()
        has_nid_auth = any(c['name'] in ['NID_AUT', 'NID_SES'] for c in cookies)
        
        if has_nid_auth:
            print("✅ 로그인 성공!")
            return True
        else:
            print("❌ 로그인 실패 (쿠키 없음)")
            return False
            
    except Exception as e:
        print(f"❌ 로그인 중 오류: {e}")
        return False


def search_cafe_post(driver):
    """카페에서 최신 RAM 시세 글 검색 (개선)"""
    print("🔍 카페 글 검색 중...")
    
    driver.get(CAFE_URL)
    time.sleep(3)
    
    try:
        # 검색창 찾기
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='검색']"))
        )
        search_input.send_keys(SEARCH_KEYWORD)
        search_input.send_keys(Keys.RETURN)
        time.sleep(3)
        
        # iframe 전환
        driver.switch_to.frame("cafe_main")
        
        # 검색 결과에서 글 찾기 (더 관대한 조건)
        articles = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.article"))
        )
        
        for article in articles:
            title = article.text.strip()
            if TARGET_TITLE_KEYWORD in title:
                article_url = article.get_attribute("href")
                print(f"📄 찾은 글: {title}")
                
                # iframe 나가기
                driver.switch_to.default_content()
                return article_url
        
        print("❌ 해당 글을 찾을 수 없습니다")
        driver.switch_to.default_content()
        return None
        
    except Exception as e:
        print(f"❌ 글 검색 실패: {e}")
        try:
            driver.switch_to.default_content()
        except:
            pass
        return None


def get_article_content(driver, article_url):
    """게시글 내용 가져오기 (개선)"""
    print("📖 게시글 내용 가져오는 중...")
    
    driver.get(article_url)
    time.sleep(3)
    
    try:
        driver.switch_to.frame("cafe_main")
        
        # 여러 셀렉터 시도
        selectors = [
            ".se-main-container",
            "#postContent",
            ".article-body",
            "[class*='content']"
        ]
        
        for selector in selectors:
            try:
                content_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                content = content_element.text.strip()
                if content and len(content) > 50:
                    print(f"✅ 내용 가져옴 ({len(content)} 글자)")
                    driver.switch_to.default_content()
                    return content
            except:
                continue
        
        print("❌ 내용을 찾을 수 없습니다")
        driver.switch_to.default_content()
        return None
        
    except Exception as e:
        print(f"❌ 내용 가져오기 실패: {e}")
        try:
            driver.switch_to.default_content()
        except:
            pass
        return None


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
            print("⚠️ 로그인 실패 - GitHub Actions 환경에서는 추가 설정 필요")
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
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
