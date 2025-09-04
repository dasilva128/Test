import sqlite3
import time
from config import DB_FILE

def init_db():
    """Initialize the SQLite database and create results table with timestamp."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS results
                     (movie_name TEXT, source TEXT, post_link TEXT, post_text TEXT, timestamp INTEGER,
                      UNIQUE(movie_name, source, post_link))''')
    conn.commit()
    conn.close()

def save_result(movie_name, source, post_link, post_text):
    """Save search results to database with timestamp, ignoring duplicates."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO results VALUES (?, ?, ?, ?, ?)', 
                      (movie_name, source, post_link, post_text, int(time.time())))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Duplicate, ignore
    conn.close()

def get_cached_results(movie_name, expire_seconds=604800):  # 7 days
    """Retrieve cached results from database, only if not expired."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT source, post_link, post_text FROM results WHERE movie_name = ? AND timestamp > ?',
                  (movie_name, int(time.time()) - expire_seconds))
    results = cursor.fetchall()
    conn.close()
    return results

def clean_expired_results(expire_seconds=604800):
    """Remove expired results from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM results WHERE timestamp <= ?', (int(time.time()) - expire_seconds,))
    conn.commit()
    conn.close()