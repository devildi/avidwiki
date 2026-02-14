import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import sys

def test():
    print("Initializing options...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    print("Installing ChromeDriver...")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(30)
    
    url = "https://community.avid.com/forums/398.aspx"
    print(f"Navigating to {url}...")
    start_time = time.time()
    try:
        driver.get(url)
        print(f"Success! Page loaded in {time.time() - start_time:.2f} seconds")
        print(f"Title: {driver.title}")
    except Exception as e:
        print(f"Failed! Error after {time.time() - start_time:.2f} seconds: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test()
