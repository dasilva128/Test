import aiohttp
import asyncio
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from src.utils import is_valid_v2ray_link, load_channels, load_config, parse_v2ray_protocol
from src.db import save_configs_bulk, get_db_connection
import sqlite3

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/link_collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
async def check_channel_access(url, proxy=None):
    """تست دسترسی به وب‌سایت"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy, timeout=10) as response:
                response.raise_for_status()
                logger.info(f"وب‌سایت {url} در دسترس است.")
                return True
    except Exception as e:
        logger.error(f"وب‌سایت {url} در دسترس نیست: {e}")
        return False

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_url(url, proxy=None):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy, timeout=15) as response:
                response.raise_for_status()
                logger.info(f"در حال ارسال درخواست به {url} با پروکسی {proxy}")
                return await response.text()
    except Exception as e:
        logger.error(f"خطا در درخواست به {url}: {e}")
        raise

async def process_channel(url, proxy, db_path):
    try:
        response = await fetch_url(url, proxy)
        soup = BeautifulSoup(response, "html.parser")
        code_tags = soup.find_all("code")

        if not code_tags:
            logger.warning(f"هیچ تگ <code> در {url} پیدا نشد")
            return []

        configs = []
        max_configs_per_channel = 20  # سقف تعداد کانفیگ‌ها از هر وب‌سایت
        for tag in code_tags:
            if len(configs) >= max_configs_per_channel:
                logger.info(f"به سقف {max_configs_per_channel} کانفیگ برای وب‌سایت {url} رسیدیم. پردازش متوقف شد.")
                break
            text = tag.get_text().strip()
            logger.debug(f"لینک خام یافت شده: {text[:50]}...")
            if is_valid_v2ray_link(text):
                protocol = parse_v2ray_protocol(text) or "Unknown"
                configs.append((text, protocol))
                logger.info(f"لینک معتبر یافت شد: {text[:50]}... - پروتکل: {protocol}")
            else:
                logger.debug(f"لینک نامعتبر: {text[:50]}...")
        return configs
    except Exception as e:
        logger.error(f"خطا در جمع‌آوری لینک‌ها از {url}: {e}")
        return []

async def collect_v2ray_links(db_path):
    config = load_config()
    proxy = config["telegram"].get("proxy")
    channels = load_channels()
    configs = []

    logger.info(f"شروع جمع‌آوری لینک‌ها از {len(channels)} وب‌سایت")
    logger.info(f"مسیر دیتابیس: {db_path}")

    try:
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='configs'")
            if not c.fetchone():
                logger.error("جدول configs در دیتابیس وجود ندارد!")
                return configs
        logger.info(f"اتصال به دیتابیس {db_path} موفقیت‌آمیز بود")
    except sqlite3.Error as e:
        logger.error(f"خطا در اتصال به دیتابیس {db_path}: {e}")
        return configs

    # تست دسترسی به وب‌سایت‌ها
    accessible_channels = []
    for url in channels:
        if await check_channel_access(url, proxy):
            accessible_channels.append(url)
        else:
            logger.warning(f"وب‌سایت {url} از لیست جمع‌آوری حذف شد.")

    # ایجاد صف برای پردازش تدریجی
    queue = asyncio.Queue()
    for url in accessible_channels:
        await queue.put(url)

    async def worker():
        while True:
            try:
                url = await queue.get()
                try:
                    channel_configs = await process_channel(url, proxy, db_path)
                    configs.extend(channel_configs)
                finally:
                    queue.task_done()
            except asyncio.QueueEmpty:
                break

    # اجرای 5 کارگر همزمان برای پردازش صف
    workers = [asyncio.create_task(worker()) for _ in range(5)]
    await queue.join()  # منتظر خالی شدن صف
    for worker in workers:
        worker.cancel()  # لغو کارگرها پس از اتمام
    await asyncio.gather(*workers, return_exceptions=True)

    # ذخیره گروهی کانفیگ‌ها
    if configs:
        save_configs_bulk(db_path, configs)
        logger.info(f"{len(configs)} کانفیگ برای ذخیره ارسال شد")
    else:
        logger.info("هیچ کانفیگ جدیدی یافت نشد")

    logger.info(f"جمع‌آوری کامل شد. تعداد کل کانفیگ‌های معتبر: {len(configs)}")
    return configs