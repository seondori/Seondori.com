"""
컴퓨존(Compuzone) RAM 가격 크롤러
- 특정 제품의 용량별 가격을 수집
- compuzone_data.json 으로 저장
- 로그인 불필요, requests + BeautifulSoup 사용
"""

import os
import json
import sys
import traceback
import requests
from bs4 import BeautifulSoup
import glob
import re
from datetime import datetime, timezone, timedelta

# ============================================
# 설정
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

SEARCH_URL = "https://www.compuzone.co.kr/search/search_result.htm"

# 수집 대상 제품 및 용량
TARGETS = [
    {
        "name": "삼성 DDR5 PC5-44800 ECC/REG 서버용",
        "search_keyword": "삼성 DDR5 PC5-44800 ECC REG 서버용",
        "category": "DDR5 ECC/REG (서버용)",
        "capacities": ["16GB", "32GB", "64GB", "128GB"],
    },
    {
        "name": "삼성 DDR5 PC5-44800",
        "search_keyword": "삼성전자 삼성 DDR5 PC5-44800",
        "category": "DDR5 (데스크탑)",
        "capacities": ["8GB", "16GB", "24GB", "32GB"],
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# ============================================
# 로깅
# ============================================
def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

# ============================================
# 컴퓨존 검색 & 제품 페이지 찾기
# ============================================
def search_product(keyword):
    """컴퓨존에서 제품 검색 후 제품 URL 반환"""
    log(f"검색: {keyword}")
    try:
        params = {"SearchProductKeyWord": keyword}
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 검색 결과에서 제품 링크 찾기
        product_links = soup.select("a[href*='product_detail']")

        if not product_links:
            # 다른 셀렉터 시도
            product_links = soup.select(".product_name a, .prd_name a, .item_name a")

        results = []
        for link in product_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if href and text:
                if not href.startswith("http"):
                    href = "https://www.compuzone.co.kr" + href
                results.append({"url": href, "title": text})

        log(f"  검색 결과: {len(results)}개")
        for r in results[:5]:
            log(f"  - {r['title'][:60]}")

        return results
    except Exception as e:
        log(f"검색 오류: {str(e)}", "ERROR")
        return []


def get_product_options(url):
    """제품 페이지에서 옵션(용량)별 가격 추출"""
    log(f"제품 페이지 접근: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        options = []

        # 방법 1: 옵션 테이블에서 추출
        option_rows = soup.select(".option_list tr, .opt_list tr, .product_option tr")
        for row in option_rows:
            text = row.get_text(strip=True)
            # [16GB] (5600) ... 963,000원 패턴 매칭
            match = re.search(r'\[(\d+GB)\].*?([\d,]+)원', text)
            if match:
                capacity = match.group(1)
                price_str = match.group(2).replace(",", "")
                price = int(price_str)
                options.append({"capacity": capacity, "price": price})
                log(f"  옵션 발견: {capacity} - {price:,}원")

        # 방법 2: 옵션 select/라디오 버튼에서 추출
        if not options:
            option_elements = soup.select("select option, input[type='radio']")
            for elem in option_elements:
                text = elem.get_text(strip=True) if elem.name == "option" else elem.get("value", "")
                label = elem.parent.get_text(strip=True) if elem.name == "input" else text
                match = re.search(r'\[(\d+GB)\].*?([\d,]+)원', label)
                if match:
                    capacity = match.group(1)
                    price_str = match.group(2).replace(",", "")
                    price = int(price_str)
                    options.append({"capacity": capacity, "price": price})
                    log(f"  옵션 발견: {capacity} - {price:,}원")

        # 방법 3: 전체 페이지 텍스트에서 패턴 매칭
        if not options:
            page_text = soup.get_text()
            # [16GB] (5600) 뒤에 가격이 오는 패턴
            pattern = r'\[(\d+GB)\]\s*\(\d+\).*?([\d,]+)원'
            matches = re.findall(pattern, page_text)
            for cap, price_str in matches:
                price = int(price_str.replace(",", ""))
                if price > 10000:  # 너무 작은 금액 필터
                    options.append({"capacity": cap, "price": price})
                    log(f"  텍스트 패턴 매칭: {cap} - {price:,}원")

        # 방법 4: data 속성이나 script에서 추출
        if not options:
            scripts = soup.find_all("script")
            for script in scripts:
                script_text = script.string or ""
                matches = re.findall(r'\[(\d+GB)\].*?(\d{2,3},?\d{3})원?', script_text)
                for cap, price_str in matches:
                    price = int(price_str.replace(",", ""))
                    if price > 10000:
                        options.append({"capacity": cap, "price": price})

        return options
    except Exception as e:
        log(f"제품 페이지 오류: {str(e)}", "ERROR")
        return []


def find_and_extract(target):
    """대상 제품을 검색하고 옵션별 가격 추출"""
    log(f"\n{'='*50}")
    log(f"📦 대상: {target['name']}")
    log(f"{'='*50}")

    search_results = search_product(target["search_keyword"])

    if not search_results:
        log(f"❌ 검색 결과 없음: {target['search_keyword']}", "ERROR")
        return None

    # 제품명에 가장 잘 매칭되는 결과 찾기
    best_match = None
    target_name_lower = target["name"].lower().replace(" ", "")

    for result in search_results:
        result_title_lower = result["title"].lower().replace(" ", "")
        # 핵심 키워드 포함 여부 확인
        if "ddr5" in result_title_lower and "pc5-44800" in result_title_lower:
            if "ecc" in target_name_lower and "ecc" in result_title_lower:
                best_match = result
                break
            elif "ecc" not in target_name_lower and "ecc" not in result_title_lower:
                best_match = result
                break

    if not best_match and search_results:
        best_match = search_results[0]

    if not best_match:
        log(f"❌ 매칭 제품 없음", "ERROR")
        return None

    log(f"✅ 매칭: {best_match['title']}")

    # 옵션 가격 추출
    options = get_product_options(best_match["url"])

    if not options:
        log(f"⚠️ 옵션 가격을 추출하지 못했습니다", "WARN")
        return None

    # 대상 용량만 필터링
    filtered = []
    for opt in options:
        if opt["capacity"] in target["capacities"]:
            filtered.append({
                "capacity": opt["capacity"],
                "price": opt["price"],
                "price_formatted": f"{opt['price']:,}원",
            })

    log(f"✅ {len(filtered)}개 용량 수집 완료")
    return {
        "product_name": target["name"],
        "category": target["category"],
        "source_url": best_match["url"],
        "source_title": best_match["title"],
        "options": filtered,
    }

# ============================================
# 데이터 저장
# ============================================
def save_data(products):
    """compuzone_data.json에 저장"""
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
    for product in products:
        if product is None:
            continue
        category = product["category"]
        full["products"][category] = {
            "product_name": product["product_name"],
            "source_url": product["source_url"],
            "options": product["options"],
        }

    # 히스토리 추가
    history_entry = {}
    for product in products:
        if product is None:
            continue
        category = product["category"]
        history_entry[category] = product["options"]

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
        results = []
        for target in TARGETS:
            result = find_and_extract(target)
            results.append(result)

        valid_results = [r for r in results if r is not None]

        if not valid_results:
            log("❌ 수집된 데이터가 없습니다", "ERROR")
            return False

        save_data(results)

        log("=" * 60)
        log(f"✅ 크롤링 완료! {len(valid_results)}/{len(TARGETS)} 제품 수집")
        log("=" * 60)
        return True

    except Exception as e:
        log(f"❌ 오류: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
