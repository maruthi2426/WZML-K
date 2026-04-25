"""
Vegamovies Direct Link Scraper v2.0
Fast scraper to extract direct download links from Vegamovies movie URLs
Supports quality filtering and both movie and series content
"""

import sys
import re
import time
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    from bs4 import BeautifulSoup
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "-q"])
        from bs4 import BeautifulSoup
    except:
        BeautifulSoup = None

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver-manager", "-q"])
        from webdriver_manager.chrome import ChromeDriverManager
    except:
        ChromeDriverManager = None


class VegamoviesScraper:
    def __init__(self):
        self.driver = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    def _create_driver(self):
        """Create optimized Chrome WebDriver for scraping"""
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--blink-settings=imagesEnabled=false")
            options.add_argument("--log-level=3")
            options.add_argument("--disable-web-resources")
            options.page_load_strategy = "eager"
            
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
            })

            if ChromeDriverManager:
                return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            else:
                return webdriver.Chrome(options=options)
        except Exception as e:
            print(f"[ERROR] Failed to create WebDriver: {str(e)}")
            raise

    def _load_page(self, url):
        """Load Vegamovies page with JavaScript rendering"""
        print(f"[INFO] Loading page: {url}")
        try:
            self.driver.get(url)
            time.sleep(1)
            
            # Scroll to load all content
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
            
            time.sleep(1)
            html = self.driver.page_source
            print(f"[INFO] Page loaded successfully")
            return html
        except Exception as e:
            print(f"[ERROR] Failed to load page: {str(e)}")
            raise

    def _normalize_quality(self, quality_str):
        """Normalize quality string for comparison"""
        if not quality_str:
            return "unknown"
        q = quality_str.upper().strip()
        q = re.sub(r'\s+', '', q)
        return q

    def _extract_episode(self, text, url_slug=""):
        """Extract episode number from text or URL"""
        if url_slug:
            slug_match = re.search(r'ep[-_]0*(\d{1,3})', url_slug.lower())
            if slug_match:
                return f"EP{slug_match.group(1).zfill(2)}"

        if text:
            patterns = [
                r'ep[-_:\s]*0*(\d{1,3})',
                r'episode[-_:\s]*0*(\d{1,3})',
                r'e(\d{2,3})\b',
            ]
            for pattern in patterns:
                match = re.search(pattern, text.lower())
                if match:
                    return f"EP{match.group(1).zfill(2)}"
        
        return "EP01"

    def scrape(self, url, quality_filter=None):
        """Main scraping function"""
        start_time = time.time()
        print(f"\n{'='*80}")
        print(f"[INFO] VEGAMOVIES SCRAPER v2.0")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality Filter: {quality_filter}")
        print(f"{'='*80}\n")

        self.driver = self._create_driver()
        results = []

        try:
            # Load page
            html = self._load_page(url)
            soup = BeautifulSoup(html, "lxml")

            # Extract page info
            title_tag = soup.find("title")
            raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            clean_title = re.sub(r'\s*\|\s*Vegamovies.*$', '', raw_title, flags=re.I).strip()
            clean_title = re.sub(r'^Download\s+', '', clean_title, flags=re.I).strip()
            clean_title = re.sub(r'\s+', ' ', clean_title)
            
            show_name = re.sub(r'\s*Season\s*\d+.*|EP.*', '', clean_title, flags=re.I).strip()
            season_match = re.search(r'Season\s*0*(\d+)', clean_title, re.I)
            season = season_match.group(1).zfill(2) if season_match else "01"

            print(f"[INFO] Title: {show_name}")
            print(f"[INFO] Season: S{season}\n")

            # Find all download links
            all_links = []
            current_quality = "unknown"
            current_size = "unknown"

            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p', 'a']):
                text = element.get_text(strip=True)
                
                # Check for quality
                quality_match = re.search(r'(480p|720p|1080p|4k|2160p|HQ\s+1080p)', text, re.I)
                if quality_match:
                    current_quality = quality_match.group(0).upper()
                    size_match = re.search(r'(\d+\.?\d*)\s*(GB|MB)', text, re.I)
                    if size_match:
                        current_size = f"{size_match.group(1)} {size_match.group(2)}".upper()
                    continue

                # Check for links
                if element.name == "a" and element.has_attr("href"):
                    href = urljoin(url, element["href"])
                    link_text = element.get_text(strip=True)
                    
                    # Check if it's a shortener link (nexdrive, fast-dl, etc)
                    if any(x in href.lower() for x in ["nexdrive", "fast-dl", "bit.ly", "tinyurl", "short"]):
                        episode = self._extract_episode(link_text, href)
                        all_links.append({
                            "url": href,
                            "quality": current_quality,
                            "size": current_size,
                            "episode": episode,
                            "text": link_text
                        })

            print(f"[INFO] Found {len(all_links)} shortener link(s)")

            # Filter by quality if specified
            if quality_filter:
                norm_filter = self._normalize_quality(quality_filter)
                filtered = [l for l in all_links if self._normalize_quality(l["quality"]) == norm_filter]
                if filtered:
                    all_links = filtered[:1]  # Use only first matching quality
                    print(f"[INFO] Quality filter applied - using {len(all_links)} link(s)")
                else:
                    print(f"[WARNING] No links found for quality: {quality_filter}")

            # Resolve each shortener link to get direct download link
            if all_links:
                print(f"[INFO] Resolving shortener links...\n")
                for idx, link_info in enumerate(all_links, 1):
                    try:
                        print(f"[{idx}/{len(all_links)}] Processing {link_info['quality']} - {link_info['episode']}")
                        print(f"     Shortener: {link_info['url'][:70]}...")
                        
                        direct_link = self._resolve_shortener(link_info["url"])
                        
                        if direct_link:
                            results.append({
                                "show_name": show_name,
                                "season": season,
                                "episode": link_info["episode"],
                                "quality": link_info["quality"],
                                "size": link_info["size"],
                                "url": direct_link
                            })
                            print(f"     ✓ Direct Link: {direct_link[:70]}...\n")
                        else:
                            print(f"     ✗ Failed to resolve link\n")
                    except Exception as e:
                        print(f"     ✗ Error: {str(e)}\n")

            elapsed = time.time() - start_time
            print(f"{'='*80}")
            print(f"[INFO] Scraping completed in {elapsed:.2f}s")
            print(f"[INFO] Total direct links found: {len(results)}")
            print(f"{'='*80}\n")

            return results

        finally:
            self._close()

    def _resolve_shortener(self, short_url):
        """Resolve shortener URL to get direct download link"""
        try:
            self.driver.get(short_url)
            time.sleep(1.5)

            # Look for verify button
            try:
                verify_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button | //a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'verify')]"))
                )
                self.driver.execute_script("arguments[0].click();", verify_btn)
                time.sleep(2)
            except TimeoutException:
                time.sleep(1)

            # Extract direct links
            html = self.driver.page_source
            soup = BeautifulSoup(html, "lxml")
            
            # Check for links in page
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http') and not any(x in href.lower() for x in ["nexdrive", "fast-dl", "short", "bit.ly"]):
                    # Check if it's a direct download link
                    if any(x in href.lower() for x in ["googledrive", "drive.google", "video-downloads.googleusercontent", "download", "dl"]):
                        return href

            # Also check in page source for direct links
            direct_links = re.findall(r'https?://[^\s"\'<>]+(?:video-downloads\.googleusercontent|googledrive)', html)
            if direct_links:
                return direct_links[0]

            return None

        except Exception as e:
            print(f"        [ERROR] Resolution failed: {str(e)}")
            return None

    def _close(self):
        """Close WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


def scrape_website(url, quality_filter=None):
    """
    Main function to scrape Vegamovies URL for direct download links
    
    Args:
        url: Vegamovies movie/series URL
        quality_filter: Optional quality filter (e.g., "1080p")
    
    Returns:
        List of dictionaries with direct download link info
    """
    scraper = VegamoviesScraper()
    try:
        results = scraper.scrape(url, quality_filter)
        return results
    except Exception as e:
        print(f"[ERROR] Scraping failed: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vg.py <vegamovies_url> [quality]")
        print("Example: python vg.py 'https://vegamovies.nf/...' '1080p'")
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = scrape_website(url, quality)
    
    if results:
        print(f"\n{'='*80}")
        print("DIRECT DOWNLOAD LINKS")
        print(f"{'='*80}\n")
        for r in results:
            filename = f"{r['show_name'].replace(' ', '.')}.S{r['season']}E{r['episode'].replace('EP', '')}.{r['quality']}.{r['size']}.mkv"
            print(f"File: {filename}")
            print(f"Link: {r['url']}\n")
