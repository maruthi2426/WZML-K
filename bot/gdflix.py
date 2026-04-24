# GDFLIX
import sys
import json
import random
import time
import re
from urllib.parse import urlparse, urljoin, parse_qs, urlencode
from curl_cffi import requests
from bs4 import BeautifulSoup

# Ensure terminal can display special characters
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def load_proxies(file_path="proxies.txt"):
    try:
        with open(file_path, "r") as f:
            return [line.strip().strip('",').strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

def strip_fastcdn_proxy(url_str: str) -> str:
    """Remove fastcdn-dl.pages.dev/?url= wrapper if present"""
    if 'fastcdn-dl.pages.dev/?url=' not in url_str:
        return url_str
    
    try:
        # Take part after ?url=
        after = url_str.split('fastcdn-dl.pages.dev/?url=', 1)[1]
        # Take until next & or end
        param_value = after.split('&', 1)[0]
        # Decode if it's query-encoded
        decoded = parse_qs(param_value).get('url', [param_value])[0]
        print(f"[*] Stripped fastcdn proxy → {decoded[:140]}...")
        return decoded
    except Exception as e:
        print(f"[!] Failed to strip fastcdn proxy from {url_str[:80]}...: {e}")
        return url_str

def follow_redirect_and_extract(final_url, session, base_referer, max_redirects=3):
    """Follow redirects for links like busycdn to get the final direct URL (e.g., pure GD without proxy). Handle quota errors."""
    try:
        final_url = strip_fastcdn_proxy(final_url)  # ← added

        headers = session.headers.copy()
        headers['Referer'] = base_referer
        resp = session.get(final_url, headers=headers, allow_redirects=True, timeout=15)
        
        if resp.status_code == 200:
            final_location = resp.url
            final_location = strip_fastcdn_proxy(final_location)  # ← added again after redirect

            if 'drive.google.com' in final_location or 'googleusercontent.com' in final_location:
                if 'quotaExceeded' in resp.text or 'download quota' in resp.text.lower():
                    print(f"[!] Quota exceeded for GD link")
                    return {'gd_direct_quota': final_location}
                print(f"[+] Clean GD direct found: {final_location[:140]}...")
                return {'gd_direct': final_location}
            
            elif 'r2.dev' in final_location:
                return {'r2_direct': final_location}
            
            elif 'pixeldrain.dev' in final_location:
                return {'pixeldrain_direct': final_location}
        
        return {'redirect_final': final_location}
    
    except Exception as e:
        print(f"[-] Redirect follow failed for {final_url}: {e}")
        return {'error': str(e)}

def fetch_and_extract_mirrors(mirror_url, session, base_referer):
    """Fetch a mirror page (e.g., goflix.sbs) and extract sub-download links with expanded hosts."""
    try:
        mirror_url = strip_fastcdn_proxy(mirror_url)  # ← added
        headers = session.headers.copy()
        headers['Referer'] = base_referer
        resp = session.get(mirror_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return {}
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        sub_mirrors = {}
        
        # Expanded host matching
        hosts = {
            'gofile': ['gofile.io'],
            'megaup': ['megaup.net'],
            '1fichier': ['1fichier.com'],
            'pixeldrain': ['pixeldrain.dev'],
            'index_zip': ['awscdn.rest', 'oest.awscdn.rest'],
            'r2': ['r2.dev'],
            'gd_direct': ['drive.google.com', 'googleusercontent.com']
        }
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_href = urljoin(mirror_url, href) if not href.startswith('http') else href
            full_href = strip_fastcdn_proxy(full_href)  # ← added
            text = a.get_text(strip=True).lower()
            
            for key, domains in hosts.items():
                if any(domain in full_href.lower() for domain in domains):
                    sub_mirrors[key] = full_href
                    print(f"[+] {key} sub-link: {full_href}")
                    break
        
        # Fallback: regex for long URLs in text
        long_links = re.findall(r'https?://[^\s<>"\']{50,}', resp.text)
        for link in long_links:
            link = strip_fastcdn_proxy(link)
            if '::' in link and any(d in link.lower() for d in ['awscdn', 'google']):
                sub_mirrors['index_zip'] = link
                print(f"[+] index_zip regex fallback: {link}")
                break
        
        return sub_mirrors
    except Exception as e:
        print(f"[-] Failed to extract mirrors from {mirror_url}: {e}")
        return {}

def extract_index_directs(zipdisk_url, session, base_referer):
    """Fetch zipdisk page and extract direct index/zip links (long URLs with :: or ?token=)."""
    try:
        zipdisk_url = strip_fastcdn_proxy(zipdisk_url)  # ← added
        headers = session.headers.copy()
        headers['Referer'] = base_referer
        resp = session.get(zipdisk_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"[-] Zipdisk fetch failed: {resp.status_code}")
            return {}
        
        # Extract long direct links (with :: or ?token= containing filename)
        directs = re.findall(r'https?://[^\s<>"\']{100,}', resp.text)  # Long URLs
        index_links = {}
        for i, link in enumerate(directs[:3], 1):  # Limit to 3
            link = strip_fastcdn_proxy(link)  # ← added here
            if '::' in link or '?token=' in link or 'googleusercontent.com' in link or 'r2.dev' in link or 'aws-eu.online' in link:
                index_links[f'index_direct{i}'] = link
                print(f"[+] Index direct {i}: {link[:140]}...")
        
        # Fallback: find all a href with download attributes or long href
        soup = BeautifulSoup(resp.text, 'html.parser')
        i = len(index_links) + 1
        for a in soup.find_all('a', href=True):
            href = a['href']
            if (len(href) > 100 or 'download' in a.get('class', []) or 'dl' in href.lower() or 'index' in href.lower()) and href.startswith('http'):
                full_href = urljoin(zipdisk_url, href)
                full_href = strip_fastcdn_proxy(full_href)  # ← added
                if f'index_direct{i}' not in index_links:
                    index_links[f'index_direct{i}'] = full_href
                    print(f"[+] Index fallback {i}: {full_href[:140]}...")
                    i += 1
        
        return index_links
    except Exception as e:
        print(f"[-] Index extraction failed: {e}")
        return {}

def extract_single_file_mirrors(file_url, session, base_referer, proxy_list, max_retries=3):
    """Extract mirrors for a single file URL (recursive call for packs)."""
    # Reuse the core logic from get_gdflix_data but simplified for sub-calls
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        sub_session = requests.Session(impersonate="chrome110")
        if proxy_list:
            proxy = random.choice(proxy_list)
            sub_session.proxies = {"http": proxy, "https": proxy}
        
        try:
            sub_session.headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1"
            })
            
            landing_res = sub_session.get(file_url, timeout=15)
            if landing_res.status_code != 200:
                continue
            
            soup = BeautifulSoup(landing_res.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else ""
            filename = title.split(' | ', 1)[1] if ' | ' in title else "Unknown"
            
            size_match = re.search(r'([\d.]+)\s*(GB|MB|KB)', landing_res.text)
            size = size_match.group(1) if size_match else "Unknown"
            unit = size_match.group(2) if size_match else ""
            filesize = f"{size} {unit}" if size != "Unknown" else "Unknown"
            
            mirrors = {}
            all_links = re.findall(r'https?://[^\s<>"\']+', landing_res.text)
            
            # Quick extraction for instant / pixeldrain / etc. (simplified)
            for link in all_links:
                link_clean = strip_fastcdn_proxy(link)
                l_lower = link_clean.lower()
                if 'busycdn.xyz' in l_lower:
                    redirects = follow_redirect_and_extract(link_clean, sub_session, file_url)
                    if 'gd_direct' in redirects:
                        mirrors['instant'] = redirects['gd_direct']
                elif 'pixeldrain.dev' in l_lower:
                    mirrors['pixeldrain'] = link_clean
                elif 't.me' in l_lower:
                    mirrors['telegram'] = link_clean
            
            # Zipdisk / index if present
            for link in all_links:
                if '/zfile/' in link or 'zipdisk' in link.lower():
                    index_directs = extract_index_directs(strip_fastcdn_proxy(link), sub_session, file_url)
                    if index_directs:
                        mirrors['index_zip'] = index_directs[list(index_directs.keys())[0]]
                    break
            
            return {
                "filename": filename,
                "filesize": filesize,
                "mirrors": mirrors
            }
        
        except Exception as e:
            print(f"[-] Sub-file extract error: {e}")
            time.sleep(0.5)
    
    return {"filename": "Unknown", "filesize": "Unknown", "mirrors": {}}

def extract_pack_episodes(pack_url, session, base_referer, proxy_list, max_episodes=20):
    """Advanced pack bypass: Extract all episode file URLs from pack page and get mirrors for each."""
    try:
        headers = session.headers.copy()
        headers['Referer'] = base_referer
        resp = session.get(pack_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"[-] Pack page fetch failed: {resp.status_code}")
            return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Extract pack name (from title or h1)
        pack_title = soup.title.string.strip() if soup.title else "Unknown Pack"
        pack_name = pack_title.split(' | ', 1)[0] if ' | ' in pack_title else pack_title
        
        episodes = []
        episode_links = []
        
        # Find all episode links: <a> with href starting with /file/
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/file/') and len(href.split('/')[-1]) > 5:  # Valid file ID
                full_url = urljoin(pack_url, href)
                episode_links.append(full_url)
                print(f"[+] Found episode link: {full_url}")
        
        # Limit to max_episodes to avoid overload
        for ep_url in episode_links[:max_episodes]:
            print(f"[*] Extracting mirrors for: {ep_url}")
            ep_data = extract_single_file_mirrors(ep_url, session, pack_url, proxy_list)
            episodes.append(ep_data)
            time.sleep(0.8)  # Rate limit
        
        print(f"[+] Pack '{pack_name}' extracted {len(episodes)} episodes")
        return [{"pack_name": pack_name, "episodes": episodes}]
    
    except Exception as e:
        print(f"[-] Pack extraction failed: {e}")
        return []

def get_gdflix_data(url, proxy_list, max_retries=5):
    parsed = urlparse(url)
    path = parsed.path
    
    # Detect pack vs single file
    if '/pack/' in path:
        print("[*] Detected PACK URL - starting advanced pack bypass...")
        session = requests.Session(impersonate="chrome110")
        if proxy_list:
            proxy = random.choice(proxy_list)
            session.proxies = {"http": proxy, "https": proxy}
        return extract_pack_episodes(url, session, url, proxy_list)
    
    # Original single file logic
    file_id = path.split("/")[-1]
    domain = parsed.scheme + "://" + parsed.netloc
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        session = requests.Session(impersonate="chrome110")
        
        proxy = None
        if proxy_list:
            proxy = random.choice(proxy_list)
            session.proxies = {"http": proxy, "https": proxy}
            print(f"[*] Attempt {attempt}: Using Proxy {proxy.split('@')[-1] if '@' in proxy else proxy}")
        else:
            print(f"[*] Attempt {attempt}: No proxy provided. Using local IP.")
        
        try:
            # Headers for landing page
            session.headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1"
            })
            
            # Step 1: Get landing page
            print(f"[*] Fetching landing page...")
            landing_res = session.get(url, timeout=15)
            print(f"[*] Landing status: {landing_res.status_code}")
            if landing_res.status_code != 200:
                print(f"[-] Blocked on landing page (Status {landing_res.status_code}). Retrying...")
                time.sleep(1)
                continue
            
            # Parse metadata from HTML
            soup = BeautifulSoup(landing_res.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else ""
            filename = title.split(' | ', 1)[1] if ' | ' in title else "Unknown"
            
            # Extract size
            size_match = re.search(r'([\d.]+)\s*(GB|MB|KB)', landing_res.text)
            size = size_match.group(1) if size_match else "Unknown"
            unit = size_match.group(2) if size_match else ""
            filesize = f"{size} {unit}" if size != "Unknown" else "Unknown"
            
            print(f"[*] Parsed filename: {filename}")
            print(f"[*] Parsed filesize: {filesize}")
            
            result = {
                "filename": filename,
                "filesize": filesize,
                "mirrors": {}
            }
            
            # Step 2: Enhanced extraction from landing page with exact button texts
            print(f"[*] Scraping landing page for download buttons...")
            button_selectors = [
                ('instant', ['Instant DL [10GBPS]', 'Instant DL']),
                ('cloud_r2', ['CLOUD DOWNLOAD [R2]', 'Cloud Download [R2]']),
                ('login_dl', ['LOGIN TO DL [10GBPS]', 'Login to DL']),
                ('zipdisk', ['FAST CLOUD / ZIPDISK', 'Fast Cloud / Zipdisk']),
                ('pixeldrain', ['PixelDrain DL [20MB/s]', 'PixelDrain']),
                ('telegram', ['Telegram File', 'Telegram Generate']),
                ('gofile_multiup', ['GOFILE [MULTIUP]', 'Gofile [Multiup]', 'GoFile'])
            ]
            
            all_links = re.findall(r'https?://[^\s<>"\']+', landing_res.text)
            
            for key, patterns in button_selectors:
                found = False
                # Try exact string match in <a> text
                for pattern in patterns:
                    a_tag = soup.find('a', string=lambda t: t and pattern in t.strip() if t else False)
                    if a_tag and a_tag.get('href'):
                        href = a_tag['href']
                        full_href = urljoin(domain, href) if not href.startswith('http') else href
                        full_href = strip_fastcdn_proxy(full_href)  # ← added
                        result["mirrors"][key] = full_href
                        print(f"[+] {key} button direct: {full_href}")
                        found = True
                        break
                
                if not found and key in ['instant', 'cloud_r2', 'pixeldrain', 'telegram', 'gofile_multiup']:
                    # Fallback: domain-specific in all_links
                    for link in all_links:
                        link_lower = link.lower()
                        link_clean = strip_fastcdn_proxy(link)  # ← added
                        if key == 'instant' and 'busycdn.xyz' in link_lower:
                            print(f"[+] {key} fallback (cleaned): {link_clean}")
                            # Follow redirect → should give gd_direct most times
                            redirects = follow_redirect_and_extract(link_clean, session, url)
                            if 'gd_direct' in redirects:
                                # Replace instant with the direct GD link
                                result["mirrors"][key] = redirects['gd_direct']
                                print(f"[+] {key} replaced with direct GD: {redirects['gd_direct'][:140]}...")
                            else:
                                result["mirrors"][key] = link_clean
                            break
                        elif key == 'cloud_r2' and 'r2.dev' in link_lower and '?token=' in link_clean:
                            result["mirrors"][key] = link_clean
                            print(f"[+] {key} direct fallback: {link_clean}")
                            break
                        elif key == 'pixeldrain' and 'pixeldrain.dev' in link_lower:
                            result["mirrors"][key] = link_clean
                            print(f"[+] {key} fallback: {link_clean}")
                            break
                        elif key == 'telegram' and ('filesgram.site' in link_lower or 't.me' in link_lower):
                            result["mirrors"][key] = link_clean
                            print(f"[+] {key} fallback: {link_clean}")
                            break
                        elif key == 'gofile_multiup' and ('goflix.sbs' in link_lower or 'gofile.io' in link_lower):
                            result["mirrors"][key] = link_clean
                            print(f"[+] {key} fallback: {link_clean}")
                            break
            
            # Redesigned Step 3: Handle Zipdisk as Index - fetch and extract index directs (removed zfile naming)
            if 'zipdisk' in result["mirrors"]:
                zipdisk_url = result["mirrors"]['zipdisk']
                index_directs = extract_index_directs(zipdisk_url, session, url)
                # Prioritize first direct as main index_zip
                if index_directs:
                    result["mirrors"]['index_zip'] = index_directs[list(index_directs.keys())[0]]
                    zip_url = result["mirrors"]['index_zip'][:140]
                    print(f"[+] Index/Zip from zipdisk: {zip_url}...")
                # Add extras if any
                result["mirrors"].update({k: v for k, v in index_directs.items() if k != list(index_directs.keys())[0]})
                print(f"[+] Zipdisk parent (now index source): {zipdisk_url}")
            else:
                # Fallback search for zipdisk in all_links
                for link in all_links:
                    if '/zfile/' in link:
                        index_directs = extract_index_directs(link, session, url)
                        if index_directs:
                            result["mirrors"]['index_zip'] = index_directs[list(index_directs.keys())[0]]
                            result["mirrors"].update({k: v for k, v in index_directs.items() if k != list(index_directs.keys())[0]})
                            print(f"[+] Index/Zip fallback from {link}")
                            break
            
            # Step 4: Enhanced Index/Zip search (for any awscdn) - now secondary to zipdisk
            for link in all_links:
                link_clean = strip_fastcdn_proxy(link)  # ← added
                if any(d in link_clean.lower() for d in ['awscdn.rest', 'oest.awscdn.rest', 'video-downloads.googleusercontent.com', 'pest.aws-eu.online', 'jest.aws-eu.online']) and 'index_zip' not in result["mirrors"]:
                    result["mirrors"]['index_zip'] = link_clean
                    print(f"[+] Index/Zip fallback: {link_clean}")
                    if '::' in link_clean:
                        redirects = follow_redirect_and_extract(link_clean, session, url)
                        result["mirrors"].update(redirects)
                    break
            
            # Step 5: Handle GoFile Multiup with expanded subs
            if 'gofile_multiup' in result["mirrors"]:
                multiup_url = result["mirrors"]['gofile_multiup']
                sub_mirrors = fetch_and_extract_mirrors(multiup_url, session, url)
                result["mirrors"].update(sub_mirrors)
                print(f"[+] GoFile Multiup parent: {multiup_url}")
            
            # Step 6: GD Index /wfile mirrors (enhanced, but prioritize index over wfile if present)
            if 'index_zip' not in result["mirrors"]:
                print(f"[*] Fetching wfile page...")
                wfile_url = f"{domain}/wfile/{file_id}"
                wfile_headers = session.headers.copy()
                wfile_headers['Referer'] = url
                wfile_res = session.get(wfile_url, headers=wfile_headers, timeout=15)
                print(f"[*] Wfile status: {wfile_res.status_code}")
                if wfile_res.status_code == 200:
                    w_soup = BeautifulSoup(wfile_res.text, 'html.parser')
                    server_links = []
                    for a in w_soup.find_all('a', href=True):
                        href = a['href']
                        if '?type=' in href:
                            full_link = urljoin(domain, href)
                            full_link = strip_fastcdn_proxy(full_link)  # ← added
                            server_links.append(full_link)
                            print(f"[*] Found wfile server: {full_link}")
                    
                    # Sort by type asc
                    server_links.sort(key=lambda x: int(x.split('type=')[-1].split('&')[0] if '&' not in x.split('type=')[-1] else x.split('type=')[-1].split('&')[0]))
                    
                    for sl in server_links[:2]:
                        sl_headers = session.headers.copy()
                        sl_headers['Referer'] = wfile_url
                        print(f"[*] Fetching wfile server {sl}...")
                        s_res = session.get(sl, headers=sl_headers, timeout=15)
                        print(f"[*] Wfile server status: {s_res.status_code}")
                        if s_res.status_code == 200:
                            patterns = [
                                r"let worker_url\s*=\s*'([^']*)'",
                                r"const url\s*=\s*'([^']*)'",
                                r"location\.href\s*=\s*'([^']*)'",
                                r"window\.open\s*\(\s*'([^']*)'"
                            ]
                            found = False
                            for pat in patterns:
                                match = re.search(pat, s_res.text)
                                if match:
                                    direct_url = match.group(1)
                                    direct_url = strip_fastcdn_proxy(direct_url)  # ← added
                                    mirror_type = sl.split('type=')[-1].split('&')[0] if '&' in sl else sl.split('type=')[-1]
                                    result["mirrors"][f"gd_server{mirror_type}"] = direct_url
                                    print(f"[+] GD Server {mirror_type}: {direct_url[:140]}...")
                                    if 'quotaExceeded' in s_res.text:
                                        print(f"[!] Possible quota on GD Server {mirror_type}")
                                    found = True
                                    break
                            
                            if not found:
                                # Fallback long href
                                s_soup = BeautifulSoup(s_res.text, 'html.parser')
                                for a in s_soup.find_all('a', href=True):
                                    href = a['href']
                                    if href.startswith('http') and (len(href) > 50 or 'download' in href.lower()):
                                        full_href = urljoin(sl, href)
                                        full_href = strip_fastcdn_proxy(full_href)  # ← added
                                        mirror_type = sl.split('type=')[-1].split('&')[0] if '&' in sl else sl.split('type=')[-1]
                                        result["mirrors"][f"gd_server{mirror_type}"] = full_href
                                        print(f"[+] GD Server {mirror_type} fallback: {full_href[:140]}...")
                                        break
            
            # Return result
            if result["mirrors"]:
                print("[+] Mirrors found!")
            else:
                print("[-] No mirrors found this attempt")
            return result
            
        except Exception as e:
            print(f"[-] Error on attempt {attempt}: {str(e)}")
            time.sleep(1)
    
    return {"error": "All attempts failed. Try without proxies or check your proxy quality."}

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://new15.gdflix.net/file/AqHd1P8JaLZrEKa"
    proxies = load_proxies("proxies.txt")
    
    output = get_gdflix_data(target, proxies)
    print(json.dumps(output, indent=2))