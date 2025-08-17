# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
DESTINATION_CHAT = os.getenv('DESTINATION_CHAT')

PROXIES = [
    'http://185.226.92.131:32737',
    # Add more proxies here
]

CHANNELS_FILE = 'channels.txt'
SITES_FILE = 'sites.txt'
DB_FILE = 'search_results.db'
LOG_FILE = 'bot.log'