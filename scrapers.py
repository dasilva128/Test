# scrapers.py
import aiohttp
import asyncio
import logging
import re
import random
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from config import HTML_OUTPUT_DIR
from utils import random_delay, extract_download_links

# List of common search paths
COMMON_SEARCH_PATHS = ['/?s=', '/search/', '/q=', '/search?q=']

# Common post selectors
POST_SELECTORS = [
    'article', 'div.post', 'div.entry', 'div.item', 'div.content',
    'div.post-title', 'div.entry-title', 'div.item-title',
    'img.wp-post-image', 'div.attachment-post_cover',  # From zarfilm.com
    'li.cat-item', 'div.cat-item'  # From cooldl.net
]

async def load_html_file(url):
    """Load HTML file from html_output directory."""
    filename = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_") + ".txt"
    filepath = os.path.join(HTML_OUTPUT_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.warning(f"HTML file for {url} not found in {HTML_OUTPUT_DIR}")
        return None
    except Exception as e:
        logging.error(f"Error reading HTML file for {url}: {e}")
        return None

async def is_dynamic_site(html_content):
    """Check if the site is dynamic (JavaScript-dependent)."""
    if not html_content:
        return False
    soup = BeautifulSoup(html_content, 'html.parser')
    # Check for SPA or redirect pages
    if soup.find('div', id='app') or \
       any(script.get('src', '').endswith('.js') for script in soup.find_all('script')) or \
       (soup.find('title') and 'redirecting' in soup.find('title').get_text().lower()):
        return True
    return False

async def guess_search_path(html_content):
    """Guess search path from HTML metadata or use common paths."""
    if not html_content:
        return COMMON_SEARCH_PATHS[0]  # Default to first common path
    soup = BeautifulSoup(html_content, 'html.parser')
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    title = soup.find('title')
    
    # Check for keywords in meta or title
    keywords = ['جستجو', 'search', 'فیلم', 'سریال']
    if (meta_desc and any(kw in meta_desc.get('content', '').lower() for kw in keywords)) or \
       (title and any(kw in title.get_text().lower() for kw in keywords)):
        return '/search/'  # Prefer /search/ if keywords found
    # Check for WordPress indicators (from zarfilm.com, cooldl.net)
    if '/wp-content/' in html_content or '/wp-' in html_content or 'cat-item' in html_content:
        return '/?s='  # Common for WordPress sites
    return random.choice(COMMON_SEARCH_PATHS)  # Otherwise, choose randomly

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_page(session, url):
    """Fetch page with retry."""
    headers = {
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        ]),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    async with session.get(url, headers=headers, timeout=10) as response:
        if response.status == 200:
            try:
                return await response.text(encoding='utf-8')
            except UnicodeDecodeError:
                logging.warning(f"UTF-8 failed for {url}, trying latin1")
                return await response.text(encoding='latin1')
        else:
            raise Exception(f"Status code {response.status}")

async def search_telegram_channel(url, movie_name):
    """Search for movie posts in a Telegram channel."""
    pattern = rf'\b{re.escape(movie_name.lower())}\b'
    
    async with aiohttp.ClientSession() as session:
        try:
            html = await fetch_page(session, url)
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

async def search_website(base_url, movie_name):
    """Search for movie on a website."""
    html_content = await load_html_file(base_url)
    search_path = await guess_search_path(html_content)
    search_url = base_url.rstrip('/') + search_path + re.sub(r'\s+', '+', movie_name)
    
    # Check if the site is dynamic
    is_dynamic = await is_dynamic_site(html_content)
    
    if is_dynamic:
        logging.info(f"Dynamic site detected for {base_url}, using Playwright")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(search_url, timeout=30000, wait_until='networkidle')
                await page.wait_for_load_state('networkidle', timeout=30000)
                html = await page.content()
                await browser.close()
            except Exception as e:
                logging.error(f"Playwright error for {search_url}: {e}")
                await browser.close()
                return []
    else:
        async with aiohttp.ClientSession() as session:
            try:
                html = await fetch_page(session, search_url)
            except Exception as e:
                logging.error(f"Error fetching {search_url}: {e}")
                return []

    # Parse the HTML
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    for selector in POST_SELECTORS:
        posts = soup.select(selector)
        for post in posts:
            # Check title or alt attributes for movie name
            title = post.get_text(strip=True).lower()
            img_alt = post.find('img', alt=True)
            alt_text = img_alt['alt'].lower() if img_alt else ''
            link_text = post.find('a', href=True)
            link_text_content = link_text.get_text(strip=True).lower() if link_text else ''
            if movie_name.lower() in title or movie_name.lower() in alt_text or movie_name.lower() in link_text_content:
                link = post.find('a', href=True)
                if link and 'href' in link.attrs:
                    post_link = link['href']
                    # Ensure post_link is absolute
                    if not post_link.startswith(('http://', 'https://')):
                        post_link = base_url.rstrip('/') + '/' + post_link.lstrip('/')
                    # Fetch post page for details
                    if is_dynamic:
                        async with async_playwright() as p:
                            browser = await p.chromium.launch(headless=True)
                            page = await browser.new_page()
                            try:
                                await page.goto(post_link, timeout=30000, wait_until='networkidle')
                                await page.wait_for_load_state('networkidle', timeout=30000)
                                post_html = await page.content()
                                await browser.close()
                            except Exception as e:
                                logging.error(f"Playwright error for {post_link}: {e}")
                                await browser.close()
                                continue
                            post_soup = BeautifulSoup(post_html, 'html.parser')
                    else:
                        async with aiohttp.ClientSession() as session:
                            try:
                                post_html = await fetch_page(session, post_link)
                                post_soup = BeautifulSoup(post_html, 'html.parser')
                            except Exception as e:
                                logging.error(f"Error fetching {post_link}: {e}")
                                continue
                    
                    text = post_soup.get_text(strip=True)[:200]
                    # Look for download links with specific classes or patterns
                    download_urls = [a['href'] for a in post_soup.find_all('a', href=True) 
                                    if any(kw in a['href'].lower() for kw in ['.mkv', '.mp4', 'download', 'dl', 'btndlapp'])]
                    results.append((post_link, text, download_urls))
        if results:  # Stop if we found results with this selector
            break
    
    logging.info(f"Search in {base_url} for {movie_name}: {len(results)} results found")
    return results