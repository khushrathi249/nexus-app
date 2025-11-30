import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import requests
from bs4 import BeautifulSoup
import sqlite3
import re

# --- IMPORT SECRETS ---
try:
    from config import TELEGRAM_BOT_TOKEN
except ImportError:
    print("CRITICAL ERROR: config.py not found. Please create it and add TELEGRAM_BOT_TOKEN.")
    exit()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("nexus.db") # Renamed DB to nexus.db
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  url TEXT, 
                  title TEXT, 
                  image_url TEXT,
                  category TEXT DEFAULT 'Inbox')''')
    conn.commit()
    conn.close()

# --- SCRAPER LOGIC ---
def scrape_metadata(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.title.string.strip() if soup.title else "Unknown Title"
        og_title = soup.find("meta", property="og:title")
        if og_title: title = og_title["content"]

        image_url = ""
        og_image = soup.find("meta", property="og:image")
        if og_image: image_url = og_image["content"]
            
        return {"url": url, "title": title, "image": image_url}
    except Exception as e:
        print(f"Scrape Error: {e}")
        return {"url": url, "title": "Error fetching title", "image": ""}

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 **Welcome to Nexus**\n\nSend a link to save it.\nAdd a tag to organize: `https://google.com #work`",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    url_match = re.search(r'(https?://\S+)', text)
    if not url_match:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="That doesn't look like a link.")
        return
    
    url = url_match.group(0)
    tag_match = re.search(r'#(\w+)', text)
    category = tag_match.group(1).capitalize() if tag_match else "Inbox"

    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"WAIT: Nexus is capturing **{category}**...", parse_mode='Markdown')

    data = scrape_metadata(url)
    
    conn = sqlite3.connect("nexus.db")
    c = conn.cursor()
    c.execute("INSERT INTO links (url, title, image_url, category) VALUES (?, ?, ?, ?)", 
              (data['url'], data['title'], data['image'], category))
    conn.commit()
    conn.close()

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        
        caption = f"✅ **Saved to Nexus / {category}**\n{data['title']}"
        
        if data['image']:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=data['image'],
                caption=caption,
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=caption, parse_mode='Markdown')
    except Exception as e:
        print(f"Telegram Error: {e}")

if __name__ == '__main__':
    init_db()
    
    # Using specific timeouts to handle network issues
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
    
    print("Nexus Bot is online...")
    application.run_polling()