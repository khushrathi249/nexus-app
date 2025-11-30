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

# --- IMPORT SECRETS ---
try:
    from config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY
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
    for col in ["ai_summary", "category"]:
        try:
            c.execute(f"ALTER TABLE links ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
            
    c.execute('''CREATE TABLE IF NOT EXISTS links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  url TEXT, 
                  title TEXT, 
                  image_url TEXT,
                  category TEXT DEFAULT 'Inbox',
                  ai_summary TEXT)''')
    conn.commit()
    conn.close()

# --- BLOCKING TASKS (Run in threads) ---

def upload_to_gemini_blocking(path, mime_type=None):
    try:
        print(f"⬆️ Uploading {path} to Gemini...")
        file = genai.upload_file(path, mime_type=mime_type)
        print(f"✅ Upload Complete: {file.name}")
        
        while file.state.name == "PROCESSING":
            print("⏳ Gemini is processing the video...")
            time.sleep(2)
            file = genai.get_file(file.name)
            
        if file.state.name == "FAILED":
            print("❌ Video processing failed.")
            return None
        return file
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

def analyze_with_video_blocking(video_path, title, description, url):
    if not model:
        return ("⚠️ AI Offline", "Inbox")

    video_file = upload_to_gemini_blocking(video_path, mime_type="video/mp4")
    if not video_file:
        return ("⚠️ Video processing failed. Link saved without analysis.", "Inbox")

    prompt = f"""
    Analyze this social media post. 
    CRITICAL: You must combine the VIDEO CONTENT (Audio/Visuals) with the TEXT DESCRIPTION provided below.
    
    --- TEXT CONTEXT ---
    Title: {title}
    Description: {description}
    URL: {url}
    
    --- TASKS ---
    1. CATEGORIZE: Pick ONE word: [Recipe, Travel, Tech, Education, Entertainment, Fitness, News].
    
    2. SUMMARY: 
       - If Recipe: Check the DESCRIPTION for ingredient lists. If missing, listen to the audio.
       - If Travel: Check the DESCRIPTION for location tags. If missing, look at video landmarks.
       - If Talking Head: Summarize exactly what they are teaching/saying.
    
    REQUIRED OUTPUT FORMAT:
    CATEGORY: [One Word]
    SUMMARY: [Content]
    """

    try:
        print("🧠 Analyzing Video + Text Content...")
        response = model.generate_content([video_file, prompt])
        text = response.text
        
        try:
            genai.delete_file(video_file.name)
        except:
            pass
        
        category = "Inbox"
        summary = text
        
        cat_match = re.search(r'CATEGORY:\s*(\w+)', text, re.IGNORECASE)
        if cat_match:
            category = cat_match.group(1).capitalize()
            summary = re.sub(r'CATEGORY:.*\n?', '', text, flags=re.IGNORECASE).strip()
            summary = re.sub(r'SUMMARY:\s*', '', summary, flags=re.IGNORECASE).strip()

        return (summary, category)

    except Exception as e:
        print(f"AI Error: {e}")
        return ("⚠️ AI Analysis Failed.", "Inbox")

def download_and_scrape_blocking(url):
    print(f"\n--- 📥 DOWNLOADING VIDEO ---")
    filename = f"temp_{int(time.time())}"
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
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
            if not data['description']: data['description'] = ""
            
            possible_files = glob.glob(f"{filename}.*")
            if possible_files:
                data['video_path'] = possible_files[0]
                print(f"✅ Video Downloaded: {data['video_path']}")
                print(f"✅ Metadata - Description Length: {len(data['description'])} chars")
            else:
                print("❌ Download finished but file not found.")

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
        text="🧠 **Nexus Full-Analysis Online**\n\nI will DOWNLOAD and WATCH videos.\n_Note: This takes about 15-30 seconds per link._",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    url_match = re.search(r'(https?://\S+)', text)
    if not url_match:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Send a link.")
        return
    
    url = url_match.group(0)
    
    try:
        status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="📥 **Downloading Video...**")
    except Exception as e:
        print(f"❌ Network Error sending status: {e}")
        return 

    # 1. Download
    data = await asyncio.to_thread(download_and_scrape_blocking, url)
    
    if data['video_path']:
        try:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="🧠 **Watching & Listening...**")
        except: 
            pass 

        # 2. Analyze
        ai_summary, ai_category = await asyncio.to_thread(
            analyze_with_video_blocking,
            data['video_path'], 
            data['title'], 
            data['description'], 
            data['url']
        )
        
        # 3. Cleanup
        try:
            os.remove(data['video_path'])
            print(f"🗑️ Deleted local temp file")
        except:
            pass
    else:
        ai_summary, ai_category = ("⚠️ Video download failed. Saved link only.", "Inbox")

    # 4. Save
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute("INSERT INTO links (url, title, image_url, ai_summary, category) VALUES (?, ?, ?, ?, ?)", 
              (data['url'], data['title'], data['image'], ai_summary, ai_category))
    conn.commit()
    conn.close()

    # 5. Reply (ROBUST FALLBACK SYSTEM)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    except:
        pass
    
    # Construct Plain Text Version
    plain_text = f"📂 {ai_category}\n{data['title']}\n\n"
    if ai_summary:
        preview = ai_summary[:200] + "..." if len(ai_summary) > 200 else ai_summary
        plain_text += f"📝 Analysis:\n{preview}"

    # Construct Markdown Version (Risky)
    md_text = f"📂 *{ai_category}*\n{data['title']}\n\n"
    if ai_summary:
        preview = ai_summary[:200] + "..." if len(ai_summary) > 200 else ai_summary
        md_text += f"📝 *Analysis:*\n{preview}"
    
    try:
        # ATTEMPT 1: Pretty Markdown
        if data['image']:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'], caption=md_text[:1000], parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=md_text[:1000], parse_mode='Markdown')
            
    except Exception as e:
        print(f"⚠️ Markdown failed ({e}). Sending Plain Text Fallback.")
        # ATTEMPT 2: Plain Text (Reliable)
        try:
            if data['image']:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'], caption=plain_text[:1000])
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=plain_text[:1000])
        except Exception as e2:
            print(f"❌ Plain text failed: {e2}")

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
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Nexus Video-Analysis Bot is online...")
    application.run_polling()