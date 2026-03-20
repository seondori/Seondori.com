"""
다나와(Danawa) RAM 최저가 크롤러
- 기존 네이버 쇼핑 API 대체
- 파일명/데이터 형식은 기존 ram_new_*.json 구조 유지
"""

import os
import json
import sys
import traceback
import re
import time
import glob
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

# ============================================
# 검색 대상
# ============================================
TARGETS = [
    {
        "category": "DDR5-5600",
        "items": [
            {"query": "삼성전자 ddr5-5600 8gb", "label": "8GB"},
            {"query": "삼성전자 ddr5-5600 16gb", "label": "16GB"},
            {"query": "삼성전자 ddr5-5600 32gb", "label": "32GB"},
        ]
    },
    {
        "category": "DDR5-4800",
        "items": [
            {"query": "삼성전자 ddr5-4800 8gb", "label": "8GB"},
            {"query": "삼성전자 ddr5-4800 16gb", "label": "16GB"},
            {"query": "삼성전자 ddr5-4800 32gb", "label": "32GB"},
        ]
    },
]

def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

def setup_driver():
    log("Chrome 드라이버 설정 중...")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    log("Chrome 드라이버 초기화 완료")
    return driver

def search_danawa(driver, query):
    """다나와 검색 후 첫 번째 제품의 이름과 최저가 추출"""
    search_url = f"https://search.danawa.com/dsearch.php?query={query.replace(' ', '+')}"
    log(f"  검색: {query}")

    driver.get(search_url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".prod_main_info"))
        )
    except:
        log("  ⚠️ 로딩 대기 타임아웃, 추가 대기...", "WARN")
        time.sleep(3)

    # 방법 1: 구조화된 셀렉터
    try:
        first_product = driver.find_element(By.CSS_SELECTOR, ".prod_main_info")

        try:
            name_el = first_product.find_element(By.CSS_SELECTOR, ".prod_name a")
            product_name = name_el.text.strip()
        except:
            product_name = query

        try:
            price_el = first_product.find_element(By.CSS_SELECTOR, ".price_sect a strong")
            price_text = price_el.text.strip().replace(",", "").replace("원", "")
            price = int(price_text)
        except:
            try:
                price_el = first_product.find_element(By.CSS_SELECTOR, ".price_sect .price")
                price_text = price_el.text.strip().replace(",", "").replace("원", "")
                price = int(re.sub(r'[^\d]', '', price_text))
            except:
                price = None

        try:
            link_el = first_product.find_element(By.CSS_SELECTOR, ".prod_name a")
            product_link = link_el.get_attribute("href")
        except:
            product_link = search_url

        if price and price > 1000:
            log(f"  ✅ {product_name[:60]} → {price:,}원")
            return {
                "product_name": product_name,
                "price": price,
                "link": product_link,
            }
    except Exception as e:
        log(f"  방법 1 실패: {str(e)}", "WARN")

    # 방법 2: 텍스트 패턴 매칭
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        lines = page_text.split('\n')

        for i, line in enumerate(lines):
            price_match = re.search(r'(\d{2,3},\d{3})원', line)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))
                if price > 10000:
                    nearby = " ".join(lines[max(0, i-5):i+1])
                    name_match = re.search(r'(삼성전자?\s*(?:DDR5|ddr5)[^\n]{0,50})', nearby, re.IGNORECASE)
                    product_name = name_match.group(1).strip() if name_match else query

                    log(f"  ✅ (패턴) {product_name[:60]} → {price:,}원")
                    return {
                        "product_name": product_name,
                        "price": price,
                        "link": search_url,
                    }
    except Exception as e:
        log(f"  방법 2 실패: {str(e)}", "WARN")

    # 디버그 스크린샷
    try:
        debug_path = os.path.join(BASE_DIR, f"danawa_debug_{query.replace(' ', '_')[:30]}.png")
        driver.save_screenshot(debug_path)
        log(f"  스크린샷: {debug_path}")
    except:
        pass

    log(f"  ❌ 가격 추출 실패: {query}", "ERROR")
    return None

# ============================================
# 데이터 저장 (기존 ram_new_*.json 형식 유지)
# ============================================
def get_data_file():
    files = glob.glob(os.path.join(BASE_DIR, "ram_new_*.json"))
    if files:
        latest = sorted(files)[-1]
        log(f"기존 데이터 파일 사용: {latest}")
        return latest
    new_file = os.path.join(BASE_DIR, f"ram_new_{datetime.now(KST).strftime('%Y%m%d')}.json")
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
        except:
            pass

    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data

    for category, items in parsed_data.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []

        existing = {item["product"]: idx for idx, item in enumerate(full["price_data"][category])}
        for new_item in items:
            name = new_item["product"]
            if name in existing:
                full["price_data"][category][existing[name]] = new_item
            else:
                full["price_data"][category].append(new_item)

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)

    log(f"✅ 저장 완료: {history_key}")

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
    log("🔍 다나와 RAM 최저가 크롤러")
    log(f"📅 KST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📂 작업 디렉토리: {BASE_DIR}")
    log("=" * 60)

    driver = None
    try:
        driver = setup_driver()

        # 기존 형식에 맞춰서 수집: { "카테고리": [{"product": ..., "price": ...}] }
        parsed_data = {}

        for target in TARGETS:
            category = target["category"]
            log(f"\n📦 카테고리: {category}")
            parsed_data[category] = []

            for item in target["items"]:
                query = item["query"]
                label = item["label"]

                result = search_danawa(driver, query)

                if result:
                    parsed_data[category].append({
                        "product": f"삼성전자 {category} {label}",
                        "price": result["price"],
                        "price_formatted": f"{result['price']:,}원",
                        "source": "다나와",
                        "source_title": result["product_name"],
                        "link": result["link"],
                    })

                time.sleep(2)

        total = sum(len(v) for v in parsed_data.values())
        if total == 0:
            log("❌ 수집된 데이터 없음", "ERROR")
            return False

        today = now.strftime("%Y-%m-%d")
        time_slot = get_current_time_slot()
        save_data(parsed_data, today, time_slot)

        log("=" * 60)
        log(f"✅ 완료! {total}개 제품 수집")
        for cat, items in parsed_data.items():
            for item in items:
                log(f"  {item['product']}: {item['price_formatted']}")
        log("=" * 60)
        return True

    except Exception as e:
        log(f"❌ 오류: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False
    finally:
        if driver:
            driver.quit()
            log("브라우저 종료")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
