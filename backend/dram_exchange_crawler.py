"""
DRAM Exchange 크롤링 모듈
"""

import os
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re

def setup_driver():
    """Selenium WebDriver 설정"""
    options = Options()
    if os.environ.get('GITHUB_ACTIONS'):
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    try:
        driver_path = ChromeDriverManager().install()
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"❌ WebDriver 생성 실패: {e}")
        raise

def crawl_dram_exchange():
    """DRAM Exchange 크롤링 실행"""
    driver = None
    try:
        driver = setup_driver()
        print("\n🌐 DRAM Exchange 접속 중...")
        driver.get("https://www.dramexchange.com/")
        time.sleep(5)
        
        results = {}
        
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if not rows:
                rows = driver.find_elements(By.CSS_SELECTOR, "tr")
            
            print(f"📊 발견된 행: {len(rows)}")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells or len(cells) < 3: continue
                    
                    product_cell = cells[0].text.strip()
                    
                    current_category = None
                    if "DDR5" in product_cell: current_category = "DDR5"
                    elif "DDR4" in product_cell: current_category = "DDR4"
                    elif "DDR3" in product_cell: current_category = "DDR3"
                    
                    if not current_category: continue
                    if current_category not in results: results[current_category] = []
                    
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
                    
                except Exception: continue
            
            return {
                "status": "success",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "data": results,
                "count": sum(len(v) for v in results.values())
            }
        
        except Exception as e:
            return {"status": "error", "message": f"테이블 파싱 실패: {e}"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    finally:
        if driver: driver.quit()

def save_dram_data(data, base_dir="."):
    """DRAM Exchange 데이터 저장 (단일 파일 누적 방식)"""
    if data["status"] != "success":
        print(f"❌ 데이터 저장 실패: {data['message']}")
        return False
    
    # ⭐ [핵심] 파일명을 고정합니다.
    filename = "dram_exchange_data.json"
    filepath = os.path.join(base_dir, filename)
    
    # 저장할 데이터 구조
    dram_data = {
        "last_updated": data["timestamp"],
        "current_data": data["data"], # 프론트엔드 키와 맞춤 (current_data)
        "price_history": {}
    }
    
    # ⭐ [핵심] 기존 파일이 있다면 불러와서 히스토리 복원
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            dram_data["price_history"] = existing_data.get("price_history", {})
        except Exception as e:
            print(f"⚠️ 기존 데이터 로드 실패 (새로 생성): {e}")
    
    # 현재 데이터를 히스토리에 추가 (키: 2026-02-07 15:00)
    history_key = data["timestamp"]
    dram_data["price_history"][history_key] = data["data"]
    
    # 파일 덮어쓰기
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(dram_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 데이터 업데이트 완료: {filepath} (총 {len(dram_data['price_history'])}개 시점 데이터)")
    return True

if __name__ == "__main__":
    print("🚀 DRAM Exchange 크롤러 시작")
    data = crawl_dram_exchange()
    if data["status"] == "success":
        save_dram_data(data)
    else:
        print(f"❌ 실패: {data.get('message')}")
