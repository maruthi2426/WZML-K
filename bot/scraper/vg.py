"""
Vegamovies Direct Link Scraper v4.0
Advanced HTTP-based scraper (no Selenium) to extract direct download links from Vegamovies movie URLs
Supports quality filtering and both movie and series content
Works on headless servers without Chrome/Chromium installed
Uses advanced request handling with retry logic and Cloudflare bypass
"""

import sys
import re
import time
import subprocess
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any

def _ensure_dependencies():
    """Ensure all required dependencies are installed"""
    required = ["requests", "beautifulsoup4", "cloudscraper"]
    missing = []
    
    for package in required:
        try:
            if package == "beautifulsoup4":
                __import__("bs4")
            elif package == "cloudscraper":
                __import__("cloudscraper")
            else:
                __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"[INFO] Installing missing dependencies: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["-q"])
            print(f"[INFO] Dependencies installed successfully")
        except Exception as e:
            print(f"[WARNING] Failed to auto-install dependencies: {e}")

_ensure_dependencies()

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    print("[ERROR] BeautifulSoup4 not available")

try:
    import requests
except ImportError:
    requests = None
    print("[ERROR] Requests library not available")

try:
    from cloudscraper import create_scraper
except ImportError:
    create_scraper = None
    print("[WARNING] CloudScraper not available, using regular requests")


class VegamoviesScraper:
    """Advanced HTTP-based scraper for Vegamovies URLs"""
    
    def __init__(self):
        """Initialize scraper with session and headers"""
        self.session = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._init_session()

    def _init_session(self):
        """Initialize HTTP session with advanced configuration"""
        print("[INFO] Initializing HTTP session...")
        try:
            # Use CloudScraper if available for Cloudflare bypass
            if create_scraper:
                self.session = create_scraper()
                print("[INFO] Using CloudScraper for advanced bypass")
            else:
                self.session = requests.Session()
                print("[INFO] Using standard requests session")
            
            # Configure session with retry strategy
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                backoff_factor=1
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            # Set headers for browser-like requests
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "sec-ch-ua-mobile": "?0",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
            })
            print("[INFO] Session headers configured")
        except Exception as e:
            print(f"[WARNING] Failed to initialize advanced session: {e}")
            if requests:
                self.session = requests.Session()
                self.session.headers.update({"User-Agent": self.user_agent})

    def _load_page(self, url: str, timeout: int = 20) -> str:
        """Load webpage with error handling and retries"""
        print(f"[INFO] Fetching URL: {url}")
        if not self.session:
            raise Exception("Session not initialized")
        
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            print(f"[INFO] Page loaded successfully (Status: {response.status_code}, Size: {len(response.text)} bytes)")
            return response.text
        except requests.exceptions.Timeout:
            raise Exception(f"Request timeout after {timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"Connection error: {e}")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP error {response.status_code}: {e}")
        except Exception as e:
            raise Exception(f"Failed to load page: {str(e)}")

    def _normalize_quality(self, quality_str: str) -> str:
        """Normalize quality string for comparison"""
        if not quality_str:
            return "unknown"
        q = quality_str.upper().strip()
        q = re.sub(r'\s+', '', q)
        return q

    def _extract_episode(self, text: str = "", url_slug: str = "") -> str:
        """Extract episode number from text or URL slug"""
        if url_slug:
            slug_match = re.search(r'ep[-_]0*(\d{1,3})', url_slug.lower())
            if slug_match:
                return f"EP{slug_match.group(1).zfill(2)}"

        if text:
            patterns = [
                r'ep[-_:\s]*0*(\d{1,3})',
                r'episode[-_:\s]*0*(\d{1,3})',
                r'\be(\d{2,3})\b',
                r'e(\d{1,3})(?:\s|$)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text.lower())
                if match:
                    return f"EP{match.group(1).zfill(2)}"
        
        return "EP01"

    def scrape(self, url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Main scraping function with advanced parsing"""
        start_time = time.time()
        print(f"\n{'='*80}")
        print(f"[INFO] VEGAMOVIES SCRAPER v4.0 (ADVANCED HTTP-BASED)")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality Filter: {quality_filter}")
        print(f"{'='*80}\n")

        results = []

        try:
            # Load page
            html = self._load_page(url, timeout=25)
            
            if not BeautifulSoup:
                raise Exception("BeautifulSoup4 not available")
            
            soup = BeautifulSoup(html, "html.parser")

            # Extract page info
            title_tag = soup.find("title")
            raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
            # Clean title
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

            # Extract all elements and look for quality and links
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p', 'a', 'span', 'div']):
                text = element.get_text(strip=True)
                
                # Check for quality markers
                quality_match = re.search(r'(480p|720p|1080p|4k|2160p|HQ\s+1080p|HD\s+1080p)', text, re.I)
                if quality_match:
                    current_quality = quality_match.group(0).upper()
                    size_match = re.search(r'(\d+\.?\d*)\s*(GB|MB)', text, re.I)
                    if size_match:
                        current_size = f"{size_match.group(1)} {size_match.group(2)}".upper()
                    print(f"[DEBUG] Found quality: {current_quality} ({current_size})")
                    continue

                # Check for download links
                if element.name == "a" and element.has_attr("href"):
                    href = urljoin(url, element["href"])
                    link_text = element.get_text(strip=True)
                    
                    # Identify shortener links
                    if any(x in href.lower() for x in ["nexdrive", "fast-dl", "bit.ly", "tinyurl", "short", "adf.ly", "adfly"]):
                        episode = self._extract_episode(link_text, href)
                        all_links.append({
                            "url": href,
                            "quality": current_quality,
                            "size": current_size,
                            "episode": episode,
                            "text": link_text
                        })
                        print(f"[DEBUG] Found shortener link: {href[:60]}...")

            print(f"[INFO] Found {len(all_links)} shortener link(s)\n")

            # Filter by quality if specified
            if quality_filter and all_links:
                norm_filter = self._normalize_quality(quality_filter)
                filtered = [l for l in all_links if self._normalize_quality(l["quality"]) == norm_filter]
                if filtered:
                    all_links = filtered[:1]
                    print(f"[INFO] Quality filter applied - using {len(all_links)} link(s)\n")
                else:
                    print(f"[WARNING] No links found for quality: {quality_filter}\n")

            # Resolve shortener links to direct download links
            if all_links:
                print(f"[INFO] Resolving shortener links to direct links (this may take time)...\n")
                for idx, link_info in enumerate(all_links, 1):
                    try:
                        print(f"[{idx}/{len(all_links)}] Processing: {link_info['quality']} - {link_info['episode']}")
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
                            print(f"     ✓ SUCCESS: {direct_link[:70]}...\n")
                        else:
                            print(f"     ✗ FAILED: Could not resolve link\n")
                    except Exception as e:
                        print(f"     ✗ ERROR: {str(e)}\n")

            elapsed = time.time() - start_time
            print(f"{'='*80}")
            print(f"[INFO] Scraping completed in {elapsed:.2f}s")
            print(f"[INFO] Total direct links found: {len(results)}")
            print(f"{'='*80}\n")

            return results

        except Exception as e:
            print(f"[ERROR] Scraping failed: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def _resolve_shortener(self, short_url: str) -> Optional[str]:
        """Resolve shortener URL to direct download link using multiple patterns"""
        if not self.session:
            return None
        
        try:
            print(f"        [DEBUG] Resolving: {short_url}")
            
            # Follow HTTP redirects
            response = self.session.get(short_url, timeout=20, allow_redirects=True)
            final_url = response.url
            print(f"        [DEBUG] Final URL: {final_url}")
            
            if not BeautifulSoup:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Pattern 1: Direct link in <a> tags
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http'):
                    href_lower = href.lower()
                    if any(x in href_lower for x in ["googledrive", "drive.google", "video-downloads.googleusercontent", "/download", "dl="]):
                        print(f"        [DEBUG] Found in <a> tag: {href[:60]}...")
                        return href
            
            # Pattern 2: Regex search in page source
            direct_patterns = [
                r'https?://[^\s"\'<>]*(?:drive\.google\.com|video-downloads\.googleusercontent)[^\s"\'<>]*',
                r'https?://[^\s"\'<>]*(?:download|dl)[^\s"\'<>]*(?:google|drive)[^\s"\'<>]*',
            ]
            for pattern in direct_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    print(f"        [DEBUG] Found via regex: {matches[0][:60]}...")
                    return matches[0]
            
            # Pattern 3: Meta refresh redirects
            meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta_refresh and meta_refresh.get("content"):
                content = meta_refresh.get("content", "")
                if "url=" in content.lower():
                    redirect_url = re.search(r'url\s*=\s*["\']?([^"\']+)["\']?', content, re.I)
                    if redirect_url:
                        url = redirect_url.group(1)
                        if url.startswith('http'):
                            print(f"        [DEBUG] Found meta redirect: {url[:60]}...")
                            return url
            
            # Pattern 4: JavaScript window.location patterns
            js_patterns = [
                r'window\.location\s*[=\.href]*\s*["\']([^"\']+)["\']',
                r'location\.href\s*=\s*["\']([^"\']+)["\']',
                r'location\.replace\s*\(\s*["\']([^"\']+)["\']\s*\)',
                r'(?:document\.location|window\.location\.href)\s*=\s*["\']?([^\s"\'<>]+)',
            ]
            for pattern in js_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    for match in matches:
                        if match.startswith('http'):
                            print(f"        [DEBUG] Found JS redirect: {match[:60]}...")
                            return match
            
            # Pattern 5: Check for button/link data attributes
            for element in soup.find_all(['button', 'a', 'div']):
                for attr in ['data-url', 'data-link', 'data-href', 'data-download']:
                    if element.has_attr(attr):
                        url = element.get(attr, '')
                        if url.startswith('http'):
                            print(f"        [DEBUG] Found in data attribute: {url[:60]}...")
                            return url
            
            print(f"        [WARNING] No direct link found")
            return None

        except Exception as e:
            print(f"        [ERROR] Resolution failed: {type(e).__name__}: {str(e)}")
            return None


def scrape_website(url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Main function to scrape Vegamovies URL for direct download links
    
    Args:
        url: Vegamovies movie/series URL
        quality_filter: Optional quality filter (e.g., "1080p")
    
    Returns:
        List of dictionaries with direct download link info
    """
    print(f"\n[INFO] Starting Vegamovies scraper")
    scraper = VegamoviesScraper()
    try:
        results = scraper.scrape(url, quality_filter)
        return results
    except Exception as e:
        print(f"[ERROR] Scraping failed: {type(e).__name__}: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vg.py <vegamovies_url> [quality]")
        print("Example: python vg.py 'https://vegamovies.nf/movie-url' '1080p'")
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
            sys.exit(1)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Scraping failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
