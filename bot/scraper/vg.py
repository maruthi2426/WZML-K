"""
Vegamovies Direct Link Scraper v3.0
Fast HTTP-based scraper (no Selenium) to extract direct download links from Vegamovies movie URLs
Supports quality filtering and both movie and series content
Works on headless servers without Chrome/Chromium installed
"""

import sys
import re
import time
from urllib.parse import urljoin
import subprocess

try:
    from bs4 import BeautifulSoup
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "-q"])
        from bs4 import BeautifulSoup
    except:
        BeautifulSoup = None

try:
    import requests
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
        import requests
    except:
        requests = None

try:
    from cloudscraper import create_scraper as cloudscraper_create
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper", "-q"])
        from cloudscraper import create_scraper as cloudscraper_create
    except:
        cloudscraper_create = None


class VegamoviesScraper:
    def __init__(self):
        self.session = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._init_session()

    def _init_session(self):
        """Initialize HTTP session with proper headers"""
        try:
            # Try cloudscraper first to bypass Cloudflare
            if cloudscraper_create:
                self.session = cloudscraper_create()
                print("[INFO] Using cloudscraper for CF bypass")
            else:
                # Fallback to regular requests
                self.session = requests.Session()
                print("[INFO] Using regular requests session")
            
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            })
        except Exception as e:
            print(f"[WARNING] Failed to initialize session: {str(e)}")
            self.session = requests.Session()

    def _load_page(self, url):
        """Load Vegamovies page via HTTP GET"""
        print(f"[INFO] Fetching page: {url}")
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            print(f"[INFO] Page loaded successfully (Status: {response.status_code})")
            return response.text
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
        print(f"[INFO] VEGAMOVIES SCRAPER v3.0 (HTTP-BASED)")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality Filter: {quality_filter}")
        print(f"{'='*80}\n")

        results = []

        try:
            # Load page
            html = self._load_page(url)
            soup = BeautifulSoup(html, "html.parser")

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
                print(f"[INFO] Resolving shortener links (this may take time)...\n")
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

        except Exception as e:
            print(f"[ERROR] Scraping failed: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def _resolve_shortener(self, short_url):
        """Resolve shortener URL to get direct download link (HTTP-based with redirects)"""
        try:
            print(f"        [DEBUG] Resolving shortener: {short_url}")
            
            # Follow redirects to get final URL
            response = self.session.get(short_url, timeout=15, allow_redirects=True)
            final_url = response.url
            print(f"        [DEBUG] Final URL after redirects: {final_url}")
            
            # Parse final page
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Pattern 1: Look for direct download links in all <a> tags
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http'):
                    href_lower = href.lower()
                    # Check if it's a direct download link (Google Drive, etc)
                    if any(x in href_lower for x in ["googledrive", "drive.google", "video-downloads.googleusercontent", "/download", "dl="]):
                        print(f"        [DEBUG] Found direct link in <a> tag: {href[:70]}")
                        return href
            
            # Pattern 2: Search page source for direct links using regex
            direct_links = re.findall(r'https?://[^\s"\'<>]+(?:video-downloads\.googleusercontent|drive\.google\.com)[^\s"\'<>]*', response.text)
            if direct_links:
                print(f"        [DEBUG] Found direct link via regex: {direct_links[0][:70]}")
                return direct_links[0]
            
            # Pattern 3: Check for redirect meta tags
            meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta_refresh and meta_refresh.get("content"):
                content = meta_refresh.get("content", "")
                if "url=" in content:
                    redirect_url = content.split("url=")[-1]
                    if redirect_url.startswith("http"):
                        print(f"        [DEBUG] Found meta redirect: {redirect_url[:70]}")
                        return redirect_url
            
            # Pattern 4: Check for JavaScript redirect patterns
            js_patterns = [
                r'window\.location\s*=\s*["\']([^"\']+)["\']',
                r'location\.href\s*=\s*["\']([^"\']+)["\']',
                r'location\.replace\(["\']([^"\']+)["\']\)',
            ]
            for pattern in js_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    for match in matches:
                        if match.startswith('http'):
                            print(f"        [DEBUG] Found JS redirect: {match[:70]}")
                            return match
            
            print(f"        [WARNING] No direct link found on final page")
            return None

        except Exception as e:
            print(f"        [ERROR] Resolution failed: {type(e).__name__}: {str(e)}")
            return None


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
    
    try:
        results = scrape_website(url, quality)
        
        if results:
            print(f"\n{'='*80}")
            print("DIRECT DOWNLOAD LINKS")
            print(f"{'='*80}\n")
            for r in results:
                filename = f"{r['show_name'].replace(' ', '.')}.S{r['season']}E{r['episode'].replace('EP', '')}.{r['quality']}.{r['size']}.mkv"
                print(f"File: {filename}")
                print(f"Link: {r['url']}\n")
        else:
            print("[ERROR] No direct links found")
    except Exception as e:
        print(f"[ERROR] Scraping failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
