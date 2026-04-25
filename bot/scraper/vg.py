"""
Vegamovies Direct Link Scraper v5.1
FIXED: Only scrapes the actual DOWNLOAD SECTION 
- Ignores related movies, sidebar, navigation, recommendations
- Only targets nexdrive / fast-dl.org / vgmlinks.app links inside download blocks
- Strict quality filtering before resolving
- Improved _resolve_shortener for nexdrive + fast-dl patterns
"""

import sys
import re
import time
import subprocess
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any

def _ensure_dependencies():
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
    """Advanced HTTP-based scraper for Vegamovies - DOWNLOAD SECTION ONLY"""
    
    def __init__(self):
        self.session = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._init_session()

    def _init_session(self):
        print("[INFO] Initializing HTTP session...")
        try:
            if create_scraper:
                self.session = create_scraper()
                print("[INFO] Using CloudScraper for advanced bypass")
            else:
                self.session = requests.Session()
                print("[INFO] Using standard requests session")
            
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
            
            self.session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            })
            print("[INFO] Session headers configured")
        except Exception as e:
            print(f"[WARNING] Failed to initialize advanced session: {e}")
            if requests:
                self.session = requests.Session()
                self.session.headers.update({"User-Agent": self.user_agent})

    def _load_page(self, url: str, timeout: int = 25) -> str:
        print(f"[INFO] Fetching URL: {url}")
        if not self.session:
            raise Exception("Session not initialized")
        
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            print(f"[INFO] Page loaded successfully (Status: {response.status_code}, Size: {len(response.text)} bytes)")
            return response.text
        except Exception as e:
            raise Exception(f"Failed to load page: {str(e)}")

    def _normalize_quality(self, quality_str: str) -> str:
        if not quality_str:
            return "unknown"
        q = quality_str.upper().strip()
        q = re.sub(r'\s+', '', q)
        return q

    def _extract_episode(self, text: str = "", url_slug: str = "") -> str:
        if url_slug:
            slug_match = re.search(r'ep[-_]0*(\d{1,3})', url_slug.lower())
            if slug_match:
                return f"EP{slug_match.group(1).zfill(2)}"

        if text:
            patterns = [
                r'ep[-_:\s]*0*(\d{1,3})',
                r'episode[-_:\s]*0*(\d{1,3})',
                r'\be(\d{2,3})\b',
            ]
            for pattern in patterns:
                match = re.search(pattern, text.lower())
                if match:
                    return f"EP{match.group(1).zfill(2)}"
        
        return "EP01"

    def scrape(self, url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        start_time = time.time()
        print(f"\n{'='*80}")
        print(f"[INFO] VEGAMOVIES SCRAPER v5.1 (DOWNLOAD SECTION ONLY)")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality Filter: {quality_filter} (strict)")
        print(f"{'='*80}\n")

        results = []

        try:
            html = self._load_page(url)
            
            if not BeautifulSoup:
                raise Exception("BeautifulSoup4 not available")
            
            soup = BeautifulSoup(html, "html.parser")

            # Extract clean title
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

            # === CRITICAL FIX: Only scan DOWNLOAD SECTION ===
            # Look for common download container classes/ids used on vegamovies
            download_containers = []
            
            # Common selectors for download blocks
            selectors = [
                "div[class*='download']", "div[id*='download']",
                "section[class*='download']", "div[class*='links']",
                "h2:contains('Download')", "h3:contains('Download')",
                ".entry-content", ".post-content", ".single-post"
            ]
            
            for sel in selectors:
                if sel.startswith("h"):
                    found = soup.find_all(['h2', 'h3'], string=re.compile(r'download', re.I))
                else:
                    found = soup.select(sel)
                download_containers.extend(found)

            # Fallback: whole content but filter aggressively later
            if not download_containers:
                download_containers = [soup]

            print(f"[INFO] Found {len(download_containers)} potential download container(s)")

            all_links = []
            current_quality = "UNKNOWN"
            current_size = "UNKNOWN"

            print(f"[INFO] Scanning DOWNLOAD SECTION only for nexdrive / fast-dl links...\n")

            for container in download_containers:
                # Get text for quality detection within this container
                container_text = container.get_text(strip=True)
                
                # Update current quality from headings inside container
                quality_match = re.search(r'(480p|720p|1080p|4k|2160p|HQ\s*1080p|HD\s*1080p)', container_text, re.I)
                if quality_match:
                    current_quality = quality_match.group(0).upper()
                
                size_match = re.search(r'(\d+\.?\d*)\s*(GB|MB)', container_text, re.I)
                if size_match:
                    current_size = f"{size_match.group(1)} {size_match.group(2)}".upper()

                # Now find ONLY relevant shortener links inside this container
                for link_element in container.find_all('a', href=True):
                    href = link_element.get('href', '').strip()
                    if not href or href == '#' or href.startswith('javascript:'):
                        continue
                    
                    if not href.startswith('http'):
                        href = urljoin(url, href)
                    
                    link_text = link_element.get_text(strip=True)
                    href_lower = href.lower()
                    text_lower = link_text.lower()

                    # STRICT FILTER: Only nexdrive, fast-dl, vgmlinks (as intermediate)
                    allowed_domains = ["nexdrive", "fast-dl.org", "vgmlinks.app"]
                    if not any(domain in href_lower for domain in allowed_domains):
                        continue

                    # Additional safety: skip if it's clearly a movie page link
                    if re.search(r'/(\d{4,5}-[a-z0-9-]+-\d{4})', href_lower) and "download" not in text_lower:
                        continue

                    episode = self._extract_episode(link_text, href)
                    
                    all_links.append({
                        "url": href,
                        "quality": current_quality,
                        "size": current_size,
                        "episode": episode,
                        "text": link_text
                    })
                    print(f"     [FOUND in DL section] {link_text[:60]} -> {href[:70]}... | Quality: {current_quality}")

            print(f"\n[INFO] Total relevant download links found in DOWNLOAD SECTION: {len(all_links)}\n")

            if not all_links:
                print("[ERROR] No nexdrive/fast-dl links found in download section")
                return results

            # === STRICT QUALITY FILTER ===
            if quality_filter and all_links:
                norm_filter = self._normalize_quality(quality_filter)
                filtered = []
                for link in all_links:
                    if self._normalize_quality(link["quality"]) == norm_filter or norm_filter in link["quality"].upper():
                        filtered.append(link)
                
                if filtered:
                    all_links = filtered
                    print(f"[INFO] Strict quality filter applied ({quality_filter}) → {len(all_links)} link(s) remaining")
                else:
                    print(f"[WARNING] No links matched exact quality {quality_filter}. Using best available.")
                    # fallback to all (but still only from DL section)

            # Resolve only the filtered relevant links
            if all_links:
                print(f"[INFO] Resolving {len(all_links)} short link(s) (nexdrive + fast-dl)...\n")
                
                for idx, link_info in enumerate(all_links, 1):
                    try:
                        print(f"[{idx}/{len(all_links)}] {link_info['quality']} | {link_info['size']} - {link_info['text'][:50]}")
                        print(f"     Short URL: {link_info['url'][:80]}...")
                        
                        direct_link = self._resolve_shortener(link_info["url"])
                        
                        if direct_link and direct_link.startswith("http"):
                            results.append({
                                "show_name": show_name,
                                "season": season,
                                "episode": link_info["episode"],
                                "quality": link_info["quality"],
                                "size": link_info["size"],
                                "url": direct_link
                            })
                            print(f"     [✓] DIRECT: {direct_link[:90]}...\n")
                        else:
                            print(f"     [✗] Could not resolve to direct link\n")
                    except Exception as e:
                        print(f"     [ERROR] Resolution failed: {str(e)}\n")

            elapsed = time.time() - start_time
            print(f"{'='*80}")
            print(f"[INFO] Scraping completed in {elapsed:.2f}s | Direct links: {len(results)}")
            print(f"{'='*80}\n")

            return results

        except Exception as e:
            print(f"[ERROR] Scraping failed: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def _resolve_shortener(self, short_url: str) -> Optional[str]:
        """Improved resolver focused on nexdrive + fast-dl patterns"""
        if not self.session:
            return None
        
        try:
            print(f"        [RESOLVE] {short_url}")
            
            # Fast-dl.org often redirects directly or has simple final URL
            if "fast-dl.org" in short_url:
                response = self.session.get(short_url, timeout=15, allow_redirects=True)
                final = response.url
                if "video-downloads.googleusercontent.com" in final or "/download" in final:
                    print(f"        [✓] Fast-DL direct: {final[:100]}")
                    return final
                # fallback
                return final

            # General handling
            response = self.session.get(short_url, timeout=20, allow_redirects=True)
            final_url = response.url
            print(f"        [DEBUG] Final after redirect: {final_url}")

            if not BeautifulSoup:
                return final_url if final_url != short_url else None

            soup = BeautifulSoup(response.text, "html.parser")
            page_text = response.text

            # Common direct Google Drive / video patterns
            direct_patterns = [
                r'https?://[^\s"\'<>]+video-downloads\.googleusercontent\.com[^\s"\'<>]*',
                r'https?://[^\s"\'<>]+drive\.google\.com[^\s"\'<>]*uc\?id=[^\s"\'<>]+',
                r'https?://[^\s"\'<>]+/download[^\s"\'<>]*',
            ]
            
            for pat in direct_patterns:
                matches = re.findall(pat, page_text)
                if matches:
                    direct = matches[0]
                    print(f"        [✓] Direct via regex: {direct[:100]}")
                    return direct

            # JS location redirects (common on nexdrive)
            js_patterns = [
                r'window\.location\s*=\s*["\']([^"\']+)["\']',
                r'location\.href\s*=\s*["\']([^"\']+)["\']',
                r'location\.replace\s*\(["\']([^"\']+)["\']',
            ]
            for pat in js_patterns:
                matches = re.findall(pat, page_text)
                for m in matches:
                    if m.startswith("http") and ("googleusercontent" in m or "drive.google" in m or "/download" in m):
                        print(f"        [✓] JS redirect direct: {m[:100]}")
                        return m

            # Meta refresh
            meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
            if meta and meta.get("content"):
                content = meta["content"]
                url_match = re.search(r'url\s*=\s*["\']?([^"\']+)', content, re.I)
                if url_match:
                    u = url_match.group(1)
                    if u.startswith("http"):
                        return u

            # If we reached a Google Drive viewer or direct, return it
            if any(x in final_url for x in ["video-downloads.googleusercontent.com", "drive.google.com/uc"]):
                return final_url

            print(f"        [WARNING] No direct link pattern matched for {short_url}")
            return None

        except Exception as e:
            print(f"        [ERROR] Resolve failed: {type(e).__name__}: {str(e)}")
            return None


def scrape_website(url: str, quality_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    print(f"[INFO] Starting Vegamovies scraper (v5.1 - Download Section Only)")
    scraper = VegamoviesScraper()
    try:
        return scraper.scrape(url, quality_filter)
    except Exception as e:
        print(f"[ERROR] Overall scraping failed: {type(e).__name__}: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vg.py <vegamovies_url> [quality]")
        print("Example: python vg.py 'https://vegamovies.nf/37740-...' '1080p'")
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        results = scrape_website(url, quality)
        
        if results:
            print(f"\n{'='*80}")
            print("✓ SUCCESS - DIRECT DOWNLOAD LINKS EXTRACTED (Download Section Only)")
            print(f"{'='*80}\n")
            for i, r in enumerate(results, 1):
                size_part = f".{r['size'].replace(' ', '.')}" if r['size'] != "UNKNOWN" else ""
                filename = f"{r['show_name'].replace(' ', '.')}.S{r['season']}E{r['episode'].replace('EP', '')}.{r['quality']}{size_part}.mkv"
                print(f"[{i}] {filename}")
                print(f"    Quality: {r['quality']}")
                print(f"    Size: {r['size']}")
                print(f"    Direct Link: {r['url']}\n")
            print(f"Total direct links: {len(results)}\n")
        else:
            print("[ERROR] No direct links extracted. Check logs above.")
            sys.exit(1)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)