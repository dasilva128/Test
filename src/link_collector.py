# src/link_collector.py
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from src.utils import is_valid_v2ray_link, load_channels, parse_v2ray_protocol
from src.db import save_configs_bulk, get_db_connection

logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
async def check_channel_access(url, session):
    try:
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"دسترسی به {url} ناموفق: {e}")
        return False

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_url(url, session):
    async with session.get(url, timeout=15) as response:
        response.raise_for_status()
        return await response.text()

async def process_channel(url, session, db_path):
    try:
        response = await fetch_url(url, session)
        soup = BeautifulSoup(response, "html.parser")
        code_tags = soup.find_all("code")
        configs = []
        max_per_channel = 20
        for tag in code_tags:
            if len(configs) >= max_per_channel:
                break
            text = tag.get_text().strip()
            if is_valid_v2ray_link(text):
                protocol = parse_v2ray_protocol(text) or "unknown"
                configs.append((text, protocol))
        return configs
    except Exception as e:
        logger.error(f"خطا در {url}: {e}")
        return []

async def collect_v2ray_links(db_path):
    channels = load_channels()
    configs = []
    async with aiohttp.ClientSession() as session:
        accessible = [url for url in channels if await check_channel_access(url, session)]
        semaphore = asyncio.Semaphore(5)
        async def limited_process(url):
            async with semaphore:
                return await process_channel(url, session, db_path)
        tasks = [limited_process(url) for url in accessible]
        results = await asyncio.gather(*tasks)
        for res in results:
            configs.extend(res)
    if configs:
        save_configs_bulk(db_path, configs)
    logger.info(f"{len(configs)} کانفیگ جمع‌آوری شد.")
    return configs