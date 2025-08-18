# db.py
import sqlite3
from datetime import datetime, timedelta

def init_db():
    """Initialize the SQLite database and create results table with UNIQUE constraint."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS results
                        (movie_name TEXT, source TEXT, post_link TEXT, post_text TEXT, timestamp TEXT,
                         UNIQUE(movie_name, source, post_link))''')
        conn.commit()

def save_result(movie_name, source, post_link, post_text):
    """Save search results to database with timestamp, ignoring duplicates."""
    timestamp = datetime.now().isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO results VALUES (?, ?, ?, ?, ?)', 
                          (movie_name, source, post_link, post_text, timestamp))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Duplicate, ignore

def get_cached_results(movie_name):
    """Retrieve cached results from database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT source, post_link, post_text FROM results WHERE movie_name = ?', 
                      (movie_name,))
        results = cursor.fetchall()
    return results

def clean_expired_results(days=7):
    """Remove results older than specified days."""
    threshold = (datetime.now() - timedelta(days=days)).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM results WHERE timestamp < ?', (threshold,))
        conn.commit()