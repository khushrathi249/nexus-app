import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import asyncio
import re
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CUSTOM MODULES ---
import database
import geo
import ai_engine
import scraper

# --- SECRET MANAGEMENT ---
try:
    from config import TELEGRAM_BOT_TOKEN
except ImportError:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# URL for the viewer (Set this in Render Env Vars)
VIEWER_URL = os.getenv("VIEWER_URL", "https://your-app-name.onrender.com")

if not TELEGRAM_BOT_TOKEN:
    print("❌ CRITICAL: TELEGRAM_BOT_TOKEN missing.")

# --- HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Nexus Bot is Alive")
    def log_message(self, format, *args): pass 

def start_health_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"✅ Health check server listening on port {port}")
        sys.stdout.flush()
        server.serve_forever()
    except Exception as e:
        print(f"❌ Failed to start health server: {e}")
        sys.stdout.flush()

threading.Thread(target=start_health_server, daemon=True).start()

# --- MODULE IMPORT CHECK ---
try:
    import database
    import geo
    import ai_engine
    import scraper
    modules_loaded = True
except Exception as e:
    print(f"❌ IMPORT ERROR: {e}")
    modules_loaded = False

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"❌ Update Error: {context.error}")
    sys.stdout.flush()

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = (
        f"🧠 **Nexus Online**\n\n"
        f"1. **Register:** `/register [username] [password]`\n"
        f"2. **Save:** Send any Link\n"
        f"3. **View:** `/site` to get your link\n"
        f"4. **Change Pass:** `/password [new_pass]`"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Usage: `/register [username] [password]`")
        return
    
    username = context.args[0]
    password = context.args[1]
    
    # Run DB operation in thread
    success, msg = await asyncio.to_thread(database.register_user, user_id, username, password)
    
    if success:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"✅ **Account Set!**\nUser: `{username}`\nPass: `{password}`\n\nLogin here: {VIEWER_URL}",
            parse_mode='Markdown'
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ {msg}")

async def site_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"🌐 **Open Viewer:**\n{VIEWER_URL}",
        disable_web_page_preview=True
    )

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Usage: `/password [new_password]`")
        return
    
    new_pass = context.args[0]
    success = await asyncio.to_thread(database.update_password, user_id, new_pass)
    
    if success:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Password Updated.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Account not found. Use `/register` first.")

async def geotest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    city = " ".join(context.args)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📍 Testing: {city}...")
    lat, lon = await asyncio.to_thread(geo.get_best_coordinates, city)
    if lat and lon: await context.bot.send_location(chat_id=update.effective_chat.id, latitude=lat, longitude=lon)
    else: await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Failed.")

# --- MESSAGE HANDLERS ---

async def handle_chat_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    user_id = update.effective_user.id
    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="🔍 **Searching Nexus...**", parse_mode='Markdown')
    
    results = await asyncio.to_thread(database.search_nexus_memory, user_id, query)
    
    if not results:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=f"❌ No matching links found.")
        return

    context_text = "Database Results:\n\n"
    for i, row in enumerate(results):
        title, summary, category, url, lat, lon = row
        loc_info = f"(Location: {lat}, {lon})" if lat else ""
        context_text += f"ITEM {i+1}:\nTitle: {title}\nCategory: {category}\nSummary: {summary}\nURL: {url} {loc_info}\n\n"

    answer = await asyncio.to_thread(ai_engine.generate_rag_answer, query, context_text)
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=answer)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id 
    url_match = re.search(r'(https?://\S+)', text)
    
    if not url_match:
        await handle_chat_query(update, context, text)
        return

    url = url_match.group(0)
    if database.is_duplicate(url, user_id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Already Saved.")
        return

    try: status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="📥 **Downloading...**")
    except: return 

    data = await asyncio.to_thread(scraper.download_and_scrape_blocking, url)
    
    lat, lon = None, None
    ai_summary, ai_category, location_str = "Error", "Inbox", None
    
    if data['video_path']:
        try: await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="🧠 **Watching...**")
        except: pass 

        ai_summary, ai_category, location_str, ai_coords = await asyncio.to_thread(
            ai_engine.analyze_with_video_blocking, 
            data['video_path'], data['title'], data['description'], data['url']
        )
        
        if location_str:
            lat, lon = await asyncio.to_thread(geo.get_best_coordinates, location_str)
            if not lat and ai_coords: lat, lon = ai_coords
        
        try: os.remove(data['video_path'])
        except: pass
    else:
        ai_summary, ai_category = ("⚠️ Restricted/Unreachable content.", "Inbox")

    save_data = {
        'url': data['url'], 'title': data['title'], 'image': data['image'],
        'ai_summary': ai_summary, 'category': ai_category, 'user_id': user_id,
        'lat': lat, 'lon': lon
    }
    database.save_link(save_data)

    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    except: pass
    
    display_text = f"📂 {ai_category}\n{data['title']}\n\n"
    if location_str and lat: display_text += f"📍 Found: {location_str}\n"
    if ai_summary: display_text += f"📝 Analysis:\n{ai_summary[:200]}..."

    try:
        if lat and lon:
            try: await context.bot.send_location(chat_id=update.effective_chat.id, latitude=lat, longitude=lon)
            except: pass
        if data['image']: await context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'], caption=display_text[:1000])
        else: await context.bot.send_message(chat_id=update.effective_chat.id, text=display_text[:1000])
    except: await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Saved: {data['title']}")

if __name__ == '__main__':
    if modules_loaded and TELEGRAM_BOT_TOKEN:
        try:
            print("🔄 Connecting to Database...")
            database.init_db()
            print("✅ Database Connected")
            
            application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).connect_timeout(30.0).read_timeout(30.0).write_timeout(30.0).build()
            application.add_error_handler(error_handler)
            
            # Register Handlers
            application.add_handler(CommandHandler('start', start))
            application.add_handler(CommandHandler('register', register_command)) # NEW
            application.add_handler(CommandHandler('password', password_command))
            application.add_handler(CommandHandler('site', site_command)) # NEW
            application.add_handler(CommandHandler('geotest', geotest))
            application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
            
            print("🤖 Nexus Modular Bot is online...")
            sys.stdout.flush()
            application.run_polling()
        except Exception as e:
            print(f"❌ Runtime Error: {e}")
            sys.stdout.flush()
            while True: time.sleep(10)
    else:
        print("❌ Bot Configuration Failed.")
        sys.stdout.flush()
        while True: time.sleep(10)