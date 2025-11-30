import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import asyncio
import re
import os

# --- CUSTOM MODULES ---
import database
import geo
import ai_engine
import scraper
from config import TELEGRAM_BOT_TOKEN

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"❌ Update Error: {context.error}")

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="🧠 **Nexus Online**\n\n- Send Link: Save & Analyze\n- Send Text: Search & Chat", 
        parse_mode='Markdown'
    )

async def geotest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    city = " ".join(context.args)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📍 Testing: {city}...")
    lat, lon = await asyncio.to_thread(geo.get_best_coordinates, city)
    if lat and lon: await context.bot.send_location(chat_id=update.effective_chat.id, latitude=lat, longitude=lon)
    else: await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Failed.")

async def handle_chat_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    user_id = update.effective_user.id
    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="🔍 **Searching Nexus...**", parse_mode='Markdown')
    
    # 1. Search DB
    results = await asyncio.to_thread(database.search_nexus_memory, user_id, query)
    
    if not results:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=f"❌ No matching links found.")
        return

    # 2. Build Context
    context_text = "Database Results:\n\n"
    for i, row in enumerate(results):
        title, summary, category, url, lat, lon = row
        loc_info = f"(Location: {lat}, {lon})" if lat else ""
        context_text += f"ITEM {i+1}:\nTitle: {title}\nCategory: {category}\nSummary: {summary}\nURL: {url} {loc_info}\n\n"

    # 3. Generate Answer
    answer = await asyncio.to_thread(ai_engine.generate_rag_answer, query, context_text)
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=answer)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id 
    url_match = re.search(r'(https?://\S+)', text)
    
    # Not a link? It's a chat query.
    if not url_match:
        await handle_chat_query(update, context, text)
        return

    # It's a link.
    url = url_match.group(0)
    if database.is_duplicate(url, user_id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Already Saved.")
        return

    try: status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="📥 **Downloading...**")
    except: return 

    # 1. Download
    data = await asyncio.to_thread(scraper.download_and_scrape_blocking, url)
    
    lat, lon = None, None
    ai_summary, ai_category, location_str = "Error", "Inbox", None
    
    if data['video_path']:
        try: await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="🧠 **Watching...**")
        except: pass 

        # 2. Analyze
        ai_summary, ai_category, location_str, ai_coords = await asyncio.to_thread(
            ai_engine.analyze_with_video_blocking, 
            data['video_path'], data['title'], data['description'], data['url']
        )
        
        # 3. Geocode
        if location_str:
            lat, lon = await asyncio.to_thread(geo.get_best_coordinates, location_str)
            if not lat and ai_coords: lat, lon = ai_coords
        
        # Cleanup
        try: os.remove(data['video_path'])
        except: pass
    else:
        ai_summary, ai_category = ("⚠️ Download failed.", "Inbox")

    # 4. Save
    # Prepare data dict
    save_data = {
        'url': data['url'], 'title': data['title'], 'image': data['image'],
        'ai_summary': ai_summary, 'category': ai_category, 'user_id': user_id,
        'lat': lat, 'lon': lon
    }
    database.save_link(save_data)

    # 5. Reply
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
    database.init_db()
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).connect_timeout(30.0).read_timeout(30.0).write_timeout(30.0).build()
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('geotest', geotest))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Nexus Modular Bot is online...")
    application.run_polling()