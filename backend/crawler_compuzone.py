"""
컴퓨존(Compuzone) RAM 가격 크롤러
- Selenium으로 검색 결과 페이지 렌더링
- 옵션 행(tr/li/div) 단위로 용량+가격 함께 추출
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

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

def extract_products(driver, keyword):
    """검색 결과 페이지에서 제품 + 옵션별 가격 추출"""
    url = f"https://www.compuzone.co.kr/search/search.htm?SearchProductKey={keyword.replace(' ', '+')}"
    log(f"검색: {url}")

    driver.get(url)

    # AJAX 로딩 대기
    log("AJAX 로딩 대기...")
    try:
        WebDriverWait(driver, 15).until(
            lambda d: "DDR5" in d.page_source and "원" in d.page_source
        )
        log("✅ 제품 로딩 완료")
    except:
        log("⚠️ 15초 대기 후에도 제품 미확인, 추가 대기...", "WARN")
        time.sleep(5)

    # ============================================
    # 핵심: JavaScript로 옵션 행 데이터 직접 추출
    # ============================================
    # 컴퓨존 옵션은 체크박스 행으로 되어있음
    # 각 행에서 [XGB] 텍스트와 가격을 함께 추출
    
    products_js = driver.execute_script("""
        var results = [];
        
        // 모든 제품 블록을 찾기 (제품명 + 옵션)
        var allText = document.body.innerText;
        
        // 제품 제목과 옵션을 포함하는 영역 찾기
        // 방법 1: 체크박스 input의 부모 행에서 추출
        var checkboxes = document.querySelectorAll('input[type="checkbox"]');
        var optionRows = [];
        
        checkboxes.forEach(function(cb) {
            var row = cb.closest('tr') || cb.closest('li') || cb.closest('div');
            if (row) {
                var text = row.innerText || row.textContent || '';
                // [8GB] (5600) ... 179,000원 패턴 확인
                if (text.match(/\\[\\d+GB\\]/)) {
                    optionRows.push(text.trim());
                }
            }
        });
        
        // 방법 2: 테이블 행에서 추출
        if (optionRows.length === 0) {
            var rows = document.querySelectorAll('tr, li, .opt_item, .option_item');
            rows.forEach(function(row) {
                var text = row.innerText || row.textContent || '';
                if (text.match(/\\[\\d+GB\\]/) && text.match(/[\\d,]+원/)) {
                    optionRows.push(text.trim());
                }
            });
        }
        
        // 방법 3: 모든 텍스트 노드에서 GB와 원이 근접한 것 찾기
        if (optionRows.length === 0) {
            var allElements = document.querySelectorAll('*');
            allElements.forEach(function(el) {
                if (el.children.length === 0 || el.children.length < 5) {
                    var text = el.innerText || '';
                    if (text.match(/\\[\\d+GB\\]/) && text.match(/[\\d,]+원/) && text.length < 500) {
                        optionRows.push(text.trim());
                    }
                }
            });
        }
        
        return {
            optionRows: optionRows,
            // 제품 제목도 추출
            titles: Array.from(document.querySelectorAll('a, span, div')).filter(function(el) {
                var t = el.innerText || '';
                return t.indexOf('[삼성전자]') >= 0 && t.indexOf('DDR5') >= 0 && t.indexOf('PC5-44800') >= 0 && t.length < 200;
            }).map(function(el) { return el.innerText.trim(); }).filter(function(v, i, a) { return a.indexOf(v) === i; })
        };
    """)

    option_rows = products_js.get("optionRows", [])
    titles = products_js.get("titles", [])

    log(f"\nJS 추출 결과:")
    log(f"  제목 후보: {len(titles)}개")
    for t in titles[:5]:
        log(f"    {t[:80]}")
    log(f"  옵션 행: {len(option_rows)}개")
    for r in option_rows[:20]:
        log(f"    {r[:120]}")

    # ============================================
    # 옵션 행에서 용량 + 가격 파싱
    # ============================================
    all_options = []
    for row_text in option_rows:
        cap_match = re.search(r'\[(\d+GB)\]', row_text)
        # 가격: 쉼표 포함 숫자 + 원 (마지막에 나오는 큰 가격)
        price_matches = re.findall(r'([\d,]+)원', row_text)
        
        if cap_match and price_matches:
            capacity = cap_match.group(1)
            # 여러 가격 중 가장 큰 것 선택 (수량 '1'이 아닌 실제 가격)
            prices = []
            for p in price_matches:
                val = int(p.replace(",", ""))
                if val > 1000:  # 수량(1) 등 제외
                    prices.append(val)
            
            if prices:
                price = prices[0]  # 첫 번째 유효 가격
                all_options.append({"capacity": capacity, "price": price})
                log(f"  ✅ {capacity}: {price:,}원")

    # 중복 제거 (같은 용량이 여러 번 나올 수 있음 - 다른 제품)
    # 제품별로 그룹화하기 위해 텍스트 기반으로 제목 매칭
    
    # 페이지 전체 텍스트도 추출 (fallback)
    if not all_options:
        log("\nJS 추출 실패, 전체 텍스트 fallback...")
        page_text = driver.find_element(By.TAG_NAME, "body").text
        lines = page_text.split('\n')
        
        for i, line in enumerate(lines):
            cap_match = re.search(r'\[(\d+GB)\]', line)
            if cap_match:
                capacity = cap_match.group(1)
                # 같은 줄에서 가격 찾기
                price_match = re.search(r'([\d,]+)원', line)
                if price_match:
                    price = int(price_match.group(1).replace(",", ""))
                    if price > 1000:
                        all_options.append({"capacity": capacity, "price": price})
                        log(f"  ✅ (텍스트) {capacity}: {price:,}원")
                        continue
                
                # 다음 줄에서 가격 찾기
                for j in range(i+1, min(i+3, len(lines))):
                    price_match = re.search(r'([\d,]+)원', lines[j])
                    if price_match:
                        price = int(price_match.group(1).replace(",", ""))
                        if price > 1000:
                            all_options.append({"capacity": capacity, "price": price})
                            log(f"  ✅ (다음줄) {capacity}: {price:,}원")
                            break

    if not all_options:
        # 디버그 스크린샷
        debug_path = os.path.join(BASE_DIR, "compuzone_debug.png")
        driver.save_screenshot(debug_path)
        log(f"스크린샷 저장: {debug_path}")

    # ============================================
    # 제품별로 옵션 그룹화
    # ============================================
    # 옵션들을 제품 제목과 매칭
    # 컴퓨존 검색 결과에서 제품 순서: 데스크탑 → 서버 → 노트북
    # 용량으로 구분: 8/16/24/32GB = 데스크탑, 16/32/64/128GB = 서버
    
    desktop_caps = {"8GB", "16GB", "24GB", "32GB"}
    server_caps = {"64GB", "128GB"}
    
    products = []
    
    # 데스크탑 제품 옵션
    desktop_options = [o for o in all_options if o["capacity"] in desktop_caps]
    # 서버 제품 옵션 (64GB, 128GB는 서버 전용)
    server_options = [o for o in all_options if o["capacity"] in server_caps]
    # 16GB, 32GB는 둘 다 있을 수 있음 - 가격으로 구분
    # 서버 16GB는 보통 90만원+, 데스크탑 16GB는 보통 30만원대
    for o in all_options:
        if o["capacity"] in {"16GB", "32GB"}:
            if o["capacity"] == "16GB" and o["price"] > 500000:
                if o not in server_options:
                    server_options.append(o)
            elif o["capacity"] == "32GB" and o["price"] > 1000000:
                if o not in server_options:
                    server_options.append(o)

    # 중복 제거
    seen = set()
    desktop_unique = []
    for o in desktop_options:
        key = o["capacity"]
        if key not in seen:
            seen.add(key)
            desktop_unique.append(o)

    seen = set()
    server_unique = []
    for o in server_options:
        key = o["capacity"]
        if key not in seen:
            seen.add(key)
            server_unique.append(o)

    if desktop_unique:
        desktop_title = ""
        for t in titles:
            if "ECC" not in t.upper() and "서버" not in t:
                desktop_title = t
                break
        products.append({
            "title": desktop_title or "[삼성전자] 삼성 DDR5 PC5-44800",
            "options": desktop_unique,
        })

    if server_unique:
        server_title = ""
        for t in titles:
            if "ECC" in t.upper() or "서버" in t:
                server_title = t
                break
        products.append({
            "title": server_title or "[삼성전자] 삼성 DDR5 PC5-44800 ECC/REG 서버용",
            "options": server_unique,
        })

    log(f"\n총 {len(products)}개 제품, {len(all_options)}개 옵션 추출")
    return products

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

def main():
    now = datetime.now(KST)
    log("=" * 60)
    log("🛒 컴퓨존 RAM 가격 크롤러 (Selenium)")
    log(f"📅 KST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    driver = None
    try:
        driver = setup_driver()
        products = extract_products(driver, "삼성 DDR5 PC5-44800")

        if not products:
            log("❌ 제품을 찾지 못했습니다", "ERROR")
            return False

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
