# src/db.py
import sqlite3
import time
import logging
from .utils import load_config

logger = logging.getLogger(__name__)
config = load_config()
DB_FILE = config["database"]["DB_FILE"]

def init_db(db_path: str = DB_FILE):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS configs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      protocol TEXT NOT NULL,
                      config TEXT NOT NULL,
                      timestamp INTEGER NOT NULL,
                      UNIQUE(protocol, config))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS proxies
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      ip TEXT NOT NULL,
                      port TEXT NOT NULL,
                      status TEXT DEFAULT 'unknown',
                      timestamp INTEGER NOT NULL,
                      UNIQUE(ip, port))''')
    conn.commit()
    conn.close()
    logger.info(f"دیتابیس در {db_path} اولیه‌سازی شد.")

def get_db_connection(db_path: str = DB_FILE):
    return sqlite3.connect(db_path)

def get_configs_by_protocol(db_path: str, protocol: str, max_configs: int):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT config FROM configs WHERE protocol = ? ORDER BY timestamp DESC LIMIT ?', (protocol, max_configs))
    configs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return configs

def cleanup_old_configs(db_path: str, expire_hours: int):
    expire_seconds = expire_hours * 3600
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM configs WHERE timestamp <= ?', (int(time.time()) - expire_seconds,))
    conn.commit()
    conn.close()
    logger.info("کانفیگ‌های قدیمی پاک شدند.")

def clear_all_configs(db_path: str):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM configs')
    cursor.execute('DELETE FROM proxies')
    conn.commit()
    conn.close()
    logger.info("همه داده‌ها پاک شدند.")

def save_configs_bulk(db_path: str, configs: list):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.executemany('INSERT OR IGNORE INTO configs (config, protocol, timestamp) VALUES (?, ?, ?)',
                          [(config, protocol, int(time.time())) for config, protocol in configs])
        conn.commit()
        logger.info(f"{cursor.rowcount} کانفیگ ذخیره شد.")
    except sqlite3.Error as e:
        logger.error(f"خطا: {e}")
    finally:
        conn.close()

def save_proxies_bulk(db_path: str, proxies: list):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.executemany('INSERT OR IGNORE INTO proxies (ip, port, timestamp) VALUES (?, ?, ?)',
                          [(ip, port, int(time.time())) for ip, port in proxies])
        conn.commit()
        logger.info(f"{cursor.rowcount} پروکسی ذخیره شد.")
    except sqlite3.Error as e:
        logger.error(f"خطا: {e}")
    finally:
        conn.close()

def get_proxies(db_path: str):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT ip, port FROM proxies')
    proxies = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return proxies

def update_proxy_status(db_path: str, ip: str, port: str, status: str):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE proxies SET status = ?, timestamp = ? WHERE ip = ? AND port = ?', (status, int(time.time()), ip, port))
    conn.commit()
    conn.close()