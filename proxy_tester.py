import aiohttp
import asyncio
import logging
import os
from typing import List, Tuple
from src.db import get_proxies, get_db_connection
from src.utils import load_config
from dotenv import load_dotenv

# تنظیم لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/proxy_tester.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# لود API Key از .env
load_dotenv()
API_KEY = "86941p-0093a6-4r1c63-50516d"
API_URL = "https://proxycheck.io/v3/{ip}?key={key}&vpn=1&asn=1&port={port}&seen=1"

async def test_proxy(ip: str, port: str, session: aiohttp.ClientSession) -> dict:
    """تست یک پروکسی با استفاده از API proxycheck.io v3"""
    try:
        url = API_URL.format(ip=ip, key=API_KEY, port=port)
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            result = await response.json()
            logger.debug(f"نتیجه تست برای {ip}:{port}: {result}")
            
            # بررسی نتیجه API
            if result.get("status") == "ok" and ip in result:
                proxy_data = result[ip]
                is_proxy = proxy_data.get("detections", {}).get("proxy", False)
                status = "active" if is_proxy else "inactive"
                return {
                    "ip": ip,
                    "port": port,
                    "status": status,
                    "type": proxy_data.get("detections", {}).get("type", "unknown"),
                    "country": proxy_data.get("location", {}).get("country_name", "unknown"),
                    "last_seen": proxy_data.get("last seen human", "unknown")
                }
            else:
                logger.warning(f"پاسخ نامعتبر از API برای {ip}:{port}: {result.get('status', 'unknown')}")
                return {"ip": ip, "port": port, "status": "failed", "type": "unknown", "country": "unknown", "last_seen": "unknown"}
    except Exception as e:
        logger.error(f"خطا در تست پروکسی {ip}:{port}: {e}")
        return {"ip": ip, "port": port, "status": "failed", "type": "unknown", "country": "unknown", "last_seen": "unknown"}

async def test_proxies(proxies: List[Tuple[str, str]], concurrent_limit: int = 5) -> List[dict]:
    """تست گروهی پروکسی‌ها با محدودیت تعداد درخواست‌های همزمان"""
    results = []
    semaphore = asyncio.Semaphore(concurrent_limit)

    async def limited_test(proxy: Tuple[str, str], session: aiohttp.ClientSession):
        async with semaphore:
            return await test_proxy(proxy[0], proxy[1], session)

    async with aiohttp.ClientSession() as session:
        tasks = [limited_test(proxy, session) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if not isinstance(result, Exception)]

def load_proxies_from_file(file_path: str = "cache/proxies.txt") -> List[Tuple[str, str]]:
    """خواندن پروکسی‌ها از فایل proxies.txt"""
    proxies = []
    try:
        if not os.path.exists(file_path):
            logger.warning(f"فایل {file_path} یافت نشد")
            return proxies
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    ip, port = line.split(":", 1)
                    proxies.append((ip.strip(), port.strip()))
        logger.info(f"{len(proxies)} پروکسی از فایل {file_path} خوانده شد")
        return proxies
    except Exception as e:
        logger.error(f"خطا در خواندن فایل پروکسی‌ها: {e}")
        return []

async def test_all_proxies(db_path: str, use_file: bool = False):
    """تست همه پروکسی‌ها از دیتابیس یا فایل"""
    try:
        if not API_KEY:
            logger.error("PROXYCHECK_API_KEY در فایل .env تنظیم نشده است!")
            return []

        if use_file:
            proxies = load_proxies_from_file()
        else:
            with get_db_connection(db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxies'")
                if not c.fetchone():
                    logger.error("جدول proxies در دیتابیس وجود ندارد!")
                    return []
                c.execute("SELECT ip, port FROM proxies")
                proxies = [(row[0], row[1]) for row in c.fetchall()]
                logger.info(f"{len(proxies)} پروکسی از دیتابیس خوانده شد")

        if not proxies:
            logger.warning("هیچ پروکسی‌ای برای تست یافت نشد")
            return []

        logger.info(f"شروع تست {len(proxies)} پروکسی...")
        results = await test_proxies(proxies)

        # ذخیره پروکسی‌های معتبر در فایل
        valid_proxies = [result for result in results if result["status"] == "active"]
        os.makedirs("cache", exist_ok=True)
        with open("cache/valid_proxies.txt", "w", encoding="utf-8") as f:
            for proxy in valid_proxies:
                f.write(f"{proxy['ip']}:{proxy['port']} # {proxy['type']}, {proxy['country']}, Last seen: {proxy['last_seen']}\n")
        logger.info(f"{len(valid_proxies)} پروکسی معتبر در cache/valid_proxies.txt ذخیره شد")

        return results
    except Exception as e:
        logger.error(f"خطا در تست پروکسی‌ها: {e}")
        return []

async def main():
    """نقطه ورود اصلی برای تست پروکسی‌ها"""
    try:
        config = load_config()
        db_path = config["database"]["path"]
        results = await test_all_proxies(db_path, use_file=True)  # use_file=True برای خواندن از proxies.txt
        logger.info(f"تست کامل شد. تعداد کل پروکسی‌های تست‌شده: {len(results)}")
    except Exception as e:
        logger.error(f"خطا در اجرای اصلی: {e}")

if __name__ == "__main__":
    asyncio.run(main())