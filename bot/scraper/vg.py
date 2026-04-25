"""
Vegamovies Direct Link Scraper v7.0 - ADVANCED CORE LOGIC
AGGRESSIVE LINK DETECTION + DEBUG MODE
Pure HTTP-based (no Selenium/Chrome needed)
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

try:
    import requests
except ImportError:
    requests = None

try:
    from cloudscraper import create_scraper
except ImportError:
    create_scraper = None


class VegamoviesScraper:
    """Advanced scraper with aggressive link detection"""
    
    def __init__(self):
        self.session = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._init_session()

    def _init_session(self):
        """Initialize HTTP session with advanced headers"""
        print("[INFO] Initializing HTTP session...")
        try:
            if create_scraper:
                self.session = create_scraper()
                print("[INFO] Using CloudScraper for Cloudflare bypass")
            else:
                self.session = requests.Session()
                print("[INFO] Using requests session")
            
            # Advanced headers to avoid blocking
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            })
        except Exception as e:
            print(f"[ERROR] Session init failed: {e}")
            self.session = requests.Session()

    def _load_page(self, url: str, timeout: int = 30) -> str:
        """Load page via HTTP with retries"""
        print(f"[INFO] Fetching page: {url}")
        
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            print(f"[DEBUG] Status: {response.status_code}, Size: {len(response.text)} bytes")
            
            if response.status_code != 200:
                print(f"[ERROR] Bad status code: {response.status_code}")
                return ""
            
            if len(response.text) < 1000:
                print(f"[WARNING] Response too small ({len(response.text)} bytes) - might be incomplete")
            
            return response.text
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch page: {e}")
            return ""

    def _extract_episode(self, text: str, url: str) -> str:
        """Extract episode number from text"""
        ep_match = re.search(r'EP\.?(\d+)|Episode\.?(\d+)|E\.?(\d+)', text, re.I)
        if ep_match:
            ep_num = ep_match.group(1) or ep_match.group(2) or ep_match.group(3)
            return f"EP{ep_num.zfill(2)}"
        return "unknown"

    def _normalize_quality(self, quality: str) -> str:
        """Normalize quality string"""
        quality = quality.upper()
        if "1080" in quality:
            return "1080P"
        elif "720" in quality:
            return "720P"
        elif "480" in quality:
            return "480P"
        elif "4K" in quality or "2160" in quality:
            return "4K"
        return quality

    def get_download_links(self, html: str, url: str) -> List[Dict]:
        """Extract nexdrive + fast-dl links using ADVANCED DETECTION"""
        
        if not html:
            print("[ERROR] Empty HTML - page not fetched properly")
            return []
        
        if not BeautifulSoup:
            print("[ERROR] BeautifulSoup not available")
            return []
        
        print("[INFO] Parsing HTML...")
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title
        title_tag = soup.find("title")
        raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown"
        clean_title = re.sub(r'\s*\|\s*Vegamovies.*$', '', raw_title, flags=re.I).strip()
        clean_title = re.sub(r'^Download\s+', '', clean_title, flags=re.I).strip()
        
        show_name = re.sub(r'\s*Season\s*\d+.*|EP.*', '', clean_title, flags=re.I).strip()
        season_match = re.search(r'Season\s*0*(\d+)', clean_title, re.I)
        season = season_match.group(1).zfill(2) if season_match else "01"
        
        print(f"[INFO] Show: {show_name} | Season: S{season}")
        
        links = []
        current_quality = "unknown"
        current_size = "unknown"
        
        # Get ALL <a> tags on page
        all_a_tags = soup.find_all('a', href=True)
        print(f"[DEBUG] Found {len(all_a_tags)} total <a> tags on page")
        
        # AGGRESSIVE LINK DETECTION
        print("[INFO] Scanning for NEXDRIVE + FAST-DL links...")
        
        for a_tag in all_a_tags:
            href = a_tag.get('href', '').strip()
            if not href or href == '#' or len(href) < 10:
                continue
            
            # Make absolute URL
            if not href.startswith('http'):
                href = urljoin(url, href)
            
            link_text = a_tag.get_text(strip=True)
            href_lower = href.lower()
            
            # CRITICAL: Check for NEXDRIVE or FAST-DL (any variation)
            is_nexdrive = "nexdrive" in href_lower
            is_fastdl = "fast-dl" in href_lower or "fastdl" in href_lower
            
            # If it's a download link, extract quality from nearby text
            if is_nexdrive or is_fastdl:
                # Look for quality in the link text or surrounding content
                quality_match = re.search(r'(480p|720p|1080p|4k|2160p)', link_text, re.I)
                if quality_match:
                    current_quality = quality_match.group(0).upper()
                
                # Look for size in link text
                size_match = re.search(r'(\d+\.?\d*)\s*(GB|MB)', link_text, re.I)
                if size_match:
                    current_size = f"{size_match.group(1)} {size_match.group(2)}".upper()
                
                episode = self._extract_episode(link_text, href)
                link_type = "FAST-DL" if is_fastdl else "NEXDRIVE"
                
                links.append({
                    "url": href,
                    "quality": current_quality,
                    "size": current_size,
                    "episode": episode,
                    "text": link_text,
                    "link_type": link_type,
                    "show_name": show_name,
                    "season": season
                })
                
                print(f"     ✓ [{link_type}] {current_quality} ({current_size}) -> {href[:65]}...")
        
        print(f"\n[INFO] Found {len(links)} NEXDRIVE/FAST-DL links")
        
        # DEBUG: Show sample links if none found
        if not links:
            print("[DEBUG] No download links found!")
            print("[DEBUG] Sample of ALL links on page (first 15):")
            for i, a_tag in enumerate(all_a_tags[:15]):
                href = a_tag.get('href', '')[:80]
                text = a_tag.get_text(strip=True)[:50]
                print(f"     [{i+1}] Text: {text}")
                print(f"         URL: {href}")
        
        return links

    def _resolve_shortener(self, short_url: str) -> Optional[str]:
        """Resolve shortener to direct download link"""
        try:
            print(f"        [DEBUG] Resolving: {short_url[:70]}")
            
            response = self.session.get(short_url, timeout=30, allow_redirects=True)
            final_url = response.url
            html = response.text
            
            print(f"        [DEBUG] Final URL after redirects: {final_url[:70]}")
            
            # Pattern 1: Look in <a> tags
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if any(x in href.lower() for x in ["googledrive", "drive.google", "video-downloads.googleusercontent", "uc?id="]):
                    print(f"        [✓] Found in <a> tag: {href[:65]}")
                    return href
            
            # Pattern 2: Regex for direct links
            direct_links = re.findall(r'https?://[^\s"\'<>]+(?:video-downloads\.googleusercontent|drive\.google\.com)[^\s"\'<>]*', html)
            if direct_links:
                print(f"        [✓] Found via regex: {direct_links[0][:65]}")
                return direct_links[0]
            
            # Pattern 3: Meta refresh
            meta = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta and "url=" in str(meta.get("content", "")):
                redirect = str(meta.get("content", "")).split("url=")[-1]
                if redirect.startswith("http"):
                    print(f"        [✓] Found meta refresh: {redirect[:65]}")
                    return redirect
            
            # Pattern 4: JavaScript window.location
            js_matches = re.findall(r'(?:window\.location|location\.href)\s*=\s*["\']([^"\']+)["\']', html)
            for match in js_matches:
                if match.startswith('http'):
                    print(f"        [✓] Found JS redirect: {match[:65]}")
                    return match
            
            print(f"        [✗] No direct link found")
            return None
            
        except Exception as e:
            print(f"        [ERROR] Resolution failed: {e}")
            return None

    def scrape(self, url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Main scraping function"""
        start_time = time.time()
        
        print(f"\n{'='*80}")
        print(f"[INFO] VEGAMOVIES SCRAPER v7.0 (ADVANCED CORE LOGIC)")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality: {quality_filter}")
        print(f"{'='*80}\n")
        
        results = []
        
        try:
            # Step 1: Load page
            html = self._load_page(url, timeout=30)
            if not html:
                print("[ERROR] Failed to load page - HTML is empty")
                return results
            
            # Step 2: Extract links
            links = self.get_download_links(html, url)
            
            if not links:
                print("[ERROR] No download links found on page")
                return results
            
            # Step 3: Filter by quality
            if quality_filter:
                norm_filter = self._normalize_quality(quality_filter)
                filtered = [l for l in links if self._normalize_quality(l["quality"]) == norm_filter]
                if filtered:
                    links = filtered[:1]  # Single-driver: only 1 link per quality
                    print(f"[INFO] Quality filter applied ({quality_filter}) - Processing 1 link\n")
            
            # Step 4: Resolve shorteners
            if links:
                print(f"[INFO] Resolving {len(links)} link(s)...\n")
                
                for idx, link in enumerate(links, 1):
                    try:
                        print(f"[{idx}/{len(links)}] [{link['link_type']}] {link['quality']} ({link['size']})")
                        print(f"     Text: {link['text'][:60]}")
                        
                        direct_link = self._resolve_shortener(link["url"])
                        
                        if direct_link:
                            results.append({
                                "show_name": link["show_name"],
                                "season": link["season"],
                                "episode": link["episode"],
                                "quality": link["quality"],
                                "size": link["size"],
                                "url": direct_link
                            })
                            print(f"     [SUCCESS] Extracted direct link\n")
                        else:
                            print(f"     [FAILED] Could not resolve\n")
                    except Exception as e:
                        print(f"     [ERROR] {e}\n")
            
            elapsed = time.time() - start_time
            print(f"{'='*80}")
            print(f"[INFO] Completed in {elapsed:.2f}s")
            print(f"[INFO] Direct links found: {len(results)}")
            print(f"{'='*80}\n")
            
            return results
            
        except Exception as e:
            print(f"\n[CRITICAL ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return results


def scrape_website(url: str, quality: Optional[str] = None) -> List[Dict[str, Any]]:
    """Public API for scraping"""
    scraper = VegamoviesScraper()
    return scraper.scrape(url, quality)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vg.py <url> [quality]")
        sys.exit(1)
    
    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = scrape_website(url, quality)
    
    if results:
        print("\nDIRECT LINKS EXTRACTED:")
        for r in results:
            print(f"\n{r['show_name']} S{r['season']}E{r['episode']} [{r['quality']}]")
            print(f"  {r['url']}")
    else:
        print("\n[ERROR] No direct links extracted")
        sys.exit(1)
