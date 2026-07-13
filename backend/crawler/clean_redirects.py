#!/usr/bin/env python3
import sys
import os
import time
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Add database path
sys.path.append(os.path.join(os.getcwd(), 'backend', 'database'))
sys.path.append(os.path.join(os.getcwd(), 'backend', 'crawler'))
from mongo_client import get_db

def main():
    print("🚀 Connecting to MongoDB...")
    db = get_db()
    sources = list(db.avid_sources.find())
    print(f"📊 Found {len(sources)} sources in database.")

    print("🤖 Initializing Headless Chrome Driver...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(30)

    redirected_count = 0
    deleted_list = []
    
    try:
        for idx, src in enumerate(sources, 1):
            url = src['url']
            name = src.get('display_name', 'Unknown')
            print(f"[{idx}/{len(sources)}] Checking: {name} ({url})...")
            
            try:
                driver.get(url)
                time.sleep(3) # Wait for page load and any redirect scripts
                
                final_url = driver.current_url
                
                parsed_start = urlparse(url)
                parsed_current = urlparse(final_url)
                
                start_path = parsed_start.path.rstrip('/')
                current_path = parsed_current.path.rstrip('/')
                
                if parsed_start.netloc != parsed_current.netloc or start_path != current_path:
                    print(f"  ⚠️ Redirected to: {final_url}")
                    print(f"  🗑️ Deleting from database...")
                    db.avid_sources.delete_one({"url": url})
                    redirected_count += 1
                    deleted_list.append((name, url, final_url))
                else:
                    print("  ✅ OK")
            except Exception as e:
                print(f"  ❌ Error loading {url}: {e}")
                
    finally:
        driver.quit()
        
    print(f"\n🎉 Clean up complete! Removed {redirected_count} redirected data sources:")
    for name, url, target in deleted_list:
        print(f" - {name} ({url}) -> Redirected to: {target}")

if __name__ == "__main__":
    main()
