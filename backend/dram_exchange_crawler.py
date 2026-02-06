"""
DRAM Exchange 크롤링 모듈
https://www.dramexchange.com/ 웹페이지에서 RAM 시세 데이터 추출

사용 시간:
- 미국 기준 11:00 (한국 기준 다음날 04:00)
- 미국 기준 14:40 (한국 기준 다음날 07:40)
- 미국 기준 18:10 (한국 기준 다음날 11:10)
"""

import os
import json
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re

# ============================================
# DRAM Exchange 크롤링
# ============================================

def setup_driver():
    """Selenium WebDriver 설정"""
    options = Options()
    
    if os.environ.get('GITHUB_ACTIONS'):
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
    
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    print("📥 webdriver-manager로 ChromeDriver 다운로드 중...")
    try:
        driver_path = ChromeDriverManager().install()
        print(f"✅ ChromeDriver 경로: {driver_path}")
        
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        print("✅ WebDriver 생성 성공")
        return driver
    except Exception as e:
        print(f"❌ WebDriver 생성 실패: {e}")
        raise


def parse_dram_exchange_price(price_str):
    """
    DRAM Exchange 가격 문자열 파싱
    예: "$52.00" → 52.00
    """
    try:
        # $ 기호 제거 및 숫자만 추출
        price = float(re.sub(r'[^0-9.]', '', price_str))
        return price
    except:
        return 0.0


def crawl_dram_exchange():
    """
    DRAM Exchange에서 RAM 시세 데이터 크롤링
    
    Returns:
        dict: {
            "status": "success/error",
            "timestamp": "2026-02-06 11:00",
            "data": {
                "DDR5": [
                    {"product": "DDR5 16Gb (2Gx8) 4800/5600", "high": 52.00, "low": 25.50, ...},
                    ...
                ],
                "DDR4": [...],
                "DDR3": [...]
            }
        }
    """
    driver = None
    try:
        driver = setup_driver()
        
        print("\n🌐 DRAM Exchange 접속 중...")
        driver.get("https://www.dramexchange.com/")
        
        # 페이지 로딩 대기
        print("⏳ 페이지 로딩 중...")
        time.sleep(5)
        
        # 테이블 찾기
        print("🔍 테이블 데이터 추출 중...")
        
        # DDR5, DDR4, DDR3 섹션 찾기
        results = {}
        
        # ⭐ 핵심: 테이블 셀렉터 (DRAM Exchange 구조에 따라 수정 필요)
        try:
            # 방법 1: 테이블 행 찾기
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            if not rows:
                # 방법 2: 테이블 구조가 다른 경우
                rows = driver.find_elements(By.CSS_SELECTOR, "tr")
            
            print(f"📊 발견된 행: {len(rows)}")
            
            current_category = None
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    
                    if not cells or len(cells) < 3:
                        continue
                    
                    # 첫 번째 셀: 제품명
                    product_cell = cells[0].text.strip()
                    
                    # 카테고리 감지
                    if "DDR5" in product_cell:
                        current_category = "DDR5"
                    elif "DDR4" in product_cell:
                        current_category = "DDR4"
                    elif "DDR3" in product_cell:
                        current_category = "DDR3"
                    
                    if not current_category:
                        continue
                    
                    # 카테고리별 데이터 저장
                    if current_category not in results:
                        results[current_category] = []
                    
                    # 가격 데이터 추출 (열 순서: Product, High, Low, Session High, Session Low, Average, Change)
                    try:
                        data_point = {
                            "product": product_cell,
                            "daily_high": float(re.sub(r'[^0-9.]', '', cells[1].text)) if len(cells) > 1 else 0,
                            "daily_low": float(re.sub(r'[^0-9.]', '', cells[2].text)) if len(cells) > 2 else 0,
                            "session_high": float(re.sub(r'[^0-9.]', '', cells[3].text)) if len(cells) > 3 else 0,
                            "session_low": float(re.sub(r'[^0-9.]', '', cells[4].text)) if len(cells) > 4 else 0,
                            "session_average": float(re.sub(r'[^0-9.]', '', cells[5].text)) if len(cells) > 5 else 0,
                            "session_change": cells[6].text.strip() if len(cells) > 6 else "N/A",
                        }
                        
                        results[current_category].append(data_point)
                        print(f"  ✅ {product_cell}: ${data_point['session_average']:.2f}")
                    
                    except Exception as e:
                        print(f"  ⚠️ 데이터 파싱 실패 ({product_cell}): {e}")
                        continue
                
                except Exception as e:
                    continue
            
            print(f"\n✅ 크롤링 완료: {len(results)}개 카테고리")
            
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "data": results,
                "count": sum(len(v) for v in results.values())
            }
        
        except Exception as e:
            print(f"❌ 테이블 파싱 실패: {e}")
            return {
                "status": "error",
                "message": f"테이블 파싱 실패: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
    
    finally:
        if driver:
            driver.quit()
            print("🏁 드라이버 종료")


def save_dram_data(data, base_dir="."):
    """DRAM Exchange 데이터 저장"""
    if data["status"] != "success":
        print(f"❌ 데이터 저장 실패: {data['message']}")
        return False
    
    # 파일명: dram_exchange_2026-02-06_11-00.json
    now = datetime.now()
    filename = f"dram_exchange_{now.strftime('%Y-%m-%d_%H-%M')}.json"
    filepath = os.path.join(base_dir, filename)
    
    # 기존 데이터 로드 (누적용)
    dram_data = {
        "price_data": data["data"],
        "price_history": {}
    }
    
    # 이전 파일들 찾기 (누적 데이터 구조 유지)
    import glob
    files = glob.glob(os.path.join(base_dir, "dram_exchange_*.json"))
    
    if files:
        latest_file = sorted(files)[-1]
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            dram_data["price_history"] = existing_data.get("price_history", {})
        except:
            pass
    
    # 현재 데이터를 히스토리에 추가
    history_key = now.strftime("%Y-%m-%d %H:%M")
    dram_data["price_history"][history_key] = data["data"]
    
    # 파일 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(dram_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 데이터 저장 완료: {filepath}")
    return True


# ============================================
# 테스트 실행
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 DRAM Exchange 크롤러 테스트")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    data = crawl_dram_exchange()
    
    if data["status"] == "success":
        print(f"\n📊 크롤링 결과: {data['count']}개 제품")
        for category, products in data["data"].items():
            print(f"\n  {category}:")
            for p in products[:3]:  # 처음 3개만 출력
                print(f"    - {p['product']}: ${p['session_average']:.2f}")
        
        # 저장
        save_dram_data(data)
    else:
        print(f"\n❌ 크롤링 실패: {data['message']}")
