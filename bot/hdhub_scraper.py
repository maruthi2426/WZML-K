import sys
import re
import random
import time
from datetime import datetime
import requests

# Try to import BeautifulSoup, install if missing
try:
    from bs4 import BeautifulSoup
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "-q"])
        from bs4 import BeautifulSoup
        print("[INFO] beautifulsoup4 installed successfully")
    except Exception as e:
        print(f"[WARNING] Failed to install beautifulsoup4: {e}")
        BeautifulSoup = None

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def load_proxies(file_path="proxies.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip().strip('",') for line in f if line.strip()]
    except Exception:
        print("[!] proxies.txt not found → no proxies used")
        return []

def bypass_hubcloud(hubcloud_url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    print(f"  ↳ Bypassing HubCloud: {hubcloud_url[:80]}...")

    try:
        print(f"[*] Fetching HubCloud page...")
        r = session.get(hubcloud_url, headers=headers, timeout=15, allow_redirects=True)
        print(f"[*] HubCloud status: {r.status_code}")
        if r.status_code != 200:
            print(f"[-] HubCloud fetch failed with status {r.status_code}")
            return {"error": f"HubCloud status {r.status_code}"}

        soup = BeautifulSoup(r.text, 'html.parser')
        gamer_url = None
        
        # Enhanced redirect detection
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if 'gamerxyt.com' in href or 'monostream' in href or 'gadgetsweb' in href:
                gamer_url = href
                print(f"[+] Found redirect: {gamer_url[:80]}...")
                break
        
        # Try script-based redirect
        if not gamer_url:
            import re
            script_match = re.search(r'window\.location\s*=\s*["\']([^"\']+)["\']', r.text)
            if script_match:
                gamer_url = script_match.group(1)
                print(f"[+] Found script redirect: {gamer_url[:80]}...")

        if not gamer_url:
            print(f"[-] No redirect URL found in HubCloud page")
            return {"error": "No redirect found on HubCloud page"}

        print(f"[*] Following redirect to bypass server...")
        r2 = session.get(gamer_url, headers=headers, timeout=15, allow_redirects=True)
        print(f"[*] Bypass server status: {r2.status_code}")
        if r2.status_code != 200:
            print(f"[-] Bypass server returned {r2.status_code}")
            return {"error": f"Bypass server status {r2.status_code}"}

        soup2 = BeautifulSoup(r2.text, 'html.parser')
        result = {}

        # FSL Server with dynamic minute
        for a in soup2.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            href = a.get('href', '')
            if 'fsl server' in txt or 'fsl' in href.lower():
                base = href.rstrip('/')
                min_pad = f"{datetime.now().minute:02d}"
                result["FSL_Server"] = f"{base}1{min_pad}"
                print(f"[+] Found FSL Server")
                break

        for a in soup2.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            href = a.get('href', '')
            if '10gbps' in txt or '10gbps' in href.lower():
                result["10Gbps_Server"] = href
                print(f"[+] Found 10Gbps Server")
                break

        for a in soup2.find_all('a', href=True):
            href = a.get('href', '')
            txt = a.get_text(strip=True).lower()
            if 'pixeldrain' in href.lower() or 'pixeldrain' in txt:
                result["Pixeldrain"] = href
                print(f"[+] Found Pixeldrain link")
                break

        if result:
            print(f"[+] HubCloud bypass successful - found {len(result)} link(s)")
            return result
        else:
            print(f"[-] No servers found after bypass")
            return {"error": "No servers found after bypass"}

    except Exception as e:
        print(f"[-] HubCloud bypass error: {str(e)}")
        return {"error": str(e)}

def get_hdhub_data(url, proxy_list=None):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    if proxy_list:
        try:
            proxy = random.choice(proxy_list)
            session.proxies = {"http": proxy, "https": proxy}
            print(f"[*] Using proxy: {proxy}")
        except IndexError:
            print("[*] No proxies → direct connection")

    print(f"[*] Fetching: {url}")
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e), "title": "Fetch failed"}

    soup = BeautifulSoup(resp.text, 'lxml')
    title = (soup.title.string or "Unknown").strip().split(' – HDHub4u')[0].strip()

    content = (soup.find('div', class_=re.compile(r'(entry-content|post-content|td-post-content|content)', re.I)) or
               soup.find('article') or soup.body)
    full_text = content.get_text(separator='\n', strip=True) if content else ""

    pattern = r'(?im)^\s*[\#*\-⚡️\s\d\.]+\s*\[+\s*([^\]]+?)\s*\]+\s*\(\s*(https?://[^\s\)]+)\s*\)'

    matches = re.findall(pattern, full_text)

    if len(matches) < 5:
        loose = r'(?i)(sample|480p|720p|1080p|hq|4k|ds4k).*?(https?://[^\s<>\n"]+)'
        extra = re.findall(loose, full_text)
        matches.extend([(q.strip(), u.strip()) for q, u in extra])

    seen = set()
    items = []

    for raw_label, link in matches:
        link = link.strip()
        if link in seen or not link.startswith('http'):
            continue
        seen.add(link)

        label = re.sub(r'^[#*\s\-⚡️\d\.]+', '', raw_label).strip()
        if not label:
            label = raw_label.strip()

        entry = {"quality": label, "url": link, "bypass": {}}

        if 'hubdrive.space/file/' in link:
            try:
                hd_resp = session.get(link, timeout=10, allow_redirects=False)
                if hd_resp.status_code in (301, 302, 303, 307, 308):
                    loc = hd_resp.headers.get('Location', '')
                    if 'hubcloud' in loc.lower():
                        bypassed = bypass_hubcloud(loc, session)
                        entry["bypass"] = bypassed
                    else:
                        entry["bypass"] = {"redirect": loc}
                else:
                    entry["bypass"] = {"direct": link}
            except Exception as e:
                entry["bypass"] = {"error": str(e)}

        elif any(x in link.lower() for x in ['hubcdn.fans', 'gadgetsweb.xyz', 'hblinks.dad']):
            entry["bypass"] = {"final": link}
        else:
            entry["bypass"] = {"direct": link}

        items.append(entry)
        time.sleep(0.5)

    print(f"[+] Found {len(items)} download items")
    return {"title": title, "items": items}

def print_result(data):
    if "error" in data:
        print(f"\nERROR: {data['error']}")
        return

    print(f"\n☰ {data['title']}")

    for i, entry in enumerate(data["items"], 1):
        print(f"{i}. {entry['quality']}")
        b = entry["bypass"]

        if "FSL_Server" in b:
            print(f"┠ Links : FSL Server ({b.get('FSL_Server', 'N/A')})")
            print(f"┠ Links : 10Gbps Server ({b.get('10Gbps_Server', 'N/A')})")
            print(f"┖ Links : Pixeldrain ({b.get('Pixeldrain', 'N/A')})")
        elif "final" in b:
            print(f"┖ Links : Download ({b['final']})")
        elif "redirect" in b:
            print(f"┖ Links : Redirect → {b['redirect']}")
        elif "direct" in b:
            print(f"┖ Links : Download ({b['direct']})")
        elif "error" in b:
            print(f"┖ Error: {b['error']}")
        else:
            print(f"┖ Links : {entry['url']}")

    print("\n━━━━━━━✦✗✦━━━━━━━")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python hdhub_scraper.py "https://..."')
        sys.exit(1)

    target = sys.argv[1]
    proxies = load_proxies()

    result = get_hdhub_data(target, proxies)
    print_result(result)
