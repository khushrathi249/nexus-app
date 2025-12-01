import streamlit as st
import psycopg2
from psycopg2 import pool
import hashlib
import time
import requests
from io import BytesIO
from settings import DATABASE_URL

# 1. Page Config
st.set_page_config(
    page_title="Nexus", 
    page_icon="🧠", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 2. IMAGE PROXY HELPER
@st.cache_data(ttl=3600, show_spinner=False)
def load_image_proxy(url):
    if not url: return None
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.instagram.com/'
        }
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            return BytesIO(response.content)
    except: pass
    return None

# --- DATABASE HELPERS (ROBUST POOLING) ---

@st.cache_resource
def get_db_pool():
    """
    Creates a Threaded Connection Pool.
    Cached resource: The POOL persists, but individual connections are borrowed/returned.
    """
    if not DATABASE_URL:
        st.error("CRITICAL: DATABASE_URL is missing.")
        return None
    try:
        # Create a pool with min 1, max 10 connections
        return psycopg2.pool.ThreadedConnectionPool(
            1, 10,
            dsn=DATABASE_URL,
            sslmode='require'
        )
    except Exception as e:
        st.error(f"Failed to connect to Database: {e}")
        return None

def run_query(query, params=None):
    """
    Safe query execution using the pool.
    Auto-commits for write operations. Returns data for SELECTs.
    """
    db_pool = get_db_pool()
    if not db_pool: return None
    
    conn = None
    try:
        # Borrow connection
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(query, params)
            
            if query.strip().upper().startswith("SELECT"):
                result = cur.fetchall()
                return result
            else:
                conn.commit()
                return True
    except Exception as e:
        # Don't show confusing DB errors to user, just log console
        print(f"DB Query Error: {e}") 
        return None
    finally:
        # CRITICAL: Always return connection to pool
        if db_pool and conn:
            db_pool.putconn(conn)

def check_login(user_id, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    res = run_query("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
    if res and res[0][0] == hashed:
        return True
    return False

# --- SESSION STATE ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

# --- VIEWS ---

def show_login():
    st.title("🧠 Nexus")
    st.write("Your Second Brain")
    
    with st.form("login_form"):
        uid = st.text_input("User ID", placeholder="Enter your Telegram ID")
        pwd = st.text_input("Password", type="password", placeholder="Enter your secret key")
        
        submitted = st.form_submit_button("Login", use_container_width=True)
        
        if submitted:
            if check_login(uid, pwd):
                st.session_state.user_id = uid
                st.rerun()
            else:
                st.error("Invalid Credentials. Check your ID and Password.")

def show_dashboard():
    # --- HEADER ---
    c1, c2, c3 = st.columns([5, 1, 1])
    with c1:
        st.header("My Stacks")
    with c2:
        if st.button("🔄", help="Refresh Data"):
            st.rerun()
    with c3:
        if st.button("Logout"):
            st.session_state.user_id = None
            st.rerun()

    # --- FILTERS ---
    col_search, col_cat = st.columns([2, 1])
    with col_search:
        search_q = st.text_input("Search", placeholder="Search titles, notes...", label_visibility="collapsed")
    with col_cat:
        # Fetch categories dynamically
        cats_raw = run_query("SELECT DISTINCT category FROM links WHERE user_id = %s", (st.session_state.user_id,))
        cats = ["All"]
        if cats_raw:
            cats += sorted([c[0] for c in cats_raw if c[0] and c[0] not in ["All", "Inbox"]])
        selected_cat = st.selectbox("Category", cats, label_visibility="collapsed")

    st.divider()

    # --- DATA FETCH ---
    query = """
        SELECT id, title, image_url, url, category, ai_summary, lat, lon 
        FROM links WHERE user_id = %s
    """
    params = [st.session_state.user_id]

    if selected_cat != "All":
        query += " AND category = %s"
        params.append(selected_cat)
    
    query += " ORDER BY id DESC"
    
    rows = run_query(query, tuple(params))
    
    if not rows:
        st.info("No links found. Send a reel to your Telegram bot to get started.")
        return

    # --- CLIENT SIDE SEARCH ---
    filtered = []
    for r in rows:
        # 1=title, 5=summary
        title_match = search_q.lower() in r[1].lower() if r[1] else False
        summary_match = search_q.lower() in r[5].lower() if r[5] else False
        
        if not search_q or title_match or summary_match:
            filtered.append(r)

    # --- GRID LAYOUT ---
    cols = st.columns(2)
    
    for i, row in enumerate(filtered):
        link_id, title, img_url, url, category, ai_summary, lat, lon = row
        
        with cols[i % 2]:
            with st.container(border=True):
                # 1. Image Cover (Proxy Method)
                if img_url:
                    img_data = load_image_proxy(img_url)
                    if img_data:
                        st.image(img_data, use_container_width=True)
                    else:
                        st.warning("Image Expired")
                else:
                    st.markdown('<div style="height:150px; background-color:#f0f2f6; border-radius: 5px 5px 0 0; margin-bottom: 10px;"></div>', unsafe_allow_html=True)
                
                # 2. Metadata
                st.caption(f"📂 {category}")
                st.markdown(f"**[{title}]({url})**")

                # 3. Action Row
                c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
                
                with c_btn1:
                    st.link_button("🔗", url, help="Open Link", use_container_width=True)
                
                with c_btn2:
                    if lat and lon:
                        st.link_button("📍", f"https://www.google.com/maps/search/?api=1&query={lat},{lon}", help="Open Map", use_container_width=True)
                    else:
                        st.button("📍", disabled=True, key=f"no_map_{link_id}", use_container_width=True)

                with c_btn3:
                    if ai_summary:
                        with st.popover("📝", use_container_width=True):
                            st.caption("Nexus Analysis")
                            st.markdown(ai_summary)
                    else:
                        st.button("📝", disabled=True, key=f"no_note_{link_id}", use_container_width=True)
                
                # 4. Delete (Full Width below)
                if st.button("🗑️ Remove", key=f"del_{link_id}", use_container_width=True):
                    run_query("DELETE FROM links WHERE id = %s", (link_id,))
                    st.toast("Item removed.")
                    time.sleep(0.5)
                    st.rerun()

# --- MAIN APP ---
if st.session_state.user_id:
    show_dashboard()
else:
    show_login()