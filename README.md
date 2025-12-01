🧠 #Nexus - Your Second Brain for Social Content

Nexus is a self-hosted, AI-powered bookmarking tool designed to organize the chaos of social media saves. It takes links (Instagram Reels, TikToks, YouTube Shorts) sent via Telegram, downloads the video content, and uses Multimodal AI (Gemini 2.0) to watch, listen, and analyze them.

It automatically categorizes content, extracts recipes/ingredients, identifies travel locations (with map coordinates), and transcribes visual text—turning mindless scrolling into a searchable knowledge base.

✨ Key Features

Zero-Friction Capture: Send a link to your Telegram Bot. That's it.

Multimodal AI Analysis: Nexus downloads the video and uses Google Gemini to "watch" it. It extracts:

Recipes: Ingredients and steps (even if only shown on screen).

Travel: Specific landmarks and cities with geocoordinates.

Tech/Education: Summaries of the core lesson.

Smart Geocoding: Automatically maps travel content using Ola Maps or OpenStreetMap.

"Ask Nexus" (RAG): Chat with your saved database. Ask "Where was that sushi place?" or "Show me pasta recipes" and it searches your saved content.

User Isolation: Multi-user support. Your data is private to your Telegram ID.

Visual Dashboard: A clean, mobile-responsive Streamlit web app to browse, search, and manage your stacks.

🛠️ Tech Stack

Backend: Python 3.11

Database: PostgreSQL (via Supabase/Neon)

AI Engine: Google Gemini 1.5/2.0 Flash

Scraping: yt-dlp + requests (with stealth headers)

Frontend: Streamlit

Interface: python-telegram-bot

Deployment: Docker (Optimized for Render.com)

🚀 Local Installation

1. Prerequisites

Python 3.10+

FFmpeg installed on your system (Required for video processing).

A PostgreSQL Database (Local or Cloud).

2. Clone & Install

git clone [https://github.com/yourusername/nexus-app.git](https://github.com/yourusername/nexus-app.git)
cd nexus-app
pip install -r requirements.txt


3. Configuration

Create a config.py file in the root directory (do not commit this file):

config.py

TELEGRAM_BOT_TOKEN = "your_bot_father_token"

GEMINI_API_KEY = "your_google_ai_studio_key"

DATABASE_URL = "postgresql://user:pass@host:port/db"

OLA_MAPS_API_KEY = "your_ola_maps_key" # Optional, defaults to OSM if missing


4. Run the Application

You need to run two terminal windows:

Terminal 1: The Bot (Backend)

python bot.py


Terminal 2: The Viewer (Frontend)

streamlit run viewer.py


Access the viewer at http://localhost:8501.

☁️ Deployment (Render.com)

This project is pre-configured for Render.com Free Tier using Docker.

Push to GitHub: Ensure your code (including render.yaml and Dockerfile) is in a GitHub repository.

Create Blueprint:

Go to Render Dashboard -> Blueprints -> New Blueprint Instance.

Connect your repository.

Set Environment Variables: Render will prompt you for these secrets:

TELEGRAM_BOT_TOKEN

GEMINI_API_KEY

DATABASE_URL (Use the Transaction Pooler URL port 6543 for Supabase)

OLA_MAPS_API_KEY (Optional)

Deploy: Click Apply. Render will spin up the Bot and Viewer services automatically.

Note: The bot.py includes a dummy health-check server to keep the Render Web Service alive on the free tier.

📖 Usage Guide

1. Registration

Start the bot in Telegram:

/start
/register [username] [password]


Example: /register khush mysecret123

2. Saving Content

Simply paste a link (Instagram, TikTok, YouTube) into the chat.

Nexus will download the video.

AI will analyze it.

It will reply with a summary and category.

3. Viewing Content

Open your deployed Streamlit URL (e.g., https://nexus-viewer.onrender.com).

Log in with the Username and Password you set in Telegram.

Browse, Search, or View Map locations.

4. Chatting with Data

In Telegram, just send a text message (without a link).

User: "Show me movie recommendations."

Nexus: "Based on your saves, you have 3 movie lists..."

🛡️ Handling Restricted Content

If downloading fails (Age-gated/Copyrighted content):

Nexus falls back to a Metadata Scrape (Title/Image only).

The link is saved, but the AI summary will be less detailed.

Power User Fix: You can add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to your environment variables to enable authenticated scraping (use at your own risk).

🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
