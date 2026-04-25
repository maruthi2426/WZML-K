"""
Vegamovies Direct Link Scraper v6.0
ULTRA-FAST + TARGETED DOWNLOAD SECTION ONLY
- Scrapes ONLY the download links section (ignores sidebar, related movies, navigation)
- Prioritizes "nexdrive" and "fast-dl.org" links only
- Strict quality filtering (1080p / 720p etc.)
- Advanced resolution for fast-dl (direct) and nexdrive (via intermediate)
- Single-driver style logic for speed and reliability
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
    from bs4 import BeautifulSoup, NavigableString
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
    """Ultra-fast Vegamovies scraper - targets only download section"""
    
    def __init__(self):
        self.session = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        self._init_session()

    def _init_session(self):
        print("[INFO] Initializing HTTP session with CloudScraper...")
        try:
            if create_scraper:
                self.session = create_scraper()
                print("[INFO] CloudScraper enabled for bypass")
            else:
                self.session = requests.Session()
            
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            })
        except Exception as e:
            print(f"[WARNING] Session init issue: {e}")
            if requests:
                self.session = requests.Session()
                self.session.headers.update({"User-Agent": self.user_agent})

    def _load_page(self, url: str, timeout: int = 25) -> str:
        print(f"[INFO] Fetching: {url}")
        response = self.session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        print(f"[INFO] Page loaded (Status: {response.status_code}, Size: {len(response.text):,} bytes)")
        return response.text

    def _normalize_quality(self, q: str) -> str:
        if not q:
            return ""
        q = q.upper().strip()
        q = re.sub(r'\s+', '', q)
        return q

    def _extract_size(self, text: str) -> str:
        match = re.search(r'(\d+\.?\d*)\s*(GB|MB)', text, re.I)
        return f"{match.group(1)} {match.group(2).upper()}" if match else "UNKNOWN"

    def scrape(self, url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        start_time = time.time()
        print(f"\n{'='*100}")
        print(f"[INFO] VEGAMOVIES ULTRA SCRAPER v6.0 - DOWNLOAD SECTION ONLY")
        print(f"[INFO] Target URL : {url}")
        if quality_filter:
            print(f"[INFO] Quality   : {quality_filter} (strict filter)")
        print(f"{'='*100}\n")

        results = []

        try:
            html = self._load_page(url)
            if not BeautifulSoup:
                raise Exception("BeautifulSoup not available")

            soup = BeautifulSoup(html, "html.parser")

            # Clean title
            title_tag = soup.find("title")
            raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
            clean_title = re.sub(r'\s*\|\s*Vegamovies.*$', '', raw_title, flags=re.I).strip()
            clean_title = re.sub(r'^Download\s+', '', clean_title, flags=re.I).strip()
            clean_title = re.sub(r'\s+', ' ', clean_title)

            show_name = re.sub(r'\s*Season\s*\d+.*|EP.*', '', clean_title, flags=re.I).strip()
            season_match = re.search(r'Season\s*0*(\d+)', clean_title, re.I)
            season = season_match.group(1).zfill(2) if season_match else "01"

            print(f"[INFO] Show     : {show_name}")
            print(f"[INFO] Season   : S{season}\n")

            # === CRITICAL: Target ONLY the DOWNLOAD SECTION ===
            # Look for common containers that hold download links on Vegamovies
            download_section = None
            candidates = [
                soup.find("div", class_=re.compile(r'download|links|button|entry-content', re.I)),
                soup.find("article"),
                soup.find("div", id=re.compile(r'post|content|main', re.I)),
            ]
            
            for cand in candidates:
                if cand and any(word in cand.get_text() for word in ["Click Here To Download", "Download", "1080p", "720p"]):
                    download_section = cand
                    break

            if not download_section:
                # Fallback: whole body but we'll be stricter later
                download_section = soup.body or soup

            print("[INFO] Scanning DOWNLOAD SECTION only for quality markers and links...\n")

            all_download_links = []
            current_quality = "UNKNOWN"
            current_size = "UNKNOWN"

            # First pass: find quality headers in the section
            for elem in download_section.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'p', 'div', 'span']):
                text = elem.get_text(strip=True)
                if not text:
                    continue
                
                q_match = re.search(r'(480p|720p|1080p|2160p|4k|HQ\s*1080p|HD\s*1080p)', text, re.I)
                if q_match:
                    current_quality = q_match.group(0).upper()
                    current_size = self._extract_size(text)
                    print(f"     Quality header → {current_quality} ({current_size})")

            # Second pass: extract only relevant shortener links inside download section
            allowed_domains = ["nexdrive", "fast-dl.org", "vgmlinks.app"]  # vgmlinks as fallback but lower priority

            for link in download_section.find_all('a', href=True):
                href = link.get('href', '').strip()
                link_text = link.get_text(strip=True)

                if not href or href.startswith('#') or len(href) < 15:
                    continue

                if not href.startswith('http'):
                    href = urljoin(url, href)

                href_lower = href.lower()
                text_lower = link_text.lower()

                # STRICT FILTER: only keep nexdrive / fast-dl (and vgmlinks as backup)
                is_target = any(dom in href_lower for dom in ["nexdrive", "fast-dl.org", "vgmlinks.app"])
                
                # Also accept if text clearly indicates download
                if not is_target and any(kw in text_lower for kw in ["click here to download", "download", "dl "]):
                    is_target = any(dom in href_lower for dom in allowed_domains)

                if not is_target:
                    continue

                # Skip obvious non-download links
                if any(skip in href_lower for skip in ["javascript", "void(0)", "/category/", "/tag/", "related", "genre"]):
                    continue

                size = self._extract_size(link_text) or current_size
                quality = current_quality if current_quality != "UNKNOWN" else re.search(r'(480p|720p|1080p|2160p)', link_text, re.I)
                quality = quality.group(0).upper() if quality else current_quality

                all_download_links.append({
                    "url": href,
                    "quality": quality,
                    "size": size,
                    "text": link_text[:100],
                    "domain": next((d for d in ["nexdrive", "fast-dl", "vgmlinks"] if d in href_lower), "other")
                })

            print(f"[INFO] Found {len(all_download_links)} potential download short links in section\n")

            # === STRICT QUALITY FILTER ===
            if quality_filter and all_download_links:
                norm_filter = self._normalize_quality(quality_filter)
                filtered_links = []
                for lnk in all_download_links:
                    if self._normalize_quality(lnk["quality"]) == norm_filter or norm_filter in lnk["quality"]:
                        filtered_links.append(lnk)
                
                if filtered_links:
                    all_download_links = filtered_links
                    print(f"[INFO] Quality filter '{quality_filter}' applied → {len(all_download_links)} links kept")
                else:
                    print(f"[WARNING] No exact match for {quality_filter}. Using best available.")
                    # fallback to any 1080p-like if requested 1080p
                    if "1080" in norm_filter:
                        all_download_links = [l for l in all_download_links if "1080" in l["quality"]]

            # Prioritize order: fast-dl > nexdrive > vgmlinks
            priority = {"fast-dl": 3, "nexdrive": 2, "vgmlinks": 1, "other": 0}
            all_download_links.sort(key=lambda x: priority.get(x["domain"], 0), reverse=True)

            print(f"[INFO] Prioritized {len(all_download_links)} link(s) for resolution...\n")

            # Resolve only the top ones (usually 1-3 per quality)
            resolved_count = 0
            for idx, link_info in enumerate(all_download_links[:8], 1):  # safety limit
                try:
                    print(f"[{idx}] {link_info['quality']} | {link_info['size']} | {link_info['domain'].upper()} → {link_info['text'][:60]}...")
                    direct = self._resolve_link(link_info["url"], link_info["domain"])
                    
                    if direct and direct.startswith("http"):
                        results.append({
                            "show_name": show_name,
                            "season": season,
                            "episode": "01",  # movie = 01
                            "quality": link_info["quality"],
                            "size": link_info["size"],
                            "url": direct
                        })
                        print(f"     [✓] DIRECT: {direct[:90]}...\n")
                        resolved_count += 1
                    else:
                        print(f"     [✗] Could not resolve\n")
                except Exception as e:
                    print(f"     [ERROR] {str(e)[:80]}\n")

            elapsed = time.time() - start_time
            print(f"{'='*100}")
            print(f"[SUCCESS] Scraping finished in {elapsed:.2f}s | Resolved: {len(results)} direct link(s)")
            print(f"{'='*100}\n")

            return results

        except Exception as e:
            print(f"[CRITICAL ERROR] {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return results

    def _resolve_link(self, short_url: str, domain: str) -> Optional[str]:
        """Resolve fast-dl (often direct) or nexdrive/vgmlinks"""
        if not self.session:
            return None

        try:
            print(f"        [RESOLVE] {domain.upper()} → {short_url[:70]}")

            resp = self.session.get(short_url, timeout=15, allow_redirects=True)
            final = resp.url

            # Fast-dl often redirects directly to Google video-downloads.googleusercontent.com
            if "video-downloads.googleusercontent.com" in final or "drive.google.com" in final:
                print(f"        [✓] FAST-DL DIRECT FOUND")
                return final

            # If still on shortener, parse page
            soup = BeautifulSoup(resp.text, "html.parser")

            # Common patterns for direct Google drive video links
            patterns = [
                r'https?://video-downloads\.googleusercontent\.com/[^\s"\'<>]+',
                r'https?://[^\s"\'<>]*drive\.google\.com[^\s"\'<>]*',
                r'https?://[^\s"\'<>]*(?:download|dl=)[^\s"\'<>]*',
            ]

            for pat in patterns:
                matches = re.findall(pat, resp.text + " " + final)
                if matches:
                    direct = matches[0]
                    print(f"        [✓] Regex direct: {direct[:80]}...")
                    return direct

            # Look for <a> tags with download
            for a in soup.find_all('a', href=True):
                h = a['href']
                if h.startswith('http') and ("video-downloads.googleusercontent.com" in h or "dl=" in h):
                    return h

            # JS location patterns (common on nexdrive intermediates)
            js_pat = [
                r'window\.location\s*=\s*["\']([^"\']+)["\']',
                r'location\.href\s*=\s*["\']([^"\']+)["\']',
            ]
            for p in js_pat:
                m = re.search(p, resp.text)
                if m and m.group(1).startswith('http'):
                    return m.group(1)

            print(f"        [WARNING] No direct Google link found")
            return final if "googleusercontent" in final else None

        except Exception as e:
            print(f"        [RESOLVE ERROR] {type(e).__name__}")
            return None


def scrape_website(url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    scraper = VegamoviesScraper()
    return scraper.scrape(url, quality_filter)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vg.py <vegamovies_url> [quality]")
        print("Example: python vg.py 'https://vegamovies.nf/xxxx-movie.html' '1080p'")
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"\n[ULTRA MODE] Vegamovies Scraper v6.0")
    print(f"[TARGET] {url} | Quality: {quality or 'ALL'}\n")

    results = scrape_website(url, quality)

    if results:
        print(f"\n{'='*100}")
        print("FINAL DIRECT DOWNLOAD LINKS")
        print(f"{'='*100}\n")
        for i, r in enumerate(results, 1):
            filename = f"{r['show_name'].replace(' ', '.')}.S{r['season']}E{r['episode']}.{r['quality']}.{r['size'].replace(' ', '')}.mkv"
            print(f"[{i}] {filename}")
            print(f"    Quality : {r['quality']}")
            print(f"    Size    : {r['size']}")
            print(f"    Link    : {r['url']}\n")
        print(f"Total direct links: {len(results)}")
    else:
        print("[ERROR] No direct links resolved. Site structure may have changed.")
        sys.exit(1)