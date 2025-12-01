import psycopg2
import hashlib
import os
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
    
    # 2. Users Table (New)
    # Stores Telegram ID and Hashed Password
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            password_hash TEXT
        );
    ''')
    
    conn.commit()
    conn.close()

# --- AUTHENTICATION ---

def hash_password(password):
    # Simple SHA256 hash (For a prototype, this is sufficient. 
    # For production, use bcrypt/argon2)
    return hashlib.sha256(password.encode()).hexdigest()

def set_password(user_id, plain_password):
    conn = get_connection()
    c = conn.cursor()
    hashed = hash_password(plain_password)
    try:
        # Upsert: Insert or Update if exists
        c.execute("""
            INSERT INTO users (user_id, password_hash) 
            VALUES (%s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET password_hash = EXCLUDED.password_hash
        """, (user_id, hashed))
        conn.commit()
        return True
    except Exception as e:
        print(f"Auth Error: {e}")
        return False
    finally:
        conn.close()

def check_login(user_id, plain_password):
    conn = get_connection()
    c = conn.cursor()
    hashed = hash_password(plain_password)
    try:
        c.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
        result = c.fetchone()
        if result and result[0] == hashed:
            return True
        return False
    except Exception as e:
        print(f"Login Error: {e}")
        return False
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