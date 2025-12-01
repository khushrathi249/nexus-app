import yt_dlp
import time
import glob
import os

def download_and_scrape_blocking(url):
    filename = f"temp_{int(time.time())}"
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{filename}.%(ext)s', 
        'quiet': True, 
        'no_warnings': True, 
        'max_filesize': 50*1024*1024
    }
    
    data = {"url": url, "title": "", "image": "", "video_path": None, "description": ""}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            data['title'] = info.get('title', 'Saved Video')
            data['image'] = info.get('thumbnail', '')
            desc = info.get('description', '') or info.get('caption', '')
            data['description'] = desc
            
            # Find the actual file
            files = glob.glob(f"{filename}.*")
            if files: 
                data['video_path'] = files[0]
    except Exception as e:
        print(f"❌ Scraper Error: {e}")
        # Cleanup
        for f in glob.glob(f"{filename}*"):
            try: os.remove(f)
            except: pass
            
    return data