import sqlite3

def init_db():
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    # Create tables and ensure columns exist
    try: c.execute("ALTER TABLE links ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE links ADD COLUMN lat REAL")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE links ADD COLUMN lon REAL")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE links ADD COLUMN ai_summary TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE links ADD COLUMN category TEXT")
    except sqlite3.OperationalError: pass
            
    c.execute('''CREATE TABLE IF NOT EXISTS links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  url TEXT, 
                  title TEXT, 
                  image_url TEXT,
                  category TEXT DEFAULT 'Inbox',
                  ai_summary TEXT,
                  user_id INTEGER,
                  lat REAL,
                  lon REAL)''')
    conn.commit()
    conn.close()

def is_duplicate(url, user_id):
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute("SELECT id FROM links WHERE url=? AND user_id=?", (url, user_id))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_link(data_dict):
    """
    Saves a fully processed link data dictionary to DB.
    """
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO links (url, title, image_url, ai_summary, category, user_id, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
        (data_dict['url'], data_dict['title'], data_dict['image'], data_dict['ai_summary'], 
         data_dict['category'], data_dict['user_id'], data_dict['lat'], data_dict['lon'])
    )
    conn.commit()
    conn.close()

def search_nexus_memory(user_id, query):
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    sql_query = """
        SELECT title, ai_summary, category, url, lat, lon
        FROM links 
        WHERE user_id=? AND (
            title LIKE ? OR 
            ai_summary LIKE ? OR 
            category LIKE ?
        ) ORDER BY id DESC LIMIT 10
    """
    wildcard_query = f"%{query}%"
    c.execute(sql_query, (user_id, wildcard_query, wildcard_query, wildcard_query))
    results = c.fetchall()
    conn.close()
    return results