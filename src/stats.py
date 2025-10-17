# src/stats.py
import sqlite3
import logging
from .db import get_db_connection

logger = logging.getLogger(__name__)

def get_stats(db_path: str) -> str:
    try:
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM configs")
            total_configs = c.fetchone()[0]
            c.execute("SELECT protocol, COUNT(*) FROM configs GROUP BY protocol")
            protocols = c.fetchall()
            c.execute("SELECT COUNT(*) FROM proxies")
            total_proxies = c.fetchone()[0]
            message = f"کل کانفیگ‌ها: {total_configs}\n"
            for p, count in protocols:
                message += f"{p}: {count}\n"
            message += f"پروکسی‌ها: {total_proxies}"
            return message
    except Exception as e:
        logger.error(f"خطا در stats: {e}")
        return "خطایی رخ داد! 😓"