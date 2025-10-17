# src/proxy.py 
import requests
from bs4 import BeautifulSoup
import re
import time

# لیست وب‌سایت‌هایی که پروکسی‌ها را از آن‌ها استخراج می‌کنیم
urls = [
    "https://www.freeproxy.world/?type=http&anonymity=&country=IR&speed=&port=&page=1",
    "https://hidemy.name/en/proxy-list/countries/iran",
    "https://www.proxynova.com/proxy-server-list/country-ir",
    "http://free-proxy.cz/en/proxylist/country/IR/all/ping/all",
    "https://www.ditatompel.com/proxy/country/ir",
    "https://spys.one/free-proxy-list/IR/",
    "https://proxy-spider.com/proxies/locations/ir-iran",
    "https://freeproxyupdate.com/iran-ir",
    "https://premiumproxy.net/top-country-proxy-list/IR-Iran/"
]

# هدرها برای جلوگیری از بلاک شدن توسط وب‌سایت‌ها
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# لیست برای ذخیره پروکسی‌ها
proxies = []

def extract_proxies(url):
    try:
        print(f"در حال استخراج پروکسی‌ها از: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # بررسی خطاهای HTTP
        soup = BeautifulSoup(response.text, 'html.parser')

        # تابع‌های خاص برای هر وب‌سایت
        if "freeproxy.world" in url:
            proxy_rows = soup.select("table tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append(f"{ip}:{port}")

        elif "hidemy.name" in url:
            proxy_rows = soup.select("table.proxy__t tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1 and "http" in cols[4].text.lower():
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append(f"{ip}:{port}")

        elif "proxynova.com" in url:
            proxy_rows = soup.select("table#tbl_proxy_list tbody tr")
            for row in proxy_rows:
                ip_script = row.find("td", recursive=False)
                if ip_script and ip_script.find("abbr"):
                    ip = re.search(r'(\d+\.\d+\.\d+\.\d+)', ip_script.text)
                    port = row.find_all("td")[1].text.strip()
                    if ip:
                        proxies.append(f"{ip.group(1)}:{port}")

        elif "free-proxy.cz" in url:
            proxy_rows = soup.select("table#proxy_list tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip_script = cols[0].find("script")
                    if ip_script:
                        ip = re.search(r'(\d+\.\d+\.\d+\.\d+)', ip_script.text)
                        port = cols[1].text.strip()
                        if ip:
                            proxies.append(f"{ip.group(1)}:{port}")

        elif "ditatompel.com" in url:
            proxy_rows = soup.select("table.table tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1 and "http" in cols[2].text.lower():
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append(f"{ip}:{port}")

        elif "spys.one" in url:
            proxy_rows = soup.select("table table tr")[2:]  # رد کردن هدرها
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1 and "http" in cols[1].text.lower():
                    ip_port = cols[0].text.strip()
                    if ":" in ip_port:
                        proxies.append(ip_port)

        elif "proxy-spider.com" in url:
            proxy_rows = soup.select("div.proxy-list table tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1 and "http" in cols[2].text.lower():
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append(f"{ip}:{port}")

        elif "freeproxyupdate.com" in url:
            proxy_rows = soup.select("table tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append(f"{ip}:{port}")

        elif "premiumproxy.net" in url:
            proxy_rows = soup.select("table.table tbody tr")
            for row in proxy_rows:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append(f"{ip}:{port}")

    except Exception as e:
        print(f"خطا در استخراج از {url}: {e}")

def save_proxies():
    # حذف پروکسی‌های تکراری
    unique_proxies = list(set(proxies))
    with open("proxies.txt", "w") as f:
        for proxy in unique_proxies:
            f.write(f"{proxy}\n")
    print(f"تعداد پروکسی‌های ذخیره‌شده: {len(unique_proxies)}")

def main():
    for url in urls:
        extract_proxies(url)
        time.sleep(2)  # تأخیر برای جلوگیری از بلاک شدن
    save_proxies()

if __name__ == "__main__":
    main()