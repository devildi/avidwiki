from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

def test_selenium():
    print("Initializing Chrome Driver...")
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Try headless first, if blocked remove it
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        url = "https://community.avid.com/forums/398.aspx"
        print(f"Navigating to {url}...")
        driver.get(url)
        
        print("Waiting for cloudflare/page load...")
        time.sleep(5) # Wait for redirects/challenges
        
        print(f"Title: {driver.title}")
        
        # Check for forum rows
        rows = driver.find_elements(By.CSS_SELECTOR, "tr")
        print(f"Found {len(rows)} table rows")
        
        if "Just a moment" in driver.title:
             print("Still blocked by Cloudflare challenge loop?")
        
        driver.quit()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_selenium()
