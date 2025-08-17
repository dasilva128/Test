# db.py
import sqlite3

def init_db():
    """Initialize the SQLite database and create results table with UNIQUE constraint."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS results
                     (movie_name TEXT, source TEXT, post_link TEXT, post_text TEXT,
                      UNIQUE(movie_name, source, post_link))''')
    conn.commit()
    conn.close()

def save_result(movie_name, source, post_link, post_text):
    """Save search results to database, ignoring duplicates."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO results VALUES (?, ?, ?, ?)', 
                      (movie_name, source, post_link, post_text))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Duplicate, ignore
    conn.close()

def get_cached_results(movie_name):
    """Retrieve cached results from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT source, post_link, post_text FROM results WHERE movie_name = ?', 
                  (movie_name,))
    results = cursor.fetchall()
    conn.close()
    return results