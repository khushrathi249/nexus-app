import yt_dlp
import time
import glob
import os
import requests
from bs4 import BeautifulSoup
import random

def get_random_user_agent():
    # Rotate User Agents to avoid simple IP blocks
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]
    return random.choice(agents)

def download_and_scrape_blocking(url):
    filename = f"temp_{int(time.time())}"
    
    # --- ANONYMOUS CONFIGURATION ---
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{filename}.%(ext)s', 
        'quiet': True, 
        'no_warnings': True, 
        'max_filesize': 50*1024*1024, # 50MB Limit
        'ignoreerrors': True,         # Don't crash on restrictions
        'nocheckcertificate': True,
        # Spoof Headers to look like a generic browser request
        'http_headers': {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }
    
    data = {"url": url, "title": "", "image": "", "video_path": None, "description": ""}
    
    # 1. Try Heavy Video Download (Anonymous yt-dlp)
    print("📥 Attempting Anonymous Download...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info:
                data['title'] = info.get('title', '')
                data['image'] = info.get('thumbnail', '')
                desc = info.get('description', '') or info.get('caption', '')
                data['description'] = desc
                
                # Sanitize Title
                if not data['title'] or "instagram" in str(data['title']).lower():
                     if "instagram" in url: data['title'] = "Instagram Reel"
                
                # Check for file
                files = glob.glob(f"{filename}.*")
                if files: 
                    data['video_path'] = files[0]
                    print(f"✅ Download Success: {files[0]}")
            else:
                print("⚠️ yt-dlp: Content restricted or blocked.")

    except Exception as e:
        print(f"❌ yt-dlp Error: {e}")
        # Cleanup
        for f in glob.glob(f"{filename}*"):
            try: os.remove(f)
            except: pass

    # 2. ROBUST FALLBACK (Metadata Only)
    # If video failed (Restricted), grab what we can so the user can still save the link.
    if not data['title'] or data['title'] == "Instagram Reel" or not data['video_path']:
        print("⚠️ Falling back to HTML scraping (Metadata Only)...")
        try:
            # Requests Headers
            headers = {
                'User-Agent': get_random_user_agent(),
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Strategy 1: OpenGraph (OG) Tags - The most reliable source
                og_title = soup.find("meta", property="og:title")
                og_desc = soup.find("meta", property="og:description")
                og_image = soup.find("meta", property="og:image")
                
                if og_title: data['title'] = og_title.get("content", "")
                if og_desc: data['description'] = og_desc.get("content", "")
                if og_image: data['image'] = og_image.get("content", "")
                
                # Strategy 2: Clean up the title if it's junk
                if "instagram" in data['title'].lower():
                    # Sometimes the description in OG tags is actually the caption
                    if data['description']:
                        # Use first 50 chars of description as title if title is generic
                        data['title'] = (data['description'][:50] + '...') if len(data['description']) > 50 else data['description']
                    elif soup.title:
                        data['title'] = soup.title.string.replace("Instagram", "").strip()

        except Exception as e:
            print(f"❌ Fallback Error: {e}")
            
    if not data['title']:
        data['title'] = "Saved Link (Restricted)"

    return data