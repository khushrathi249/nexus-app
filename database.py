import psycopg2
import hashlib
from settings import DATABASE_URL

def get_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is missing.")
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Links Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id SERIAL PRIMARY KEY,
            url TEXT,
            title TEXT,
            image_url TEXT,
            category TEXT DEFAULT 'Inbox',
            ai_summary TEXT,
            user_id BIGINT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION
        );
    ''')
    
    # 2. Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            password_hash TEXT
        );
    ''')
    
    # 3. Migration: Add username column if it doesn't exist
    try:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT UNIQUE")
    except psycopg2.errors.DuplicateColumn:
        conn.rollback() # Column exists, ignore
    except Exception as e:
        print(f"Migration Note: {e}")
        conn.rollback()
    
    conn.commit()
    conn.close()

# --- AUTHENTICATION ---

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(user_id, username, plain_password):
    """
    Sets username and password for a Telegram ID.
    Returns: (Success: bool, Message: str)
    """
    conn = get_connection()
    c = conn.cursor()
    hashed = hash_password(plain_password)
    
    try:
        # Check if username is taken by SOMEONE ELSE
        c.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        existing = c.fetchone()
        if existing and existing[0] != user_id:
            return False, "Username already taken."

        # Upsert (Insert or Update)
        c.execute("""
            INSERT INTO users (user_id, username, password_hash) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET username = EXCLUDED.username, password_hash = EXCLUDED.password_hash
        """, (user_id, username, hashed))
        conn.commit()
        return True, "Account updated successfully."
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        conn.close()

def login_user(username, plain_password):
    """
    Checks credentials and returns the Telegram USER_ID if valid.
    This allows the viewer to load the correct data.
    """
    conn = get_connection()
    c = conn.cursor()
    hashed = hash_password(plain_password)
    try:
        c.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
        result = c.fetchone()
        
        if result:
            db_id, db_hash = result
            if db_hash == hashed:
                return db_id # Login Success: Return the internal ID
        return None # Login Failed
    except Exception as e:
        print(f"Login Error: {e}")
        return None
    finally:
        conn.close()

def update_password(user_id, new_password):
    conn = get_connection()
    c = conn.cursor()
    hashed = hash_password(new_password)
    try:
        c.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (hashed, user_id))
        if c.rowcount == 0:
            return False # User doesn't exist yet
        conn.commit()
        return True
    finally:
        conn.close()

# --- EXISTING LINK LOGIC ---

def save_link(data_dict):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO links 
            (url, title, image_url, ai_summary, category, user_id, lat, lon) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, 
            (data_dict['url'], data_dict['title'], data_dict['image'], data_dict['ai_summary'], 
             data_dict['category'], data_dict['user_id'], data_dict['lat'], data_dict['lon'])
        )
        conn.commit()
    except Exception as e:
        print(f"❌ Database Save Error: {e}")
    finally:
        conn.close()

def is_duplicate(url, user_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM links WHERE url=%s AND user_id=%s", (url, user_id))
        result = c.fetchone()
        return result is not None
    finally:
        conn.close()

def search_nexus_memory(user_id, query):
    conn = get_connection()
    c = conn.cursor()
    sql_query = """
        SELECT title, ai_summary, category, url, lat, lon
        FROM links 
        WHERE user_id=%s AND (
            title ILIKE %s OR 
            ai_summary ILIKE %s OR 
            category ILIKE %s
        ) ORDER BY id DESC LIMIT 10
    """
    wildcard_query = f"%{query}%"
    try:
        c.execute(sql_query, (user_id, wildcard_query, wildcard_query, wildcard_query))
        results = c.fetchall()
        return results
    finally:
        conn.close()