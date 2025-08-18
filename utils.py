# utils.py
import random
import time
import re
import logging
from telethon import events
from config import LOG_FILE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def load_list(file_path):
    """Load list from file, skipping comments and empty lines."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            items = [line.strip() for line in file if line.strip() and not line.startswith('#')]
        return items
    except FileNotFoundError:
        logging.error(f"File {file_path} not found!")
        return []
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return []

def extract_download_links(text):
    """Extract potential download links using regex."""
    urls = re.findall(r'https?://[^\s<>"\']+', text)
    download_urls = [url for url in urls if any(ext in url.lower() for ext in ['.mkv', '.mp4', '.zip', 'download', 'dl', 'btndlapp'])]
    return download_urls if download_urls else None

def random_delay(min_sec=1, max_sec=5):
    """Sleep for a random time to avoid rate limiting."""
    time.sleep(random.uniform(min_sec, max_sec))