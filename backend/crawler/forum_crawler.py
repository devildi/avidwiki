import time
import random
import os
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path to allow imports if running from backend/crawler
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database'))
try:
    from db_schema import init_db
    from mongo_client import get_db
except ImportError:
    # Fallback if running from project root
    sys.path.append(os.path.join(os.getcwd(), 'backend', 'crawler'))
    sys.path.append(os.path.join(os.getcwd(), 'backend', 'database'))
    from db_schema import init_db
    from mongo_client import get_db

class AvidCrawler:
    def __init__(self, specific_urls: list = None):
        self.driver = None
        if specific_urls:
            self.source_urls = specific_urls
        else:
            self.source_urls = []
            self.load_settings()
        self.setup_driver()

    def load_settings(self):
        try:
            db = get_db()
            rows = list(db.avid_sources.find({}))
            if rows:
                self.source_urls = [row["url"] for row in rows]
            else:
                self.source_urls = ["https://community.avid.com/forums/398.aspx"]
        except Exception as e:
            print(f"Error loading settings: {e}")
            self.source_urls = ["https://community.avid.com/forums/398.aspx"]
        
    def setup_driver(self):
        """Stable Chrome setup with standard headers to avoid detection."""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Standard User-Agent to avoid generic bot blocks
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Use local driver if possible, but keep it updated
        os.environ['WDM_LOG_LEVEL'] = '0'
        
        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(60) # Back to stable timeout
        
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

    def interruptible_sleep(self, seconds, stop_event=None):
        """Sleep for X seconds, but check stop_event every 0.5s for immediate interruption."""
        if not stop_event:
            time.sleep(seconds)
            return False
            
        end_time = time.time() + seconds
        while time.time() < end_time:
            if stop_event.is_set():
                return True # Interrupted
            time.sleep(0.5)
        return False

    def check_for_captcha(self, max_wait_seconds=30):
        """Check if the page is showing a CAPTCHA/verification challenge."""
        captcha_indicators = [
            "cloudflare", "captcha", "verify you are human",
            "human verification", "security check", "are you a human", "just a moment"
        ]

        try:
            page_source = self.driver.page_source.lower()
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
        except:
            return False

        for indicator in captcha_indicators:
            if indicator in page_source or indicator in page_text:
                print(f"\n🤖 CAPTCHA/Verification detected! Waiting for manual completion...")
                for i in range(max_wait_seconds):
                    time.sleep(1)
                    try:
                        curr_source = self.driver.page_source.lower()
                        if not any(ind in curr_source for ind in captcha_indicators):
                            print(f"✅ Verification completed!")
                            time.sleep(2)
                            return True
                    except:
                        pass
                return True
        return False
        
    def run(self, stop_event=None, log_callback=None):
        import re
        
        def log(msg, type="log", data=None):
            if log_callback:
                log_callback(msg, type=type, data=data)
            else:
                print(msg)

        try:
            log("🚀 Initializing Database...")
            init_db()
            db = get_db()
            processed_count = 0

            for start_url in self.source_urls:
                if stop_event and stop_event.is_set():
                    log("🛑 Crawl stopped by user.")
                    break

                log(f"🎬 Starting crawl for source: {start_url}")
                
                source_record = db.avid_sources.find_one({"url": start_url})
                resume_page = source_record.get("current_page", 1) if source_record else 1
                
                max_pages_on_web = 500
                should_continue = True

                try:
                    self.driver.get(start_url)
                    self.interruptible_sleep(3, stop_event)
                    self.check_for_captcha(max_wait_seconds=60)
                    
                    # 检查是否发生跳转，并永久删除跳转的源
                    from urllib.parse import urlparse
                    parsed_start = urlparse(start_url)
                    parsed_current = urlparse(self.driver.current_url)
                    
                    start_path = parsed_start.path.rstrip('/')
                    current_path = parsed_current.path.rstrip('/')
                    
                    if parsed_start.netloc != parsed_current.netloc or start_path != current_path:
                        log(f"⚠️ 检测到数据源发生跳转: {start_url} -> {self.driver.current_url}")
                        log(f"🗑️ 正在从数据库中永久删除该源。")
                        db.avid_sources.delete_one({"url": start_url})
                        continue
                    
                    # Extract total pages
                    try:
                        paging_area = self.driver.find_element(By.CSS_SELECTOR, ".CommonPagingArea")
                        match = re.search(r'Page \d+ of (\d+)', paging_area.text)
                        if match:
                            max_pages_on_web = int(match.group(1))
                            log(f"  📊 Total pages on web: {max_pages_on_web}")
                    except:
                        log("  ⚠️ Could not determine total page count, using default limit.")
                except Exception as e:
                    log(f"⚠️ Initial page load error: {e}")
                    continue

                # Define the sequence of pages to crawl: Page 1 ALWAYS first, then resume from resume_page
                pages_to_crawl = [1]
                if resume_page > 1:
                    # If resume_page is valid and not 1, add it and subsequent pages
                    start_resume = resume_page
                    if start_resume <= max_pages_on_web:
                        pages_to_crawl.extend(range(start_resume, max_pages_on_web + 1))
                    else:
                        log(f"  ℹ️ Resume page {resume_page} exceeds total pages {max_pages_on_web}. Finishing backlog.")
                else:
                    # Normal flow from page 2 onwards
                    if max_pages_on_web >= 2:
                        pages_to_crawl.extend(range(2, max_pages_on_web + 1))

                def get_page_url(base_url, page_num):
                    if "?" in base_url:
                        return f"{base_url}&PageIndex={page_num}"
                    else:
                        return f"{base_url}?PageIndex={page_num}"

                for current_page in pages_to_crawl:
                    if stop_event and stop_event.is_set():
                        db.avid_sources.update_one({"url": start_url}, {"$set": {"current_page": current_page}})
                        log(f"  💾 Progress saved: Page {current_page}")
                        break

                    # Extra log for clarity on the priority scan
                    if current_page == 1 and resume_page > 1:
                        log(f"📄 Processing Page 1 (Priority Scan for new items)...")
                    else:
                        log(f"📄 Processing Page {current_page}/{max_pages_on_web}...")
                    
                    target_url = get_page_url(start_url, current_page)
                    
                    max_retries = 5
                    success = False
                    for attempt in range(1, max_retries + 1):
                        if stop_event and stop_event.is_set():
                            break
                        try:
                            self.driver.get(target_url)
                            self.interruptible_sleep(5, stop_event)
                            self.check_for_captcha(max_wait_seconds=30)
                            log(f"  🌐 Title: {self.driver.title}")
                            success = True
                            break
                        except Exception as e:
                            log(f"  ⚠️ Attempt {attempt}/{max_retries} failed to load Page {current_page}: {e}")
                            if attempt < max_retries:
                                # Exponential backoff: 2s, 4s, 8s, 16s...
                                if self.interruptible_sleep(2 ** attempt, stop_event):
                                    break
                    
                    if not success:
                        log(f"  ❌ Failed to load Page {current_page} after {max_retries} attempts. Skipping this topic.")
                        break

                    # 1. Extract Thread Data
                    thread_info_list = []
                    try:
                        # Try to find rows with different possible selectors
                        rows = self.driver.find_elements(By.CSS_SELECTOR, "tr[class*='CommonListRow']")
                        
                        if not rows:
                            # Fallback: search for any rows in a table that might be the list
                            rows = self.driver.find_elements(By.CSS_SELECTOR, ".CommonListArea tr")
                        
                        if not rows:
                            # Final diagnostic: log what we DO see
                            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:200].replace("\n", " ")
                            log(f"  ⚠️ No rows found. Page snippet: {body_text}")

                        for row in rows:
                            try:
                                links = row.find_elements(By.CSS_SELECTOR, "a.ForumName, a.ForumNameUnRead")
                                date_el = row.find_elements(By.CSS_SELECTOR, ".ForumLastPost")
                                if links:
                                    link = links[0]
                                    url = link.get_attribute("href")
                                    title = link.text
                                    last_post_date = ""
                                    if date_el:
                                        text = date_el[0].text.strip()
                                        parts = text.split(',')
                                        last_post_date = ','.join(parts[1:]).strip()
                                    if url and title:
                                        thread_info_list.append({"url": url, "title": title, "last_post_date": last_post_date})
                            except:
                                continue
                    except Exception as e:
                        log(f"  ❌ Error finding thread links: {e}")
                        break

                    if not thread_info_list:
                        log(f"  ⚠️ No threads found on Page {current_page}. (Empty or block?)")
                        if current_page >= max_pages_on_web:
                            db.avid_sources.update_one({"url": start_url}, {"$set": {"current_page": 1}})
                            break
                        else:
                            current_page += 1
                            continue

                    # 2. Process threads
                    for t in thread_info_list:
                        if stop_event and stop_event.is_set():
                            break

                        url, title, last_post_date = t['url'], t['title'], t['last_post_date']
                        row_data = db.avid.find_one({"url": url}, {"last_post_date": 1})

                        if row_data and row_data.get("last_post_date") == last_post_date:
                            continue
                        
                        log(f"  🆕 Processing: {title[:50]}...")
                        self.scrape_thread(url, title, db, last_post_date, start_url, stop_event=stop_event)
                        
                        processed_count += 1
                        log(f"Progress update", type="progress", data={"current": processed_count, "total": processed_count + 20})
                        if self.interruptible_sleep(random.uniform(2, 4), stop_event): break

                    # 3. Increment Page
                    db.avid_sources.update_one({"url": start_url}, {"$set": {"current_page": current_page + 1}})

                # Update last_updated timestamp after each source
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                db.avid_sources.update_one({"url": start_url}, {"$set": {"last_updated": now_str}})

            log("✅ All sources processed.")
        except Exception as e:
            log(f"❌ Crawler crashed: {e}")
        finally:
            if self.driver:
                self.driver.quit()

    def scrape_thread(self, url, title, db, last_post_date_on_list, source_url, stop_event=None):
        if stop_event and stop_event.is_set():
            return
        max_retries = 5
        success = False
        for attempt in range(1, max_retries + 1):
            if stop_event and stop_event.is_set():
                return
            try:
                self.driver.get(url)
                self.interruptible_sleep(3, stop_event)
                success = True
                break
            except Exception as e:
                print(f"  ⚠️ Attempt {attempt}/{max_retries} failed to load thread details: {e}")
                if attempt < max_retries:
                    if self.interruptible_sleep(2 ** attempt, stop_event):
                        return
        
        if not success:
            print(f"  ❌ Failed to load thread details after {max_retries} attempts.")
            return

        # 检查主题页是否发生跳转（例如跳转到登录页或已删除提示页），若跳转则跳过该主题
        from urllib.parse import urlparse
        parsed_start = urlparse(url)
        parsed_current = urlparse(self.driver.current_url)
        
        start_path = parsed_start.path.rstrip('/')
        current_path = parsed_current.path.rstrip('/')
        
        if parsed_start.netloc != parsed_current.netloc or start_path != current_path:
            print(f"  ⚠️ 发现主题帖发生跳转: {url} -> {self.driver.current_url}，已跳过。")
            return

        try:
            bodies = self.driver.find_elements(By.CSS_SELECTOR, "div.ForumPostContentText")
            if not bodies:
                bodies = self.driver.find_elements(By.CSS_SELECTOR, "td.ForumPostContentArea")

            question_content = bodies[0].text if bodies else ""
            now = datetime.now().isoformat()
            db.avid.update_one(
                {"url": url},
                {"$set": {
                    "title": title,
                    "question_content": question_content,
                    "last_post_date": last_post_date_on_list,
                    "scraped_at": now,
                    "source_url": source_url,
                    "is_vectorized": False
                }},
                upsert=True
            )
        except Exception as e:
            print(f"  ⚠️ Error scraping thread content {url}: {e}")

if __name__ == "__main__":
    crawler = AvidCrawler()
    crawler.run()
