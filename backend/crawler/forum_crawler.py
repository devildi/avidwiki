import time
import sqlite3
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
try:
    from db_schema import init_db
except ImportError:
    # Fallback if running from project root
    sys.path.append(os.path.join(os.getcwd(), 'backend', 'crawler'))
    from db_schema import init_db

DB_PATH = os.getenv("DATABASE_PATH", "backend/crawler/forums.db")
# Fallback path logic
if not os.path.exists(os.path.dirname(DB_PATH)):
    DB_PATH = os.getenv("DATABASE_PATH", "forums.db")

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
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT url FROM sources")
            rows = c.fetchall()
            if rows:
                self.source_urls = [row[0] for row in rows]
            else:
                self.source_urls = ["https://community.avid.com/forums/398.aspx"]
            conn.close()
        except:
            self.source_urls = ["https://community.avid.com/forums/398.aspx"]
        
    def setup_driver(self):
        options = webdriver.ChromeOptions()
        # Comment out headless mode to allow manual verification if needed
        # options.add_argument('--headless') # Run headless for speed
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        self.driver.set_page_load_timeout(60)  # Increased timeout
        self.driver.set_script_timeout(60)

        # Execute script to hide webdriver property
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

    def check_for_captcha(self, max_wait_seconds=30):
        """
        Check if the page is showing a CAPTCHA/verification challenge.
        Wait for user to complete it manually if detected.
        Returns True if CAPTCHA was detected and (presumably) completed.
        """
        import re

        captcha_indicators = [
            "cloudflare",
            "captcha",
            "verify you are human",
            "human verification",
            "security check",
            "are you a human",
            "just a moment"
        ]

        page_source = self.driver.page_source.lower()
        page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()

        for indicator in captcha_indicators:
            if indicator in page_source or indicator in page_text:
                print(f"\n🤖 🤖 🤖  CAPTCHA/Verification detected! 🤖 🤖 🤖")
                print(f"🔒 Please complete the verification in the browser window.")
                print(f"⏳ Waiting for up to {max_wait_seconds} seconds...")

                # Wait for the CAPTCHA to be completed
                for i in range(max_wait_seconds):
                    time.sleep(1)

                    # Check if CAPTCHA is still present
                    current_page_source = self.driver.page_source.lower()
                    current_page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()

                    # Check if any indicator is still present
                    captcha_still_present = any(
                        ind in current_page_source or ind in current_page_text
                        for ind in captcha_indicators
                    )

                    if not captcha_still_present:
                        print(f"✅ Verification completed! Continuing crawl...")
                        time.sleep(2)  # Extra wait to ensure page is fully loaded
                        return True

                    # Progress indicator
                    if (i + 1) % 5 == 0:
                        print(f"⏳ Still waiting... {i + 1}/{max_wait_seconds} seconds")

                print(f"⚠️ Timed out waiting for verification. Will try to continue...")
                return True  # Assume completed and try to continue

        return False  # No CAPTCHA detected
        
    def run(self, stop_event=None, log_callback=None):
        import re
        
        def log(msg, type="log", data=None):
            if log_callback:
                log_callback(msg, type=type, data=data)
            else:
                print(msg)

        try:
            log("🚀 Initializing Database...")
            init_db() # Ensure tables exist
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            processed_count = 0

            for start_url in self.source_urls:
                if stop_event and stop_event.is_set():
                    log("🛑 Crawl stopped by user.")
                    break

                log(f"🎬 Starting crawl for source: {start_url}")
                try:
                    self.driver.get(start_url)
                except Exception as e:
                    log(f"⚠️ Initial page load error: {e}")

                if stop_event and stop_event.is_set():
                    log("🛑 Crawl stopped by user after initial load.")
                    break

                # Check for CAPTCHA/verification after initial page load
                if stop_event and stop_event.is_set():
                    break

                log("🔍 Checking for CAPTCHA/verification...")
                self.check_for_captcha(max_wait_seconds=60)  # Wait up to 60 seconds for manual verification

                if stop_event and stop_event.is_set():
                    log("🛑 Crawl stopped by user during CAPTCHA wait.")
                    break
                
                # --- NEW: Extract Total Count ---
                total_items = 0
                try:
                    paging_area = self.driver.find_element(By.CSS_SELECTOR, ".CommonPagingArea")
                    paging_text = paging_area.text
                    # Pattern: "Page 1 of 1870 (37386 items) 1"
                    match = re.search(r'\((\d+)\s+items\)', paging_text)
                    if match:
                        total_items = int(match.group(1))
                        log(f"📊 Total items found: {total_items}", type="progress", data={"current": 0, "total": total_items})
                except Exception as paging_err:
                    log(f"⚠️ Could not extract total count: {paging_err}")

                current_page = 1
                max_pages_per_source = 20 # Increased to cover more pages (was 3)
                consecutive_empty_pages = 0 # Track how many pages in a row have no threads
                max_empty_pages = 3 # Stop after 3 consecutive empty pages

                while current_page <= max_pages_per_source:
                    if stop_event and stop_event.is_set():
                        log("🛑 Crawl stopped by user while switching page.")
                        break

                    log(f"📄 Processing Page {current_page} - {self.driver.current_url}")

                    # Wait for page to load (especially important for page 2+)
                    # Increased wait time to ensure dynamic content is loaded
                    time.sleep(5)

                    # 1. Get Thread Links
                    thread_links = []
                    try:
                        # Target the second CommonListArea (the Topics section)
                        # The first one is usually announcements/pinned posts
                        areas = self.driver.find_elements(By.CSS_SELECTOR, ".CommonListArea")
                        log(f"  🔍 Found {len(areas)} CommonListArea elements on page {current_page}")

                        if len(areas) >= 2:
                            # Find the table inside the second CommonListArea
                            # then get all rows from that table
                            tables = areas[1].find_elements(By.TAG_NAME, "table")
                            log(f"  🔍 Found {len(tables)} table(s) in second CommonListArea")

                            if tables:
                                all_rows = tables[0].find_elements(By.TAG_NAME, "tr")
                                log(f"  🔍 Table has {len(all_rows)} total rows")

                                # Log class names of first few rows for debugging
                                for i, row in enumerate(all_rows[:5]):
                                    row_class = row.get_attribute("class") or "no-class"
                                    log(f"    Row {i} class: '{row_class}'")

                                # Filter rows that have CommonListRow or CommonListRowAlt class (may have multiple classes)
                                rows = []
                                for row in all_rows:
                                    class_attr = row.get_attribute("class") or ""
                                    # Check for both CommonListRow and CommonListRowAlt class patterns
                                    if "CommonListRow" in class_attr:
                                        rows.append(row)
                                log(f"  Found {len(rows)} potential rows (including CommonListRow and CommonListRowAlt) in the table of the second CommonListArea (out of {len(all_rows)} total rows).")
                            else:
                                # Fallback: try direct selector that matches both CommonListRow and CommonListRowAlt
                                rows = areas[1].find_elements(By.CSS_SELECTOR, "tr[class*='CommonListRow']")
                                log(f"  Found {len(rows)} potential rows using fallback selector.")
                        else:
                            rows = self.driver.find_elements(By.CSS_SELECTOR, ".CommonListArea tr[class*='CommonListRow']")
                            log(f"  Found {len(rows)} potential rows.")

                        # Additional debug: check if page has content at all
                        page_source_length = len(self.driver.page_source)
                        log(f"  📏 Page source length: {page_source_length} chars")
                        
                        for row in rows:
                            try:
                                links = row.find_elements(By.CSS_SELECTOR, "a.ForumName, a.ForumNameUnRead")
                                date_el = row.find_elements(By.CSS_SELECTOR, ".ForumLastPost")
                                
                                if links:
                                    link = links[0]
                                    url = link.get_attribute("href")
                                    title = link.text
                                    
                                    # Extract date info for incremental check
                                    last_post_date = ""
                                    if date_el:
                                        text = date_el[0].text.strip()
                                        parts = text.split(',')
                                        # Result: "Jan 12 2024 4:00 PM" (omits the username part)
                                        last_post_date = ','.join(parts[1:]).strip() 
                                    
                                    if url and title:
                                        thread_links.append((url, title, last_post_date))
                            except:
                                continue
                    except Exception as e:
                        log(f"Error finding thread links: {e}")

                    log(f"Found {len(thread_links)} threads on this page.")

                    # If no threads found on this page, try next page instead of stopping
                    if len(thread_links) == 0:
                        consecutive_empty_pages += 1
                        log(f"  ⚠️ No threads found on page {current_page}. (Consecutive empty pages: {consecutive_empty_pages}/{max_empty_pages})")

                        if consecutive_empty_pages >= max_empty_pages:
                            log(f"  🛑 {max_empty_pages} consecutive pages with no threads. Stopping crawl.")
                            break

                        # Try next page
                        current_page += 1
                        try:
                            # Find and click the page number link instead of "Next >"
                            # Look for the page number in the paging area
                            paging_area = self.driver.find_element(By.CSS_SELECTOR, ".CommonPagingArea")
                            # Find link with text matching the next page number
                            next_page_link = paging_area.find_element(By.XPATH, f".//a[contains(text(), '{current_page}')]")
                            if next_page_link:
                                self.driver.execute_script("arguments[0].scrollIntoView();", next_page_link)
                                next_page_link.click()
                                time.sleep(random.uniform(3, 5))

                                # Check for CAPTCHA after page change
                                log(f"🔍 Checking for CAPTCHA after navigating to page {current_page}...")
                                if self.check_for_captcha(max_wait_seconds=30):
                                    log(f"✅ Page {current_page} loaded successfully after verification check")

                                continue
                            else:
                                log(f"Page {current_page} link not found. Source complete.")
                                break
                        except:
                            log(f"Page {current_page} link not found (or end of list). Source complete.")
                            break

                    # Reset counter if we found threads
                    consecutive_empty_pages = 0

                    # 2. Process each thread
                    unchanged_count = 0
                    all_unchanged_on_page = True # Track if entire page is unchanged

                    for url, title, last_post_date in thread_links:
                        if stop_event and stop_event.is_set():
                            log("🛑 Crawl stopped by user.")
                            break

                        # Check database
                        c.execute("SELECT id, last_post_date FROM threads WHERE url = ?", (url,))
                        row_data = c.fetchone()

                        # Backfill source_url for ALL threads (unchanged or new)
                        try:
                            c.execute("UPDATE threads SET source_url = ? WHERE url = ?", (start_url, url))
                            conn.commit()
                        except Exception as update_e:
                            log(f"  ⚠️ Failed to backfill source_url: {update_e}")

                        if row_data:
                            db_last_date = row_data[1]
                            if db_last_date == last_post_date:
                                log(f"  ⏭️ 没有更新 (Last Post: {last_post_date}): {title[:30]}...")
                                unchanged_count += 1
                                processed_count += 1
                                log(f"Progress update", type="progress", data={"current": processed_count, "total": total_items})
                                continue
                            else:
                                log(f"  🆕 发现新回复! ({db_last_date} -> {last_post_date})")
                                all_unchanged_on_page = False

                        log(f"  🔍 Scraping: {title[:50]}...")
                        self.scrape_thread(url, title, c, last_post_date, start_url, stop_event=stop_event)
                        all_unchanged_on_page = False # At least one thread was processed

                        if stop_event and stop_event.is_set():
                            log("🛑 Task cancelled after scraping thread.")
                            break

                        processed_count += 1
                        log(f"Progress update", type="progress", data={"current": processed_count, "total": total_items})

                        conn.commit()
                        log(f"  ✅ Topic: {title}")
                        time.sleep(random.uniform(1, 4)) # Polite delay

                    # If entire page is unchanged (all threads already in DB), check if we should stop
                    if all_unchanged_on_page and len(thread_links) > 0:
                        # Check Total vs Local count
                        should_continue = False
                        if total_items > 0:
                            try:
                                c.execute("SELECT COUNT(*) FROM threads WHERE source_url = ?", (start_url,))
                                local_count = c.fetchone()[0]
                                log(f"  📊 Local Count: {local_count} / Web Total: {total_items}")
                                
                                # If we have fewer items locally than on web, we might be missing old threads
                                # Allow a buffer (e.g. 5) for sticky threads or deleted items
                                if local_count < (total_items - 5):
                                    log(f"  ⚠️ Local data incomplete ({local_count} < {total_items}). Continuing crawl to find older threads...")
                                    should_continue = True
                            except Exception as count_e:
                                log(f"  ⚠️ Failed to check local count: {count_e}")

                        if not should_continue:
                            log(f"  ✅ 当前页所有 {len(thread_links)} 条都已在数据库中且无更新，且数据量似乎完整，停止本源爬取。")
                            break

                    # 3. Next Page
                    try:
                        # Find and click the page number link instead of "Next >"
                        # Look for the page number in the paging area
                        paging_area = self.driver.find_element(By.CSS_SELECTOR, ".CommonPagingArea")
                        # Calculate next page number
                        next_page_num = current_page + 1
                        # Find link with text matching the next page number
                        next_page_link = paging_area.find_element(By.XPATH, f".//a[contains(text(), '{next_page_num}')]")
                        if next_page_link:
                            self.driver.execute_script("arguments[0].scrollIntoView();", next_page_link)
                            next_page_link.click()
                            current_page += 1
                            time.sleep(random.uniform(3, 5))

                            # Check for CAPTCHA after page change
                            log(f"🔍 Checking for CAPTCHA after navigating to page {current_page}...")
                            if self.check_for_captcha(max_wait_seconds=30):
                                log(f"✅ Page {current_page} loaded successfully after verification check")
                        else:
                            log(f"Page {next_page_num} link not found. Source complete.")
                            break
                    except:
                        log(f"Page {current_page + 1} link not found (or end of list). Source complete.")
                        break
            
                # Update last_updated in sources for this specific URL
                if not (stop_event and stop_event.is_set()):
                    try:
                        conn_settings = sqlite3.connect(DB_PATH)
                        c_settings = conn_settings.cursor()
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        c_settings.execute("UPDATE sources SET last_updated = ? WHERE url = ?", (now_str, start_url))
                        conn_settings.commit()
                        conn_settings.close()
                    except Exception as update_err:
                        log(f"  ⚠️ Failed to update timestamp for {start_url}: {update_err}")
            
            conn.close()
            
        except Exception as e:
            log(f"❌ Crawler crashed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                self.driver.quit()
            print("✅ Crawler workflow finished.")

    def scrape_thread(self, url, title, cursor, last_post_date_on_list, source_url, stop_event=None):
        if stop_event and stop_event.is_set():
            return

        # Open new tab
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        
        try:
            if stop_event and stop_event.is_set():
                return

            self.driver.get(url)
            time.sleep(3)
            
            if stop_event and stop_event.is_set():
                return

            # Selectors based on inspection
            authors = self.driver.find_elements(By.CSS_SELECTOR, "td.ForumPostUserArea a")
            bodies = self.driver.find_elements(By.CSS_SELECTOR, "div.ForumPostContentText")
            headers = self.driver.find_elements(By.CSS_SELECTOR, "h4.ForumPostHeader") # Contains date
            
            if not bodies:
                # Fallback selector just in case
                bodies = self.driver.find_elements(By.CSS_SELECTOR, "td.ForumPostContentArea")

            post_count = min(len(authors), len(bodies))
            
            # Extract the original question content (first post)
            question_content = bodies[0].text if bodies else ""
            
            # Insert Thread
            now = datetime.now().isoformat()
            # Use INSERT OR REPLACE to update last_post_date and source_url for existing threads
            cursor.execute('''INSERT OR REPLACE INTO threads 
                (id, title, url, question_content, last_post_date, scraped_at, source_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (url, title, url, question_content, last_post_date_on_list, now, source_url))
            
            # We only care about the first post (question_content) for now per user request.
            # Commeting out the loop that processes every reply/post.
            """
            for i in range(post_count):
                if stop_event and stop_event.is_set():
                    break

                author = authors[i].text
                content = bodies[i].text
                date_str = headers[i].text if i < len(headers) else ""
                
                is_op = (i == 0)
                
                # Use INSERT OR IGNORE with the new UNIQUE constraint to only add new posts
                cursor.execute('''INSERT OR IGNORE INTO posts 
                    (thread_id, author, content, post_date, is_op) 
                    VALUES (?, ?, ?, ?, ?)''',
                    (url, author, content, date_str, is_op))
            """
            
            print(f"  📝 {title} 详情已完成")
                    
        except Exception as e:
            print(f"  ⚠️ Error scraping thread {url}: {e}")
        finally:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

if __name__ == "__main__":
    crawler = AvidCrawler()
    crawler.run()
