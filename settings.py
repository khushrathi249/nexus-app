import os

# 1. Try loading from local file (Dev)
try:
    import config
    TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
    GEMINI_API_KEY = config.GEMINI_API_KEY
    # Use getattr to avoid crash if key is missing
    OLA_MAPS_API_KEY = getattr(config, 'OLA_MAPS_API_KEY', None)
    DATABASE_URL = getattr(config, 'DATABASE_URL', None)
except ImportError:
    # 2. Fallback to Environment Variables (Prod/Cloud)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OLA_MAPS_API_KEY = os.getenv("OLA_MAPS_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")

# Validation
if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("CRITICAL: API Keys missing.")

if not DATABASE_URL:
    raise ValueError("CRITICAL: DATABASE_URL is missing. Set it in config.py or Environment Variables.")