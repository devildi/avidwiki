import cloudscraper
from bs4 import BeautifulSoup

URL = "https://community.avid.com/forums/398.aspx"

def test_connect():
    print(f"Connecting to {URL} using Cloudscraper...")
    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(URL)
        resp.raise_for_status()
        print(f"Status Code: {resp.status_code}")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "No Title"
        print(f"Page Title: {title}")
        
        threads = soup.select("tr") 
        print(f"Found {len(threads)} table rows")

        with open('backend/crawler/debug_page.html', 'w') as f:
            f.write(resp.text)
        print("Saved debug_page.html")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_connect()
