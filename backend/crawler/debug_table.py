import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

def debug_page_structure(url):
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    try:
        print(f"Loading page: {url}")
        driver.get(url)
        time.sleep(5)

        # Find all CommonListArea elements
        areas = driver.find_elements(By.CSS_SELECTOR, ".CommonListArea")
        print(f"\nFound {len(areas)} CommonListArea elements")

        for idx, area in enumerate(areas):
            print(f"\n=== CommonListArea #{idx} ===")
            print(f"HTML tag: {area.tag_name}")
            print(f"Class: {area.get_attribute('class')}")

            # Check if it has a table
            tables = area.find_elements(By.TAG_NAME, "table")
            print(f"Tables inside: {len(tables)}")

            if tables:
                table = tables[0]
                print(f"Table class: {table.get_attribute('class')}")

                # Try to find rows with different selectors
                rows_selector1 = table.find_elements(By.CSS_SELECTOR, "tr.CommonListRow")
                rows_selector2 = table.find_elements(By.CSS_SELECTOR, "tr")
                rows_selector3 = area.find_elements(By.CSS_SELECTOR, "tr.CommonListRow")

                print(f"\nRows with 'tr.CommonListRow' (from table): {len(rows_selector1)}")
                print(f"Rows with 'tr' (from table): {len(rows_selector2)}")
                print(f"Rows with 'tr.CommonListRow' (from area): {len(rows_selector3)}")

                # Show first few row classes
                if rows_selector2:
                    print(f"\nFirst 5 row classes:")
                    for i, row in enumerate(rows_selector2[:5]):
                        classes = row.get_attribute('class')
                        print(f"  Row {i}: class='{classes}'")

        # Specifically check second CommonListArea
        if len(areas) >= 2:
            print(f"\n\n=== DETAILED ANALYSIS OF SECOND CommonListArea ===")
            area = areas[1]

            # Try different approaches
            print("\nApproach 1: area.find_elements(By.CSS_SELECTOR, 'tr.CommonListRow')")
            rows1 = area.find_elements(By.CSS_SELECTOR, "tr.CommonListRow")
            print(f"  Found: {len(rows1)} rows")

            print("\nApproach 2: Find table first, then rows")
            tables = area.find_elements(By.TAG_NAME, "table")
            if tables:
                table = tables[0]
                rows2 = table.find_elements(By.TAG_NAME, "tr")
                print(f"  Found: {len(rows2)} rows in table")

                # Count rows with CommonListRow class
                rows_with_class = [r for r in rows2 if "CommonListRow" in r.get_attribute("class")]
                print(f"  Of those, {len(rows_with_class)} have 'CommonListRow' class")

            print("\nApproach 3: Direct CSS selector from driver")
            rows3 = driver.find_elements(By.CSS_SELECTOR, ".CommonListArea:nth-of-type(2) tr.CommonListRow")
            print(f"  Found: {len(rows3)} rows")

        # Save page source for inspection
        with open("/Users/DevilDI/Desktop/projects/wiki/backend/crawler/page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("\nPage source saved to: backend/crawler/page_source.html")

    finally:
        driver.quit()
        print("\nBrowser closed.")

if __name__ == "__main__":
    # Test with page 2 (the one that only found 6 rows)
    debug_page_structure("https://community.avid.com/forums/398.aspx?PageIndex=2&forumoptions=0:1:11::")
