"""
컴퓨존(Compuzone) RAM 가격 크롤러
- 검색 결과 페이지에서 직접 가격 추출 (제품 상세 페이지 접근 안 함)
- compuzone_data.json 으로 저장
"""

import os
import json
import sys
import traceback
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta

# ============================================
# 설정
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

# 컴퓨존 검색 URL
SEARCH_URL = "https://www.compuzone.co.kr/search/search.htm"

# 수집 대상
TARGETS = [
    {
        "name": "삼성 DDR5 PC5-44800",
        "search_keyword": "삼성 DDR5 PC5-44800",
        "category": "DDR5 (데스크탑)",
        "title_must_include": ["DDR5", "PC5-44800"],
        "title_must_exclude": ["ECC", "REG", "서버", "노트북"],
        "capacities": ["8GB", "16GB", "24GB", "32GB"],
    },
    {
        "name": "삼성 DDR5 PC5-44800 ECC/REG 서버용",
        "search_keyword": "삼성 DDR5 PC5-44800",
        "category": "DDR5 ECC/REG (서버용)",
        "title_must_include": ["DDR5", "PC5-44800", "ECC"],
        "title_must_exclude": [],
        "capacities": ["16GB", "32GB", "64GB", "128GB"],
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://www.compuzone.co.kr/",
}

# ============================================
# 로깅
# ============================================
def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

# ============================================
# 검색 결과 페이지에서 제품 + 옵션 가격 직접 추출
# ============================================
def fetch_search_page(keyword):
    """검색 결과 페이지 HTML 가져오기"""
    log(f"검색 페이지 요청: {keyword}")
    
    # 여러 URL 패턴 시도
    url_patterns = [
        (SEARCH_URL, {"SearchProductKeyWord": keyword}),
        (SEARCH_URL, {"q": keyword}),
        ("https://www.compuzone.co.kr/search/search_result.htm", {"SearchProductKeyWord": keyword}),
    ]
    
    for url, params in url_patterns:
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 200 and len(resp.text) > 1000:
                log(f"  ✅ 검색 성공: {url} (응답 {len(resp.text)} bytes)")
                return resp.text
            else:
                log(f"  ⚠️ {url} → status={resp.status_code}, size={len(resp.text)}", "WARN")
        except Exception as e:
            log(f"  ⚠️ {url} → {str(e)}", "WARN")
    
    log("❌ 모든 검색 URL 실패", "ERROR")
    return None


def parse_products_from_search(html):
    """검색 결과 HTML에서 제품명 + 옵션 가격 추출"""
    soup = BeautifulSoup(html, "html.parser")
    products = []
    
    # ============================================
    # 방법 1: 전체 HTML 텍스트에서 제품 블록 패턴으로 추출
    # ============================================
    page_text = soup.get_text(separator="\n")
    
    # 제품 제목 패턴: [삼성전자] 삼성 DDR5 PC5-44800 ...
    title_pattern = r'\[삼성전자\]\s*(삼성\s*DDR5\s*PC5-44800[^\n]*)'
    titles = re.finditer(title_pattern, page_text)
    
    for title_match in titles:
        product_title = title_match.group(0).strip()
        # 제목 이후 텍스트에서 옵션 가격 추출
        start_pos = title_match.end()
        # 다음 제품까지의 텍스트 블록 (최대 2000자)
        block_text = page_text[start_pos:start_pos + 2000]
        
        # [용량] (속도) ... 가격원 패턴
        option_pattern = r'\[(\d+GB)\]\s*\(\d+\)\s*.*?([\d,]+)원'
        options = re.findall(option_pattern, block_text)
        
        if options:
            parsed_options = []
            for cap, price_str in options:
                price = int(price_str.replace(",", ""))
                if price > 10000:
                    parsed_options.append({"capacity": cap, "price": price})
            
            if parsed_options:
                products.append({
                    "title": product_title,
                    "options": parsed_options
                })
                log(f"  📦 제품 발견: {product_title}")
                for opt in parsed_options:
                    log(f"     {opt['capacity']}: {opt['price']:,}원")
    
    # ============================================
    # 방법 2: HTML 구조 기반 추출 (방법 1 실패 시 보완)
    # ============================================
    if not products:
        log("  텍스트 패턴 실패, HTML 구조 분석 시도...")
        
        # 제품 카드/블록 찾기 (다양한 셀렉터 시도)
        product_blocks = (
            soup.select(".product_list > div") or
            soup.select(".prd_list > li") or
            soup.select("[class*='product']") or
            soup.select("[class*='item']")
        )
        
        for block in product_blocks:
            block_text = block.get_text()
            if "DDR5" not in block_text or "PC5-44800" not in block_text:
                continue
            
            # 제목 추출
            title_el = block.select_one("a[href*='product'], .prd_name, .product_name")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                title_match = re.search(r'\[삼성전자\]\s*삼성[^\n]+', block_text)
                title = title_match.group(0) if title_match else "DDR5 PC5-44800"
            
            option_pattern = r'\[(\d+GB)\]\s*\(\d+\)\s*.*?([\d,]+)원'
            options = re.findall(option_pattern, block_text)
            
            if options:
                parsed_options = []
                for cap, price_str in options:
                    price = int(price_str.replace(",", ""))
                    if price > 10000:
                        parsed_options.append({"capacity": cap, "price": price})
                
                if parsed_options:
                    products.append({"title": title, "options": parsed_options})
                    log(f"  📦 제품 발견 (HTML): {title[:60]}")
    
    log(f"  총 {len(products)}개 제품 파싱 완료")
    return products


def match_target(products, target):
    """파싱된 제품 중 타겟에 맞는 제품 찾기"""
    for product in products:
        title = product["title"].upper()
        
        # 포함해야 할 키워드 확인
        must_include = all(kw.upper() in title for kw in target["title_must_include"])
        # 제외해야 할 키워드 확인
        must_exclude = any(kw.upper() in title for kw in target["title_must_exclude"])
        
        if must_include and not must_exclude:
            # 대상 용량만 필터링
            filtered_options = [
                opt for opt in product["options"] 
                if opt["capacity"] in target["capacities"]
            ]
            
            if filtered_options:
                return {
                    "product_name": target["name"],
                    "category": target["category"],
                    "source_title": product["title"],
                    "options": [
                        {
                            "capacity": opt["capacity"],
                            "price": opt["price"],
                            "price_formatted": f"{opt['price']:,}원",
                        }
                        for opt in filtered_options
                    ],
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
            log(f"기존 데이터 로드 완료")
        except Exception as e:
            log(f"기존 파일 로드 실패: {str(e)}", "WARN")

    timestamp = now.strftime("%Y-%m-%d %H:%M")

    # 현재 데이터 업데이트
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

    log(f"✅ 데이터 저장 완료: {data_path}")

# ============================================
# 메인
# ============================================
def main():
    now = datetime.now(KST)
    log("=" * 60)
    log("🛒 컴퓨존 RAM 가격 크롤러")
    log(f"📅 KST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📂 작업 디렉토리: {BASE_DIR}")
    log("=" * 60)

    try:
        # 1. 검색 페이지 가져오기 (한 번만 검색하면 됨 - 두 제품 모두 같은 결과에 있음)
        html = fetch_search_page("삼성 DDR5 PC5-44800")
        
        if not html:
            log("❌ 검색 페이지를 가져올 수 없습니다", "ERROR")
            return False
        
        # 디버깅: HTML 일부 저장
        debug_path = os.path.join(BASE_DIR, "compuzone_debug.html")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"디버그 HTML 저장: {debug_path}")
        
        # 2. 검색 결과에서 모든 제품 + 옵션 가격 추출
        products = parse_products_from_search(html)
        
        if not products:
            log("❌ 검색 결과에서 제품을 찾지 못했습니다", "ERROR")
            log("💡 compuzone_debug.html 파일을 확인해주세요", "ERROR")
            return False
        
        # 3. 각 타겟에 맞는 제품 매칭
        results = []
        for target in TARGETS:
            log(f"\n🎯 매칭 시도: {target['name']}")
            result = match_target(products, target)
            if result:
                log(f"  ✅ 매칭 성공: {len(result['options'])}개 용량")
                for opt in result["options"]:
                    log(f"     {opt['capacity']}: {opt['price_formatted']}")
            else:
                log(f"  ❌ 매칭 실패", "WARN")
            results.append(result)
        
        # 4. 저장
        valid_results = [r for r in results if r is not None]
        if not valid_results:
            log("❌ 매칭된 제품이 없습니다", "ERROR")
            return False
        
        save_data(results)
        
        log("=" * 60)
        log(f"✅ 완료! {len(valid_results)}/{len(TARGETS)} 제품 수집")
        log("=" * 60)
        return True

    except Exception as e:
        log(f"❌ 오류: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
