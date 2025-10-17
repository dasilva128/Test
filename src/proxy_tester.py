# src/proxy_tester.py
import aiohttp
import asyncio
import logging
import os
from typing import List, Tuple
from src.db import get_proxies, get_db_connection, update_proxy_status
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("PROXYCHECK_API_KEY")
API_URL = "https://proxycheck.io/v2/{ip}?key={key}&vpn=1&asn=1&port={port}&seen=1"
logger = logging.getLogger(__name__)

async def test_proxy(ip: str, port: str, session: aiohttp.ClientSession, db_path: str = None) -> dict:
    result = {"ip": ip, "port": port, "status": "failed", "type": "unknown", "country": "unknown"}
    proxy_url = f"http://{ip}:{port}"
    try:
        # تست API
        url = API_URL.format(ip=ip, key=API_KEY, port=port)
        async with session.get(url, timeout=10) as resp:
            api_data = await resp.json()
            if api_data.get("status") == "ok" and ip in api_data:
                proxy_data = api_data[ip]
                result["type"] = proxy_data.get("detections", {}).get("type", "unknown")
                result["country"] = proxy_data.get("location", {}).get("country_name", "unknown")
                if proxy_data.get("detections", {}).get("proxy", False):
                    # تست واقعی connectivity
                    async with session.get("http://google.com", proxy=proxy_url, timeout=5) as conn_resp:
                        if conn_resp.status == 200:
                            result["status"] = "active"
    except Exception as e:
        logger.error(f"خطا در تست {ip}:{port}: {e}")
    if db_path and result["status"] == "active":
        update_proxy_status(db_path, ip, port, "active")
    return result

async def test_proxies(proxies: List[Tuple[str, str]], db_path: str = None, concurrent_limit: int = 5) -> List[dict]:
    results = []
    semaphore = asyncio.Semaphore(concurrent_limit)
    async def limited_test(proxy):
        async with semaphore:
            return await test_proxy(proxy[0], proxy[1], session, db_path)
    async with aiohttp.ClientSession() as session:
        tasks = [limited_test(p) for p in proxies]
        results = await asyncio.gather(*tasks)
    return results

def load_proxies_from_file(file_path: str = "cache/proxies.txt") -> List[Tuple[str, str]]:
    proxies = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                if ":" in line:
                    ip, port = line.strip().split(":", 1)
                    proxies.append((ip, port))
    return proxies

async def test_all_proxies(db_path: str, use_file: bool = False):
    if not API_KEY:
        logger.error("API_KEY تنظیم نشده!")
        return []
    proxies = load_proxies_from_file() if use_file else get_proxies(db_path)
    if not proxies:
        return []
    results = await test_proxies(proxies, db_path)
    valid_proxies = [r for r in results if r["status"] == "active"]
    with open("cache/valid_proxies.txt", "w") as f:
        for p in valid_proxies:
            f.write(f"{p['ip']}:{p['port']} # {p['type']}, {p['country']}\n")
    return results

async def main():
    config = load_config()
    db_path = config["database"]["DB_FILE"]
    await test_all_proxies(db_path, use_file=True)

if __name__ == "__main__":
    asyncio.run(main())