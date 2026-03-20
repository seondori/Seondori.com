"""
컴퓨존(Compuzone) RAM 가격 크롤러
- 검색 결과 페이지에서 직접 가격 추출
- 디버그 로깅 강화: HTML 구조 분석 출력
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

SEARCH_URL = "https://www.compuzone.co.kr/search/search.htm"

TARGETS = [
    {
        "name": "삼성 DDR5 PC5-44800",
        "category": "DDR5 (데스크탑)",
        "title_must_include": ["DDR5", "PC5-44800"],
        "title_must_exclude": ["ECC", "REG", "서버", "노트북", "저전력"],
        "capacities": ["8GB", "16GB", "24GB", "32GB"],
    },
    {
        "name": "삼성 DDR5 PC5-44800 ECC/REG 서버용",
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

def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

# ============================================
# HTML 구조 디버깅
# ============================================
def debug_html_structure(soup):
    """HTML 구조를 분석하여 로그 출력"""
    log("=" * 50)
    log("🔍 HTML 구조 디버깅")
    log("=" * 50)
    
    # 1. 페이지 제목
    title = soup.title.string if soup.title else "없음"
    log(f"페이지 제목: {title}")
    
    # 2. DDR5 텍스트가 포함된 모든 요소 찾기
    all_text = soup.get_text()
    ddr5_count = all_text.count("DDR5")
    pc5_count = all_text.count("PC5-44800")
    log(f"DDR5 언급 횟수: {ddr5_count}")
    log(f"PC5-44800 언급 횟수: {pc5_count}")
    
    # 3. 가격 패턴 찾기 (숫자,숫자원)
    price_matches = re.findall(r'([\d,]+)원', all_text)
    log(f"'X원' 패턴 발견: {len(price_matches)}개")
    if price_matches[:10]:
        log(f"  처음 10개: {price_matches[:10]}")
    
    # 4. [XGB] 패턴 찾기
    gb_matches = re.findall(r'\[(\d+GB)\]', all_text)
    log(f"[XGB] 패턴 발견: {len(gb_matches)}개")
    if gb_matches:
        log(f"  목록: {gb_matches}")
    
    # 5. DDR5가 포함된 텍스트 근처 100자씩 출력
    lines = all_text.split('\n')
    ddr5_lines = [l.strip() for l in lines if 'DDR5' in l and 'PC5-44800' in l and len(l.strip()) > 10]
    log(f"\nDDR5 + PC5-44800 포함 라인: {len(ddr5_lines)}개")
    for i, line in enumerate(ddr5_lines[:10]):
        log(f"  [{i}] {line[:120]}")
    
    # 6. [삼성전자] 포함 라인
    samsung_lines = [l.strip() for l in lines if '삼성전자' in l and len(l.strip()) > 5]
    log(f"\n'삼성전자' 포함 라인: {len(samsung_lines)}개")
    for i, line in enumerate(samsung_lines[:10]):
        log(f"  [{i}] {line[:120]}")
    
    # 7. 가격이 있는 GB 라인 (핵심)
    gb_price_lines = [l.strip() for l in lines if re.search(r'\d+GB.*\d+원', l)]
    log(f"\n'XGB...X원' 패턴 라인: {len(gb_price_lines)}개")
    for i, line in enumerate(gb_price_lines[:20]):
        log(f"  [{i}] {line[:150]}")
    
    # 8. 주요 HTML 태그 구조 확인
    log(f"\n주요 태그 수:")
    for tag in ['table', 'tr', 'td', 'div', 'li', 'span', 'input', 'label', 'checkbox']:
        count = len(soup.find_all(tag))
        if count > 0:
            log(f"  <{tag}>: {count}개")
    
    # 9. class에 product/item/prd 포함된 요소
    product_elements = soup.select("[class*='product'], [class*='prd'], [class*='item'], [class*='goods']")
    unique_classes = set()
    for el in product_elements:
        classes = el.get("class", [])
        for c in classes:
            if any(kw in c.lower() for kw in ['product', 'prd', 'item', 'goods']):
                unique_classes.add(c)
    log(f"\n제품 관련 CSS 클래스:")
    for c in sorted(unique_classes)[:30]:
        log(f"  .{c}")
    
    # 10. checkbox/input 요소 (옵션 선택 관련)
    checkboxes = soup.select("input[type='checkbox'], input[type='radio']")
    log(f"\ncheckbox/radio 요소: {len(checkboxes)}개")
    for cb in checkboxes[:10]:
        log(f"  {cb.get('name', '')}: {cb.get('value', '')} / {cb.parent.get_text(strip=True)[:80] if cb.parent else ''}")

# ============================================
# 제품 + 옵션 가격 추출
# ============================================
def parse_products_from_search(soup):
    """여러 전략으로 제품 + 옵션 가격 추출 시도"""
    products = []
    all_text = soup.get_text(separator="\n")
    lines = all_text.split('\n')
    
    # ============================================
    # 전략 1: [삼성전자] 제목 → 하위 [XGB] 가격 블록
    # ============================================
    log("\n📋 전략 1: 제목 + 하위 GB/가격 블록")
    
    title_indices = []
    for i, line in enumerate(lines):
        if '[삼성전자]' in line and 'DDR5' in line and 'PC5-44800' in line:
            title_indices.append((i, line.strip()))
    
    log(f"  제목 후보: {len(title_indices)}개")
    
    for idx, title in title_indices:
        log(f"  제목[{idx}]: {title[:80]}")
        # 제목 이후 50줄 내에서 옵션 찾기
        options = []
        for j in range(idx + 1, min(idx + 50, len(lines))):
            line = lines[j].strip()
            # [16GB] (5600) 와 가격이 같은 줄 또는 인접 줄
            cap_match = re.search(r'\[(\d+GB)\]', line)
            price_match = re.search(r'([\d,]+)원', line)
            
            if cap_match and price_match:
                cap = cap_match.group(1)
                price = int(price_match.group(1).replace(",", ""))
                if price > 10000:
                    options.append({"capacity": cap, "price": price})
                    log(f"    ✅ {cap}: {price:,}원 (라인 {j})")
            
            # 다음 제품 제목이 나오면 중단
            if j > idx + 3 and '[삼성전자]' in line:
                break
        
        if options:
            products.append({"title": title, "options": options})
    
    # ============================================
    # 전략 2: 전체 텍스트에서 연속된 GB+가격 패턴
    # ============================================
    if not products:
        log("\n📋 전략 2: 연속 GB+가격 패턴")
        
        # 전체 텍스트를 한 줄로 합치고 제품 블록 찾기
        flat_text = " ".join(l.strip() for l in lines if l.strip())
        
        # [삼성전자] 삼성 DDR5 PC5-44800 ... [8GB] (5600) ... 179,000원 ... [16GB] (5600) ... 345,000원
        product_blocks = re.split(r'(?=\[삼성전자\]\s*삼성\s*DDR5\s*PC5-44800)', flat_text)
        
        log(f"  제품 블록: {len(product_blocks)}개")
        
        for block in product_blocks:
            if 'DDR5' not in block or 'PC5-44800' not in block:
                continue
            
            title_match = re.search(r'\[삼성전자\]\s*(삼성\s*DDR5\s*PC5-44800[^[]*?)(?=\[?\d+GB\]|\d{2,3},\d{3}원)', block)
            title = title_match.group(0).strip()[:80] if title_match else "삼성 DDR5 PC5-44800"
            
            options = []
            for cap_match in re.finditer(r'\[(\d+GB)\]\s*\(\d+\)', block):
                cap = cap_match.group(1)
                # 용량 뒤에 오는 첫 번째 가격 찾기
                after_cap = block[cap_match.end():cap_match.end() + 200]
                price_match = re.search(r'([\d,]+)원', after_cap)
                if price_match:
                    price = int(price_match.group(1).replace(",", ""))
                    if price > 10000:
                        options.append({"capacity": cap, "price": price})
                        log(f"    ✅ {cap}: {price:,}원")
            
            if options:
                products.append({"title": title, "options": options})
    
    # ============================================
    # 전략 3: HTML label/checkbox 기반
    # ============================================
    if not products:
        log("\n📋 전략 3: HTML checkbox/label 구조")
        
        # 옵션 체크박스 근처에서 가격 찾기
        for checkbox in soup.select("input[type='checkbox']"):
            parent_text = ""
            for parent in [checkbox.parent, checkbox.parent.parent if checkbox.parent else None]:
                if parent:
                    parent_text = parent.get_text(strip=True)
                    cap_match = re.search(r'\[?(\d+GB)\]?', parent_text)
                    price_match = re.search(r'([\d,]+)원', parent_text)
                    if cap_match and price_match:
                        log(f"    checkbox 발견: {parent_text[:100]}")
                        break
    
    log(f"\n총 {len(products)}개 제품 추출 완료")
    return products


def match_target(products, target):
    """파싱된 제품 중 타겟에 맞는 제품 찾기"""
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
        # 1. 검색
        log("검색 페이지 요청: 삼성 DDR5 PC5-44800")
        resp = requests.get(
            SEARCH_URL,
            params={"SearchProductKeyWord": "삼성 DDR5 PC5-44800"},
            headers=HEADERS,
            timeout=15
        )
        
        if resp.status_code != 200:
            log(f"❌ 검색 실패: HTTP {resp.status_code}", "ERROR")
            return False
        
        html = resp.text
        log(f"✅ 검색 성공 ({len(html)} bytes)")
        
        # 디버그 HTML 저장
        debug_path = os.path.join(BASE_DIR, "compuzone_debug.html")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        soup = BeautifulSoup(html, "html.parser")
        
        # 2. HTML 구조 디버깅
        debug_html_structure(soup)
        
        # 3. 제품 추출
        products = parse_products_from_search(soup)
        
        if not products:
            log("❌ 제품을 찾지 못했습니다", "ERROR")
            log("💡 위 디버그 로그를 확인하거나, compuzone_debug.html을 공유해주세요", "ERROR")
            return False
        
        # 4. 타겟 매칭
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
        
        # 5. 저장
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


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
