"""
Vegamovies Direct Link Scraper v3.0
Pure Python scraper (no Chrome required) to extract direct download links from Vegamovies
Supports quality filtering and both movie and series content
"""

import sys
import re
import time
from urllib.parse import urljoin
import subprocess

# Auto-install dependencies
def _ensure_dependency(package_name, import_name=None):
    """Auto-install missing dependencies"""
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        print(f"[INFO] Installing {package_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "-q"])
            return True
        except Exception as e:
            print(f"[ERROR] Failed to install {package_name}: {e}")
            return False

# Ensure all dependencies are installed
_ensure_dependency("requests", "requests")
_ensure_dependency("beautifulsoup4", "bs4")
_ensure_dependency("lxml", "lxml")

import requests
from bs4 import BeautifulSoup


class VegamoviesScraper:
    def __init__(self):
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.session.headers.update({"User-Agent": self.user_agent})

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
        print(f"[INFO] VEGAMOVIES SCRAPER v3.0")
        print(f"[INFO] URL: {url}")
        if quality_filter:
            print(f"[INFO] Quality Filter: {quality_filter}")
        print(f"{'='*80}\n")

        results = []

        try:
            # Fetch page
            print(f"[INFO] Fetching page...")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            html = response.text
            print(f"[INFO] Page fetched successfully (Status: {response.status_code})")
            
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

        except Exception as e:
            print(f"[ERROR] Scraping error: {str(e)}")
            raise

    def _resolve_shortener(self, short_url):
        """Resolve shortener URL to get direct download link"""
        try:
            # Follow redirects with timeout
            response = self.session.get(short_url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            html = response.text
            
            soup = BeautifulSoup(html, "lxml")
            
            # Extract direct links from page
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http') and not any(x in href.lower() for x in ["nexdrive", "fast-dl", "short", "bit.ly"]):
                    if any(x in href.lower() for x in ["googledrive", "drive.google", "video-downloads.googleusercontent", "download", "dl"]):
                        return href

            # Also check in page source for direct links
            direct_links = re.findall(r'https?://[^\s"\'<>]+(?:video-downloads\.googleusercontent|googledrive)', html)
            if direct_links:
                return direct_links[0]

            # Try finding in meta refresh
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                meta_url = re.search(r'url=([^;]+)', content)
                if meta_url:
                    return meta_url.group(1)

            # Try finding in script tags
            for script in soup.find_all('script'):
                if script.string:
                    urls = re.findall(r'(https?://[^\s"\'<>]+)', script.string)
                    for u in urls:
                        if any(x in u.lower() for x in ["googledrive", "drive.google", "video-downloads.googleusercontent"]):
                            return u

            return None

        except Exception as e:
            print(f"        [ERROR] Resolution failed: {str(e)}")
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
    
    results = scrape_website(url, quality)
    
    if results:
        print(f"\n{'='*80}")
        print("DIRECT DOWNLOAD LINKS")
        print(f"{'='*80}\n")
        for r in results:
            filename = f"{r['show_name'].replace(' ', '.')}.S{r['season']}E{r['episode'].replace('EP', '')}.{r['quality']}.{r['size']}.mkv"
            print(f"File: {filename}")
            print(f"Link: {r['url']}\n")
