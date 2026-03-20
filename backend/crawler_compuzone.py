"""
컴퓨존(Compuzone) RAM 가격 크롤러
- Selenium headless Chrome으로 JavaScript 렌더링 후 가격 추출
- 컴퓨존 검색 결과는 AJAX로 동적 로딩되므로 requests 사용 불가
- compuzone_data.json 으로 저장
"""

import os
import json
import sys
import traceback
import re
import time
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ============================================
# 설정
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

SEARCH_URL = "https://www.compuzone.co.kr/search/search.htm"

TARGETS = [
    {
        "name": "삼성 DDR5 PC5-44800",
        "category": "DDR5 (데스크탑)",
        "title_must_include": ["삼성", "DDR5", "PC5-44800"],
        "title_must_exclude": ["ECC", "REG", "서버", "노트북", "저전력"],
        "capacities": ["8GB", "16GB", "24GB", "32GB"],
    },
    {
        "name": "삼성 DDR5 PC5-44800 ECC/REG 서버용",
        "category": "DDR5 ECC/REG (서버용)",
        "title_must_include": ["삼성", "DDR5", "PC5-44800", "ECC"],
        "title_must_exclude": [],
        "capacities": ["16GB", "32GB", "64GB", "128GB"],
    },
]

def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

# ============================================
# Selenium 드라이버
# ============================================
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

# ============================================
# 검색 결과 페이지에서 제품 + 옵션 가격 추출
# ============================================
def extract_products(driver, keyword):
    """검색 결과 페이지를 렌더링한 후 제품 + 옵션 가격 추출"""
    url = f"{SEARCH_URL}?SearchProductKey={keyword.replace(' ', '+')}"
    log(f"검색 페이지 접속: {url}")
    
    driver.get(url)
    
    # AJAX 로딩 대기 (제품 목록이 나타날 때까지)
    log("AJAX 제품 목록 로딩 대기...")
    try:
        WebDriverWait(driver, 15).until(
            lambda d: "DDR5" in d.page_source and "원" in d.page_source and "PC5-44800" in d.page_source
        )
        log("✅ 제품 목록 로딩 완료")
    except:
        log("⚠️ 15초 대기 후에도 제품 목록 미확인, 추가 대기...", "WARN")
        time.sleep(5)
    
    # 렌더링된 페이지 텍스트 추출
    page_text = driver.find_element(By.TAG_NAME, "body").text
    
    # 디버그: DDR5 관련 내용 확인
    ddr5_count = page_text.count("DDR5")
    price_count = page_text.count("원")
    log(f"렌더링 후 - DDR5 언급: {ddr5_count}회, '원' 언급: {price_count}회")
    
    if ddr5_count == 0:
        log("❌ 렌더링 후에도 DDR5 제품 없음", "ERROR")
        # 디버그용 스크린샷
        debug_path = os.path.join(BASE_DIR, "compuzone_debug.png")
        driver.save_screenshot(debug_path)
        log(f"스크린샷 저장: {debug_path}")
        return []
    
    # 제품 파싱
    products = []
    lines = page_text.split('\n')
    
    # [삼성전자] 삼성 DDR5 PC5-44800 ... 제목 라인 찾기
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # 제품 제목 탐지
        if '[삼성전자]' in line and 'DDR5' in line and 'PC5-44800' in line:
            product_title = line
            log(f"\n📦 제품 발견 (라인 {i}): {product_title[:80]}")
            
            # 제목 이후 라인들에서 옵션 가격 추출
            options = []
            for j in range(i + 1, min(i + 60, len(lines))):
                opt_line = lines[j].strip()
                
                # 다음 제품 제목이 나오면 중단
                if '[삼성전자]' in opt_line and 'DDR5' in opt_line and j > i + 2:
                    break
                
                # [16GB] (5600) ... 345,000원 패턴
                cap_match = re.search(r'\[(\d+GB)\]', opt_line)
                if cap_match:
                    capacity = cap_match.group(1)
                    # 같은 줄 또는 바로 다음 줄에서 가격 찾기
                    price_text = opt_line
                    if j + 1 < len(lines):
                        price_text += " " + lines[j + 1].strip()
                    
                    price_match = re.search(r'([\d,]+)원', price_text)
                    if price_match:
                        price = int(price_match.group(1).replace(",", ""))
                        if price > 10000:
                            options.append({"capacity": capacity, "price": price})
                            log(f"  ✅ {capacity}: {price:,}원")
            
            if options:
                products.append({"title": product_title, "options": options})
    
    # 방법 2: 위 방법으로 못 찾으면 전체 텍스트에서 패턴 매칭
    if not products:
        log("\n📋 전체 텍스트 패턴 매칭 시도...")
        
        # 전체 텍스트에서 [XGB] (XXXX) ... X,XXX원 또는 X,XXX,XXX원 패턴
        all_text = " ".join(lines)
        
        # 제품 블록 분리: [삼성전자] 기준으로 분할
        blocks = re.split(r'(?=\[삼성전자\])', all_text)
        
        for block in blocks:
            if 'DDR5' not in block or 'PC5-44800' not in block:
                continue
            
            title_match = re.match(r'(\[삼성전자\][^\[]*?)(?=\[\d+GB\]|$)', block)
            title = title_match.group(1).strip()[:100] if title_match else "삼성 DDR5"
            
            options = []
            for m in re.finditer(r'\[(\d+GB)\]\s*\(\d+\)', block):
                cap = m.group(1)
                after = block[m.end():m.end() + 300]
                pm = re.search(r'([\d,]+)원', after)
                if pm:
                    price = int(pm.group(1).replace(",", ""))
                    if price > 10000:
                        options.append({"capacity": cap, "price": price})
            
            if options:
                products.append({"title": title, "options": options})
                log(f"📦 제품(패턴): {title[:60]} ({len(options)}개 옵션)")
    
    log(f"\n총 {len(products)}개 제품 추출")
    return products

# ============================================
# 타겟 매칭
# ============================================
def match_target(products, target):
    for product in products:
        title_upper = product["title"].upper()
        
        must_include = all(kw.upper() in title_upper for kw in target["title_must_include"])
        must_exclude = any(kw.upper() in title_upper for kw in target["title_must_exclude"])
        
        if must_include and not must_exclude:
            filtered = [
                {
                    "capacity": opt["capacity"],
                    "price": opt["price"],
                    "price_formatted": f"{opt['price']:,}원",
                }
                for opt in product["options"]
                if opt["capacity"] in target["capacities"]
            ]
            
            if filtered:
                return {
                    "product_name": target["name"],
                    "category": target["category"],
                    "source_title": product["title"],
                    "options": filtered,
                }
    return None

# ============================================
# 데이터 저장
# ============================================
def save_data(results):
    now = datetime.now(KST)
    data_path = os.path.join(BASE_DIR, "compuzone_data.json")

    full = {"products": {}, "price_history": {}, "last_updated": ""}

    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                full = json.load(f)
        except:
            pass

    timestamp = now.strftime("%Y-%m-%d %H:%M")
    history_entry = {}

    for result in results:
        if result is None:
            continue
        category = result["category"]
        full["products"][category] = {
            "product_name": result["product_name"],
            "source_title": result["source_title"],
            "options": result["options"],
        }
        history_entry[category] = result["options"]

    if history_entry:
        full["price_history"][timestamp] = history_entry

    full["last_updated"] = timestamp

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)

    log(f"✅ 데이터 저장: {data_path}")

# ============================================
# 메인
# ============================================
def main():
    now = datetime.now(KST)
    log("=" * 60)
    log("🛒 컴퓨존 RAM 가격 크롤러 (Selenium)")
    log(f"📅 KST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📂 작업 디렉토리: {BASE_DIR}")
    log("=" * 60)

    driver = None
    try:
        driver = setup_driver()
        
        # 검색 & 추출
        products = extract_products(driver, "삼성 DDR5 PC5-44800")
        
        if not products:
            log("❌ 제품을 찾지 못했습니다", "ERROR")
            return False
        
        # 타겟 매칭
        results = []
        for target in TARGETS:
            log(f"\n🎯 매칭: {target['name']}")
            result = match_target(products, target)
            if result:
                log(f"  ✅ 성공: {len(result['options'])}개 용량")
                for opt in result["options"]:
                    log(f"     {opt['capacity']}: {opt['price_formatted']}")
            else:
                log(f"  ❌ 실패", "WARN")
            results.append(result)
        
        valid = [r for r in results if r is not None]
        if not valid:
            log("❌ 매칭된 제품 없음", "ERROR")
            return False
        
        save_data(results)
        
        log("=" * 60)
        log(f"✅ 완료! {len(valid)}/{len(TARGETS)} 제품 수집")
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
