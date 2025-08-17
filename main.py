import asyncio
from telethon import TelegramClient, events

from config import API_ID, API_HASH, BOT_TOKEN, DESTINATION_CHAT, CHANNELS_FILE, SITES_FILE
from db import init_db, save_result, get_cached_results, clean_expired_results
from utils import load_list, random_delay
from scrapers import search_telegram_channel, search_website

client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Handle /start command."""
    await event.reply("سلام! نام فیلم را ارسال کنید تا در کانال‌های عمومی تلگرام و سایت‌های دانلود جستجو کنم و لینک پست‌های مرتبط را بفرستم.")
    raise events.StopPropagation

@client.on(events.NewMessage)
async def search_movie(event):
    """Handle movie search requests."""
    if event.message.text.startswith('/start'):
        return

    movie_name = event.message.text.strip()
    if not movie_name:
        await event.reply("لطفاً نام فیلم را وارد کنید!")
        return

    await event.reply(f"در حال جستجو برای '{movie_name}'...")
    logging.info(f"New search for: {movie_name}")

    # Check cache
    cached_results = get_cached_results(movie_name)
    if cached_results:
        for source, post_link, post_text in cached_results:
            message = f"پست از کش ({source}):\nلینک: {post_link}\nمتن: {post_text}..."
            await event.reply(message)
        logging.info(f"Cached results for {movie_name} sent")
        return

    # Load sources
    telegram_urls = load_list(CHANNELS_FILE)
    sites = load_list(SITES_FILE)
    if not telegram_urls and not sites:
        await event.reply("هیچ منبع‌ای (کانال یا سایت) تعریف نشده است!")
        return

    # Search concurrently with semaphore
    found = False
    tasks = []
    for url in telegram_urls:
        tasks.append(search_with_semaphore(search_telegram_channel, url, movie_name))
    for site in sites:
        tasks.append(search_with_semaphore(search_website, site, movie_name))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            logging.error(f"Error in search: {res}")
            continue
        if res:
            source = telegram_urls[idx] if idx < len(telegram_urls) else sites[idx - len(telegram_urls)]
            for post_link, post_text, download_urls in res:
                message = f"پست پیدا شد در {source}:\nلینک: {post_link}\nمتن: {post_text}..."
                if download_urls:
                    message += f"\nلینک‌های دانلود: {', '.join(download_urls)}"
                await event.reply(message)
                await client.send_message(DESTINATION_CHAT, message)
                save_result(movie_name, source, post_link, post_text)
                found = True
            random_delay()

    if not found:
        await event.reply(f"هیچ پستی با نام '{movie_name}' پیدا نشد.")
        logging.info(f"No results for {movie_name}")

async def search_with_semaphore(search_func, url, movie_name):
    """Wrap search function with semaphore."""
    async with semaphore:
        return await search_func(url, movie_name)

if __name__ == '__main__':
    init_db()
    clean_expired_results()  # Clean expired results on startup
    print("ربات شروع به کار کرد...")
    client.run_until_disconnected()