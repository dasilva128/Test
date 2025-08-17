# scrapers.py
import aiohttp
import asyncio
import logging
import re
import random
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import PROXIES
from utils import random_delay, extract_download_links

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_page(session, url, proxy=None):
    """Fetch page with retry."""
    headers = {
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            # Add more user-agents
        ])
    }
    async with session.get(url, proxy=proxy, headers=headers, timeout=10) as response:
        if response.status == 200:
            return await response.text()
        else:
            raise Exception(f"Status code {response.status}")

async def get_proxy():
    """Get a random working proxy."""
    if not PROXIES:
        return None
    proxy = random.choice(PROXIES)
    # Test proxy (simplified)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.google.com', proxy=proxy, timeout=5):
                return proxy
    except:
        return await get_proxy()  # Recurse to try another

async def search_telegram_channel(url, movie_name):
    """Search for movie posts in a Telegram channel."""
    pattern = rf'\b{re.escape(movie_name.lower())}\b'
    proxy = await get_proxy()
    
    async with aiohttp.ClientSession() as session:
        try:
            html = await fetch_page(session, url, proxy)
            soup = BeautifulSoup(html, 'html.parser')
            messages = soup.find_all('div', class_='tgme_widget_message')
            posts = []
            
            for message in messages:
                text = message.get_text(separator=' ', strip=True).lower()
                if re.search(pattern, text) and (
                    message.find('video') or 
                    any(kw in text for kw in ['دانلود', 'لینک فیلم', '480p', '720p', '1080p'])
                ):
                    link_tag = message.find('a', class_='tgme_widget_message_date')
                    if link_tag and 'href' in link_tag.attrs:
                        post_link = link_tag['href']
                        download_urls = extract_download_links(text)
                        posts.append((post_link, text[:200], download_urls))
            
            logging.info(f"Search in {url} for {movie_name}: {len(posts)} posts found")
            return posts
        except Exception as e:
            logging.error(f"Error searching {url}: {e}")
            return []

# Site-specific selectors (example; customize per site)
SITE_SELECTORS = {
    'zarfilm.com': {
        'search_path': '/?s=',
        'post_class': 'post-title',
        'link_attr': 'href',
        'text_tag': 'p',
        'download_class': 'download-link'
    },
    'film2mediax.ir': {
        'search_path': '/search/',
        'post_class': 'entry-title',
        'link_attr': 'href',
        'text_tag': 'div.entry-summary',
        'download_class': 'dl-link'
    },
    # Add more sites with their selectors...
    # For example:
    'hexdl.com': {
        'search_path': '/?s=',
        'post_class': 'item-title',
        'link_attr': 'href',
        'text_tag': 'div.excerpt',
        'download_class': 'download-button'
    },
    # ... and so on for other sites
}

async def search_website(base_url, movie_name):
    """Search for movie on a website."""
    if base_url not in SITE_SELECTORS:
        logging.warning(f"No selectors for {base_url}")
        return []
    
    selectors = SITE_SELECTORS[base_url]
    search_url = base_url.rstrip('/') + selectors['search_path'] + re.sub(r'\s+', '+', movie_name)
    proxy = await get_proxy()
    
    async with aiohttp.ClientSession() as session:
        try:
            html = await fetch_page(session, search_url, proxy)
            soup = BeautifulSoup(html, 'html.parser')
            posts = soup.find_all(class_=selectors['post_class'])
            results = []
            
            for post in posts:
                title = post.get_text(strip=True).lower()
                if movie_name.lower() in title:
                    link = post.find('a')[selectors['link_attr']] if post.find('a') else None
                    if link:
                        # Optionally fetch post page for download links
                        post_html = await fetch_page(session, link, proxy)
                        post_soup = BeautifulSoup(post_html, 'html.parser')
                        text = post_soup.find(selectors['text_tag']).get_text(strip=True) if post_soup.find(selectors['text_tag']) else ''
                        download_urls = [a['href'] for a in post_soup.find_all('a', class_=selectors['download_class'])]
                        results.append((link, text[:200], download_urls))
            
            logging.info(f"Search in {base_url} for {movie_name}: {len(results)} results found")
            return results
        except Exception as e:
            logging.error(f"Error searching {base_url}: {e}")
            return []