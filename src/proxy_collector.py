# src/proxy_collector.py
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import logging
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from src.db import save_proxies_bulk
from src.utils import load_config

logger = logging.getLogger(__name__)
config = load_config()
urls = config["proxy"]["sources"]
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
max_per_site = 50

@retry(stop=stop_after_attempt(5), wait=wait_exponential())
async def fetch_url(session, url):
    async with session.get(url, headers=headers, timeout=10) as response:
        response.raise_for_status()
        return await response.text()

async def process_site(url, session):
    proxies = []
    try:
        response = await fetch_url(session, url)
        soup = BeautifulSoup(response, 'html.parser')

        if "freeproxy.world" in url:
            rows = soup.select("table tbody tr")
            for row in rows[:max_per_site]:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append((ip, port))

        # (سایر if/elif برای سایت‌ها مشابه نسخه قبلی sync، اما با soup و rows)
        # مثلاً برای hidemy.name: rows = soup.select("table.proxy__t tbody tr")
        # ... (کپی از کد قبلی، تغییر به async soup)

        elif "premiumproxy.net" in url:
            rows = soup.select("table.table tbody tr")
            for row in rows[:max_per_site]:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    proxies.append((ip, port))

        logger.info(f"{len(proxies)} پروکسی از {url} استخراج شد.")
    except Exception as e:
        logger.error(f"خطا در {url}: {e}")
    return proxies

async def collect_proxies(db_path: str = None):
    proxies = []
    async with aiohttp.ClientSession() as session:
        tasks = [process_site(url, session) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                proxies.extend(result)
    unique_proxies = list(set(proxies))
    os.makedirs("cache", exist_ok=True)
    file_path = "cache/proxies.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        for ip, port in unique_proxies:
            f.write(f"{ip}:{port}\n")
    if db_path:
        save_proxies_bulk(db_path, unique_proxies)
    logger.info(f"{len(unique_proxies)} پروکسی منحصر به فرد ذخیره شد.")
    return file_path, len(unique_proxies)