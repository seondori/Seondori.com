"""
네이버 쇼핑 API 기반 RAM 신품 최저가 수집기
- 쿠키/로그인 불필요, API 키만 있으면 동작
- ram_new_YYYYMMDD.json 으로 별도 저장
- 기존 카페 크롤러(중고 매입 시세)와 병렬 운영
"""

import os
import json
import sys
import traceback
import requests
import glob
from datetime import datetime, timezone, timedelta

# ============================================
# 설정
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

# 수집 대상 RAM 목록
RAM_TARGETS = [
    {
        "category": "DDR5 RAM (데스크탑)",
        "items": [
            {"query": "삼성 DDR5 데스크탑 8GB", "capacity": "8GB"},
            {"query": "삼성 DDR5 데스크탑 16GB", "capacity": "16GB"},
            {"query": "삼성 DDR5 데스크탑 32GB", "capacity": "32GB"},
        ]
    },
    {
        "category": "DDR4 RAM (데스크탑)",
        "items": [
            {"query": "삼성 DDR4 데스크탑 4GB", "capacity": "4GB"},
            {"query": "삼성 DDR4 데스크탑 8GB", "capacity": "8GB"},
            {"query": "삼성 DDR4 데스크탑 16GB", "capacity": "16GB"},
            {"query": "삼성 DDR4 데스크탑 32GB", "capacity": "32GB"},
        ]
    },
    {
        "category": "DDR3 RAM (데스크탑)",
        "items": [
            {"query": "삼성 DDR3 데스크탑 4GB", "capacity": "4GB"},
            {"query": "삼성 DDR3 데스크탑 8GB", "capacity": "8GB"},
        ]
    },
    {
        "category": "DDR5 RAM (노트북)",
        "items": [
            {"query": "삼성 DDR5 노트북 8GB SO-DIMM", "capacity": "8GB"},
            {"query": "삼성 DDR5 노트북 16GB SO-DIMM", "capacity": "16GB"},
            {"query": "삼성 DDR5 노트북 32GB SO-DIMM", "capacity": "32GB"},
        ]
    },
    {
        "category": "DDR4 RAM (노트북)",
        "items": [
            {"query": "삼성 DDR4 노트북 4GB SO-DIMM", "capacity": "4GB"},
            {"query": "삼성 DDR4 노트북 8GB SO-DIMM", "capacity": "8GB"},
            {"query": "삼성 DDR4 노트북 16GB SO-DIMM", "capacity": "16GB"},
            {"query": "삼성 DDR4 노트북 32GB SO-DIMM", "capacity": "32GB"},
        ]
    },
    {
        "category": "DDR3 RAM (노트북)",
        "items": [
            {"query": "삼성 DDR3 노트북 4GB SO-DIMM", "capacity": "4GB"},
            {"query": "삼성 DDR3 노트북 8GB SO-DIMM", "capacity": "8GB"},
        ]
    },
]

# ============================================
# 로깅
# ============================================
def log(msg, level="INFO"):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

# ============================================
# 네이버 쇼핑 API
# ============================================
def search_shopping(query, client_id, client_secret, display=10):
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": display,
        "sort": "asc",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        log(f"API 오류 ({response.status_code}): {response.text}", "ERROR")
        return None

    return response.json()


def get_lowest_price(query, client_id, client_secret):
    result = search_shopping(query, client_id, client_secret)

    if not result or not result.get("items"):
        log(f"  검색 결과 없음: {query}", "WARN")
        return None

    prices = []
    for item in result["items"]:
        try:
            price = int(item["lprice"])
            if price > 0:
                prices.append({
                    "price": price,
                    "title": item["title"].replace("<b>", "").replace("</b>", ""),
                    "mall": item.get("mallName", ""),
                    "link": item.get("link", ""),
                })
        except (ValueError, KeyError):
            continue

    if not prices:
        return None

    prices.sort(key=lambda x: x["price"])
    return prices[0]

# ============================================
# 데이터 수집
# ============================================
def collect_prices(client_id, client_secret):
    log("=" * 50)
    log("📊 RAM 신품 최저가 수집 시작")
    log("=" * 50)

    parsed_data = {}

    for target in RAM_TARGETS:
        category = target["category"]
        parsed_data[category] = []

        log(f"\n📦 카테고리: {category}")

        for item in target["items"]:
            query = item["query"]
            capacity = item["capacity"]

            log(f"  🔍 검색: {query}")
            result = get_lowest_price(query, client_id, client_secret)

            if result:
                ddr_type = "DDR5" if "DDR5" in category else ("DDR4" if "DDR4" in category else "DDR3")
                mem_type = "(노트북)" if "노트북" in category else ""
                product_name = f"삼성 {ddr_type} {capacity} {mem_type}".strip()

                entry = {
                    "product": product_name,
                    "price": result["price"],
                    "price_formatted": f"{result['price']:,}원",
                    "source": result["mall"],
                    "source_title": result["title"],
                    "link": result["link"],
                }
                parsed_data[category].append(entry)
                log(f"  ✅ {product_name}: {result['price']:,}원 ({result['mall']})")
            else:
                log(f"  ⚠️ {query}: 결과 없음", "WARN")

    total = sum(len(items) for items in parsed_data.values())
    log(f"\n수집 완료: {len(parsed_data)} 카테고리, {total} 제품")
    return parsed_data

# ============================================
# 데이터 저장 (ram_new_*.json)
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
            log(f"기존 데이터 로드: {len(full.get('price_history', {}))} 히스토리")
        except Exception as e:
            log(f"기존 파일 로드 실패, 새로 생성: {str(e)}", "WARN")

    history_key = f"{date_str} {time_str}"
    full["price_history"][history_key] = parsed_data

    for category, items in parsed_data.items():
        if category not in full["price_data"]:
            full["price_data"][category] = []

        existing_products = {
            item["product"]: idx
            for idx, item in enumerate(full["price_data"][category])
        }
        for new_item in items:
            prod_name = new_item["product"]
            if prod_name in existing_products:
                full["price_data"][category][existing_products[prod_name]] = new_item
            else:
                full["price_data"][category].append(new_item)

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)

    log(f"✅ 저장 완료: {history_key}")
    return True


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
    log("🚀 RAM 신품 최저가 수집기 (네이버 쇼핑 API)")
    log(f"📅 KST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📂 작업 디렉토리: {BASE_DIR}")
    log("=" * 60)

    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        log("❌ NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수 없음", "ERROR")
        log("GitHub Secrets에 API 키를 등록해주세요", "ERROR")
        return False

    log(f"✅ API 키 확인됨 (ID: {client_id[:4]}...)")

    try:
        parsed_data = collect_prices(client_id, client_secret)

        if not parsed_data or all(len(v) == 0 for v in parsed_data.values()):
            log("❌ 수집된 데이터 없음", "ERROR")
            return False

        today = now.strftime("%Y-%m-%d")
        time_slot = get_current_time_slot()
        save_data(parsed_data, today, time_slot)

        log("=" * 60)
        log("✅ 신품 최저가 수집 완료!")
        log("=" * 60)
        return True

    except Exception as e:
        log(f"❌ 오류: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
