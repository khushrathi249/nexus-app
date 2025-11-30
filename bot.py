import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import yt_dlp
import google.generativeai as genai
import os
import time
import glob
import asyncio 
from geopy.geocoders import Nominatim
import urllib.parse

# --- IMPORT SECRETS ---
try:
    # Try importing Ola Key, but don't crash if missing
    from config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY
    try:
        from config import OLA_MAPS_API_KEY
    except ImportError:
        OLA_MAPS_API_KEY = None
        print("⚠️ OLA_MAPS_API_KEY not found in config.py. Ola Maps will be skipped.")
except ImportError:
    print("CRITICAL ERROR: config.py not found.")
    exit()

# --- CONFIGURE AI ---
genai.configure(api_key=GEMINI_API_KEY)

# --- GLOBAL ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"❌ Network/Update Error: {context.error}")

def get_working_model():
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash']
    print("🤖 Selecting Video-Capable AI model...")
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            model.generate_content("test")
            print(f"✅ Success: Connected to '{model_name}'")
            return model
        except Exception as e:
            print(f"⚠️ Error with '{model_name}': {e}")
            continue
    print("❌ CRITICAL: No working AI models found.")
    return None

model = get_working_model()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    for col in ["ai_summary", "category", "ai_summary"]:
        try: c.execute(f"ALTER TABLE links ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError: pass
    
    try: c.execute("ALTER TABLE links ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE links ADD COLUMN lat REAL")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE links ADD COLUMN lon REAL")
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

# --- DATABASE HELPERS ---
def is_duplicate(url, user_id):
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute("SELECT id FROM links WHERE url=? AND user_id=?", (url, user_id))
    result = c.fetchone()
    conn.close()
    return result is not None

# --- GEOCODING HELPERS ---

def get_coordinates_ola(location_name):
    """
    Custom Driver for Ola Maps Geocoding API.
    """
    if not OLA_MAPS_API_KEY:
        return None, None

    print(f"📍 Trying Ola Maps for: '{location_name}'")
    try:
        # NOTE: Ola Maps API endpoints change. Verify this in your dashboard documentation.
        # Common pattern: /places/v1/geocode or /places/v1/autocomplete
        base_url = "https://api.olamaps.io/places/v1/geocode" 
        
        params = {
            "address": location_name,
            "api_key": OLA_MAPS_API_KEY
        }
        
        # We use a short timeout because if Ola fails, we want to fallback to OSM quickly
        response = requests.get(base_url, params=params, timeout=5)
        data = response.json()
        
        # Parse logic (This depends on Ola's exact JSON response structure)
        if "geocodingResults" in data and len(data["geocodingResults"]) > 0:
            result = data["geocodingResults"][0]
            lat = result.get("geometry", {}).get("location", {}).get("lat")
            lng = result.get("geometry", {}).get("location", {}).get("lng")
            if lat and lng:
                print(f"✅ Ola Hit! {lat}, {lng}")
                return lat, lng
                
    except Exception as e:
        print(f"⚠️ Ola Maps Error: {e}")
    
    return None, None

def get_coordinates_osm(location_name):
    """
    OpenStreetMap (Nominatim) Fallback.
    """
    if not location_name or location_name.lower() == "none":
        return None, None
        
    geolocator = Nominatim(user_agent="NexusBot_v1")
    attempts = [location_name]
    
    if "," in location_name:
        parts = [p.strip() for p in location_name.split(",")]
        if len(parts) >= 2: attempts.append(f"{parts[0]}, {parts[1]}")
        attempts.append(parts[0]) 

    for search_query in attempts:
        try:
            print(f"📍 Trying OSM: '{search_query}'...")
            location = geolocator.geocode(search_query, timeout=5)
            if location:
                print(f"✅ OSM Hit! {location.latitude}, {location.longitude}")
                return location.latitude, location.longitude
        except Exception as e:
            print(f"   ❌ OSM Error: {e}")
            
    return None, None

def get_best_coordinates(location_name):
    """
    The Waterfall Strategy: Ola -> OSM
    """
    # 1. Try Ola (Best for India)
    lat, lon = get_coordinates_ola(location_name)
    if lat and lon: return lat, lon
    
    # 2. Try OSM (Global Free)
    lat, lon = get_coordinates_osm(location_name)
    if lat and lon: return lat, lon
    
    return None, None

# --- BLOCKING TASKS ---
def upload_to_gemini_blocking(path, mime_type=None):
    try:
        print(f"⬆️ Uploading {path} to Gemini...")
        file = genai.upload_file(path, mime_type=mime_type)
        print(f"✅ Upload Complete: {file.name}")
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        if file.state.name == "FAILED": return None
        return file
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

def analyze_with_video_blocking(video_path, title, description, url):
    if not model:
        return ("⚠️ AI Offline", "Inbox", None, None)

    video_file = upload_to_gemini_blocking(video_path, mime_type="video/mp4")
    if not video_file:
        return ("⚠️ Video processing failed.", "Inbox", None, None)

    prompt = f"""
    Analyze this social media post (Video + Text).
    
    --- TEXT CONTEXT ---
    Title: {title}
    Description: {description}
    URL: {url}
    
    --- TASKS ---
    1. CATEGORIZE: Pick ONE word: [Recipe, Travel, Tech, Education, Entertainment, Fitness, News].
    
    2. LOCATION_NAME: If Travel/Food, identify the city/landmark. "None" if unknown.
    
    3. COORDINATES: If you are confident about the specific landmark/location, provide estimated coordinates.
       - Format: 12.345, 67.890
       - If unknown, write "None".
    
    4. SUMMARY: Write a useful note.
    
    REQUIRED OUTPUT FORMAT:
    CATEGORY: [One Word]
    LOCATION_NAME: [Landmark, City, Country]
    COORDINATES: [Lat, Lon]
    SUMMARY: [Content]
    """

    try:
        print("🧠 Analyzing Video + Text Content...")
        response = model.generate_content([video_file, prompt])
        text = response.text
        
        try: genai.delete_file(video_file.name)
        except: pass
        
        category = "Inbox"
        location_str = None
        ai_coords = None
        summary = text
        
        cat_match = re.search(r'CATEGORY:\s*(\w+)', text, re.IGNORECASE)
        if cat_match: category = cat_match.group(1).capitalize()
            
        loc_match = re.search(r'LOCATION_NAME:\s*(.+)', text, re.IGNORECASE)
        if loc_match:
            raw_loc = loc_match.group(1).strip().replace('*', '').replace('_', '').strip()
            if raw_loc.lower() != "none" and len(raw_loc) > 2:
                location_str = raw_loc

        coord_match = re.search(r'COORDINATES:\s*(-?\d+\.\d+),\s*(-?\d+\.\d+)', text)
        if coord_match:
            try:
                ai_coords = (float(coord_match.group(1)), float(coord_match.group(2)))
                print(f"🎯 AI guessed coordinates: {ai_coords}")
            except: pass

        summary = re.sub(r'CATEGORY:.*\n?', '', summary, flags=re.IGNORECASE).strip()
        summary = re.sub(r'LOCATION_NAME:.*\n?', '', summary, flags=re.IGNORECASE).strip()
        summary = re.sub(r'COORDINATES:.*\n?', '', summary, flags=re.IGNORECASE).strip()
        summary = re.sub(r'SUMMARY:\s*', '', summary, flags=re.IGNORECASE).strip()

        return (summary, category, location_str, ai_coords)

    except Exception as e:
        print(f"AI Error: {e}")
        return ("⚠️ AI Analysis Failed.", "Inbox", None, None)

def download_and_scrape_blocking(url):
    print(f"\n--- 📥 DOWNLOADING VIDEO ---")
    filename = f"temp_{int(time.time())}"
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True, 'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024, 
    }
    data = {"url": url, "title": "", "image": "", "video_path": None, "description": ""}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            data['title'] = info.get('title', 'Saved Video')
            data['image'] = info.get('thumbnail', '')
            desc = info.get('description', '')
            caption = info.get('caption', '')
            data['description'] = desc if len(str(desc)) > len(str(caption)) else caption
            possible_files = glob.glob(f"{filename}.*")
            if possible_files: data['video_path'] = possible_files[0]
    except Exception as e:
        print(f"❌ Download failed: {e}")
        for f in glob.glob(f"{filename}*"):
            try: os.remove(f)
            except: pass
    return data

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🧠 **Nexus Full-Analysis Online**\n\nI will DOWNLOAD, WATCH, and GEOCODE your videos.",
        parse_mode='Markdown'
    )

async def geotest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /geotest CityName")
        return
    city = " ".join(context.args)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📍 Testing Geocoding for: {city}...")
    
    # Test Waterfall
    lat, lon = await asyncio.to_thread(get_best_coordinates, city)
    
    if lat and lon:
        await context.bot.send_location(chat_id=update.effective_chat.id, latitude=lat, longitude=lon)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Failed to find '{city}'.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id 
    url_match = re.search(r'(https?://\S+)', text)
    if not url_match:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Send a link.")
        return
    url = url_match.group(0)

    if is_duplicate(url, user_id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Already Saved.")
        return

    try: status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="📥 **Downloading...**")
    except: return 

    data = await asyncio.to_thread(download_and_scrape_blocking, url)
    
    lat, lon = None, None
    ai_summary, ai_category, location_str = "Error", "Inbox", None
    
    if data['video_path']:
        try: await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="🧠 **Watching & Mapping...**")
        except: pass 

        ai_summary, ai_category, location_str, ai_coords = await asyncio.to_thread(
            analyze_with_video_blocking,
            data['video_path'], 
            data['title'], 
            data['description'], 
            data['url']
        )
        
        # GEOCODING WATERFALL: Ola -> OSM -> AI Guess
        if location_str:
            lat, lon = await asyncio.to_thread(get_best_coordinates, location_str)
            
            # If both Ola and OSM failed, use AI's guess
            if not lat and ai_coords:
                print("⚠️ Maps API failed. Using AI Coordinates.")
                lat, lon = ai_coords
        
        try: os.remove(data['video_path'])
        except: pass
    else:
        ai_summary, ai_category = ("⚠️ Download failed.", "Inbox")

    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute("INSERT INTO links (url, title, image_url, ai_summary, category, user_id, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
              (data['url'], data['title'], data['image'], ai_summary, ai_category, user_id, lat, lon))
    conn.commit()
    conn.close()

    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    except: pass
    
    display_text = f"📂 {ai_category}\n{data['title']}\n\n"
    if location_str and lat:
        display_text += f"📍 Found: {location_str}\n"
    elif location_str:
        display_text += f"⚠️ Location: {location_str} (No Map)\n"
        
    if ai_summary:
        preview = ai_summary[:200] + "..." if len(ai_summary) > 200 else ai_summary
        display_text += f"📝 Analysis:\n{preview}"

    try:
        if lat and lon:
            try: await context.bot.send_location(chat_id=update.effective_chat.id, latitude=lat, longitude=lon)
            except: pass

        if data['image']:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'], caption=display_text[:1000])
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=display_text[:1000])
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Saved: {data['title']}")

if __name__ == '__main__':
    init_db()
    
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0) 
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )
    
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('geotest', geotest))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Nexus Hybrid-Geo Bot is online...")
    application.run_polling()