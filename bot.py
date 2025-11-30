import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import yt_dlp
import google.generativeai as genai

# --- IMPORT SECRETS ---
try:
    from config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY
except ImportError:
    print("CRITICAL ERROR: config.py not found. Please add TELEGRAM_BOT_TOKEN and GEMINI_API_KEY.")
    exit()

# --- CONFIGURE AI ---
genai.configure(api_key=GEMINI_API_KEY)

def get_ai_model():
    """Tries to get the best model, falls back if necessary."""
    try:
        # Try the fast, new model first
        return genai.GenerativeModel('gemini-2.5-flash-lite')
    except:
        # Fallback to the stable text model
        print("⚠️ Gemini 2.0 Flash not found. Falling back to Gemini Pro.")
        return genai.GenerativeModel('gemini-2.0-flash')

model = get_ai_model()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE links ADD COLUMN ai_summary TEXT")
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

# --- AI ANALYST ---
def analyze_content_with_ai(title, description, url):
    """Asks Gemini to analyze the metadata."""
    if len(title) < 5 and len(description) < 5:
        return "⚠️ Not enough text to analyze."

    prompt = f"""
    Analyze this content from a social media post.
    Title: {title}
    Description: {description}
    URL: {url}

    Your goal is to be a smart assistant.
    1. If it's a RECIPE: Extract ingredients and brief steps.
    2. If it's a LOCATION/TRAVEL: Extract the place name, city, and a Google Maps link if possible.
    3. If it's EDUCATIONAL: Summarize the key lesson.
    4. Otherwise: Write a 1-sentence summary.

    Output Format (Markdown):
    **Type:** [Recipe/Travel/etc]
    **Summary:** ...
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Provide a cleaner error message in console
        if "404" in str(e):
            print(f"AI Model Error: The model '{model.model_name}' was not found. Try upgrading google-generativeai.")
            # Emergency fallback attempt if global model failed during generation
            try:
                fallback_model = genai.GenerativeModel('gemini-pro')
                return fallback_model.generate_content(prompt).text
            except:
                return None
        print(f"AI Error: {e}")
        return None

# --- SMART SCRAPER (yt-dlp) ---
def smart_scrape(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ignoreerrors': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }

    data = {"url": url, "title": "", "image": "", "description": ""}

    # 1. Try yt-dlp 
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                data['title'] = info.get('title', '')
                data['image'] = info.get('thumbnail', '')
                data['description'] = info.get('description', '') or info.get('caption', '')
                
                if not data['title'] or data['title'] == "Instagram link":
                    if "instagram" in url:
                        data['title'] = "Instagram Reel"
                    elif "tiktok" in url:
                        data['title'] = "TikTok Video"
                
    except Exception as e:
        print(f"yt-dlp failed ({e}), falling back...")

    # 2. Fallback to Basic BeautifulSoup
    if not data['title'] or data['title'] == "Instagram Reel":
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title["content"]:
                data['title'] = og_title["content"]
            elif soup.title:
                data['title'] = soup.title.string.strip()

            if not data['image']:
                og_image = soup.find("meta", property="og:image")
                if og_image: data['image'] = og_image["content"]
            
            if not data['description']:
                og_desc = soup.find("meta", property="og:description")
                if og_desc: data['description'] = og_desc["content"]
                
        except Exception as e:
            print(f"Basic scrape error: {e}")

    if not data['title']:
        data['title'] = "Saved Link"

    return data

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🧠 **Nexus AI Online**\n\nSend me a Reel, Short, or TikTok.",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    url_match = re.search(r'(https?://\S+)', text)
    
    if not url_match:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Send a link to analyze.")
        return
    
    url = url_match.group(0)
    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="🧠 **Analyzing...**")

    # 1. Scrape
    data = smart_scrape(url)
    
    # 2. AI Analysis
    ai_note = analyze_content_with_ai(data['title'], data['description'], url)
    
    # 3. Save
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute("INSERT INTO links (url, title, image_url, ai_summary) VALUES (?, ?, ?, ?)", 
              (data['url'], data['title'], data['image'], ai_note))
    conn.commit()
    conn.close()

    # 4. Reply
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    
    response_text = f"✅ **Saved**\n{data['title']}\n\n"
    if ai_note:
        response_text += f"📝 **Nexus Note:**\n{ai_note}"
    
    try:
        if len(response_text) > 1000: response_text = response_text[:1000] + "..."
        
        if data['image']:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'], caption=response_text, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text, parse_mode='Markdown')
    except Exception as e:
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
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Nexus AI Bot is online...")
    application.run_polling()