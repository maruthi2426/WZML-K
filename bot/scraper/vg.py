"""
Vegamovies Direct Link Scraper v6.0
FOCUSED SCRAPER - Only finds links in download section (nexdrive + fast-dl.org)
Works without Selenium/Chrome - Pure HTTP-based approach
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
    """Focused scraper - ONLY nexdrive + fast-dl.org from download section"""
    
    def __init__(self):
        self.session = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._init_session()

    def _init_session(self):
        """Initialize HTTP session"""
        print("[INFO] Initializing HTTP session...")
        try:
            if create_scraper:
                self.session = create_scraper()
                print("[INFO] Using CloudScraper for bypass")
            else:
                self.session = requests.Session()
                print("[INFO] Using requests session")
            
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(total=3, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1)
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            })
        except Exception as e:
            print(f"[WARNING] Session init failed: {e}")
            if requests:
                self.session = requests.Session()
                self.session.headers.update({"User-Agent": self.user_agent})

    def _load_page(self, url: str, timeout: int = 25) -> str:
        """Load page via HTTP"""
        print(f"[INFO] Fetching page...")
        if not self.session:
            raise Exception("Session not initialized")
        
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            print(f"[INFO] Page loaded ({response.status_code}, {len(response.text)} bytes)")
            return response.text
        except Exception as e:
            raise Exception(f"Failed to load page: {str(e)}")

    def _normalize_quality(self, q: str) -> str:
        """Normalize quality for comparison"""
        if not q:
            return "unknown"
        q = q.upper().replace("X264", "X264").replace("X265", "X265")
        return re.sub(r'\s+', '', q)

    def _extract_episode(self, text: str = "", url_slug: str = "") -> str:
        """Extract episode number"""
        if url_slug:
            slug_match = re.search(r'ep[-_]0*(\d{1,3})', url_slug.lower())
            if slug_match:
                return f"EP{slug_match.group(1).zfill(2)}"
        
        if text:
            patterns = [r'ep[-_:\s]*0*(\d{1,3})', r'episode[-_:\s]*0*(\d{1,3})', r'\be(\d{2,3})\b']
            for pattern in patterns:
                match = re.search(pattern, text.lower())
                if match:
                    return f"EP{match.group(1).zfill(2)}"
        
        return "unknown"

    def get_download_links(self, html: str, url: str) -> List[Dict]:
        """Extract ONLY nexdrive + fast-dl links from download section"""
        
        if not BeautifulSoup:
            print("[ERROR] BeautifulSoup not available")
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title info
        title_tag = soup.find("title")
        raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown"
        clean_title = re.sub(r'\s*\|\s*Vegamovies.*$', '', raw_title, flags=re.I).strip()
        clean_title = re.sub(r'^Download\s+', '', clean_title, flags=re.I).strip()
        clean_title = re.sub(r'\s+', ' ', clean_title)
        
        show_name = re.sub(r'\s*Season\s*\d+.*|EP.*', '', clean_title, flags=re.I).strip()
        season_match = re.search(r'Season\s*0*(\d+)', clean_title, re.I)
        season = season_match.group(1).zfill(2) if season_match else "01"
        
        print(f"[INFO] Show: {show_name} | Season: S{season}")
        
        links = []
        current_quality = "unknown"
        current_size = "unknown"
        
        # Scan page elements to find quality markers followed by shortener links
        all_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p', 'div', 'span', 'a'])
        
        print(f"[INFO] Scanning for NEXDRIVE + FAST-DL links only...\n")
        
        # Debug: count all <a> tags
        all_a_tags = soup.find_all('a', href=True)
        print(f"[DEBUG] Found {len(all_a_tags)} total <a> tags on page")
        
        for i, element in enumerate(all_elements):
            text = element.get_text(strip=True)
            if not text:
                continue
            
            # Look for quality markers
            quality_match = re.search(r'(480p|720p|1080p|4k|2160p)', text, re.I)
            if quality_match:
                current_quality = quality_match.group(0).upper()
                size_match = re.search(r'(\d+\.?\d*)\s*(GB|MB)', text, re.I)
                if size_match:
                    current_size = f"{size_match.group(1)} {size_match.group(2)}".upper()
                print(f"     Quality marker found: {current_quality} ({current_size})")
                continue
            
            # Look for ONLY nexdrive and fast-dl links (support multiple domains)
            if element.name == "a" and element.has_attr("href"):
                href = element.get('href', '').strip()
                if not href or href == '#':
                    continue
                
                # Make absolute URL
                if not href.startswith('http'):
                    href = urljoin(url, href)
                
                link_text = element.get_text(strip=True)
                href_lower = href.lower()
                
                # Check for NEXDRIVE or FAST-DL (support multiple domain variations)
                is_nexdrive = "nexdrive" in href_lower
                is_fastdl = "fast-dl" in href_lower  # Catches fast-dl.org, fast-dl.com, etc
                
                if (is_nexdrive or is_fastdl) and len(href) > 10:
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
        
        print(f"\n[INFO] Found {len(links)} NEXDRIVE/FAST-DL link(s)")
        
        # Debug: if no links found, show some of the links we skipped
        if not links:
            print("[DEBUG] No NEXDRIVE/FAST-DL links found. Sample of links on page:")
            for a_tag in all_a_tags[:10]:  # Show first 10 links
                href = a_tag.get('href', '')
                text = a_tag.get_text(strip=True)[:50]
                print(f"     - {text}: {href[:70]}")
        
        return links

    def _resolve_shortener(self, short_url: str) -> Optional[str]:
        """Resolve shortener to direct Google Drive link"""
        if not self.session:
            return None
        
        try:
            print(f"     Resolving shortener...")
            response = self.session.get(short_url, timeout=20, allow_redirects=True)
            final_url = response.url
            
            if not BeautifulSoup:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Pattern 1: Look for direct links in <a> tags
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http') and 'googleusercontent' in href.lower():
                    return href
            
            # Pattern 2: Regex for Google Drive URLs
            matches = re.findall(r'https?://[^\s"\'<>]*video-downloads\.googleusercontent[^\s"\'<>]*', response.text)
            if matches:
                return matches[0]
            
            # Pattern 3: Meta refresh
            meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta_refresh and meta_refresh.get("content"):
                content = meta_refresh.get("content", "")
                if "url=" in content.lower():
                    url_match = re.search(r'url\s*=\s*["\']?([^"\']+)["\']?', content, re.I)
                    if url_match:
                        return url_match.group(1)
            
            # Pattern 4: JavaScript redirects
            js_patterns = [
                r'window\.location\s*[=\.href]*\s*["\']([^"\']+)["\']',
                r'location\.href\s*=\s*["\']([^"\']+)["\']',
            ]
            for pattern in js_patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    for match in matches:
                        if match.startswith('http') and 'googleusercontent' in match.lower():
                            return match
            
            return None
        except Exception as e:
            print(f"     Error: {str(e)}")
            return None

    def scrape(self, url: str, quality_filter: Optional[str] = None) -> List[Dict]:
        """Main scrape function"""
        start_time = time.time()
        
        print(f"\n{'='*80}")
        print(f"[INFO] VEGAMOVIES SCRAPER v6.0 (FOCUSED - NEXDRIVE + FAST-DL ONLY)")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality: {quality_filter}")
        print(f"{'='*80}\n")
        
        try:
            # Load page
            html = self._load_page(url)
            
            # Get ONLY nexdrive + fast-dl links
            short_links = self.get_download_links(html, url)
            
            if not short_links:
                print("[ERROR] No NEXDRIVE/FAST-DL links found in download section")
                return []
            
            # Filter by quality if specified
            results = []
            if quality_filter:
                norm_filter = self._normalize_quality(quality_filter)
                filtered = [l for l in short_links if self._normalize_quality(l["quality"]) == norm_filter]
                if filtered:
                    short_links = filtered[:1]  # SINGLE DRIVER MODE - only 1 link
                    print(f"\n[INFO] Quality filter applied - Processing 1 link (ULTRA-FAST mode)\n")
                else:
                    print(f"[ERROR] No link found for quality: {quality_filter}")
                    return []
            
            # Resolve each shortener link
            if short_links:
                print(f"[INFO] Resolving {len(short_links)} link(s)...\n")
                
                for idx, link_info in enumerate(short_links, 1):
                    try:
                        print(f"[{idx}/{len(short_links)}] [{link_info['link_type']}] {link_info['quality']} ({link_info['size']})")
                        
                        direct_link = self._resolve_shortener(link_info["url"])
                        
                        if direct_link:
                            results.append({
                                "show_name": link_info["show_name"],
                                "season": link_info["season"],
                                "episode": link_info["episode"],
                                "quality": link_info["quality"],
                                "size": link_info["size"],
                                "url": direct_link
                            })
                            print(f"     ✓ Direct link: {direct_link[:70]}...\n")
                        else:
                            print(f"     ✗ Failed to resolve\n")
                    except Exception as e:
                        print(f"     ✗ Error: {str(e)}\n")
            
            elapsed = time.time() - start_time
            print(f"{'='*80}")
            print(f"[INFO] Completed in {elapsed:.2f}s")
            print(f"[INFO] Direct links found: {len(results)}")
            print(f"{'='*80}\n")
            
            return results
        
        except Exception as e:
            print(f"[ERROR] Scraping failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return []


def scrape_website(url: str, quality_filter: Optional[str] = None) -> List[Dict]:
    """Main function called from bot"""
    print(f"[INFO] Starting Vegamovies scraper")
    scraper = VegamoviesScraper()
    try:
        results = scraper.scrape(url, quality_filter)
        return results
    except Exception as e:
        print(f"[ERROR] Scraping failed: {str(e)}")
        return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vg.py <url> [quality]")
        print("Example: python vg.py 'https://vegamovies.nf/movie' '1080p'")
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = scrape_website(url, quality)
    
    if results:
        print(f"\n{'='*80}")
        print("FINAL DIRECT DOWNLOAD LINKS")
        print(f"{'='*80}\n")
        for r in results:
            ep = r.get('episode', 'unknown').replace('EP', '')
            filename = f"{r['show_name'].replace(' ', '.')}.S{r['season']}E{ep}.{r['quality']}.{r['size']}.mkv"
            print(f"{filename}")
            print(f"→ {r['url']}\n")
    else:
        print("[ERROR] No direct links found")
        sys.exit(1)
