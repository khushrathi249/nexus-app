import google.generativeai as genai
import time
import re
import os

try:
    from config import GEMINI_API_KEY
    genai.configure(api_key=GEMINI_API_KEY)
except ImportError:
    print("CRITICAL: GEMINI_API_KEY missing in config.py")

def get_working_model():
    models_to_try = ['gemini-2.0-flash', 'gemini-2.5-flash-lite']
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

# Global model instance
model = get_working_model()

def upload_to_gemini_blocking(path, mime_type=None):
    try:
        file = genai.upload_file(path, mime_type=mime_type)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        if file.state.name == "FAILED": return None
        return file
    except Exception: return None

def analyze_with_video_blocking(video_path, title, description, url):
    if not model: return ("⚠️ AI Offline", "Inbox", None, None)
    
    video_file = upload_to_gemini_blocking(video_path, mime_type="video/mp4")
    if not video_file: return ("⚠️ Video processing failed.", "Inbox", None, None)

    # ROBUST PROMPT WITH 'INBOX' FALLBACK
    prompt = f"""
    Analyze this social media post (Video + Text).
    
    --- METADATA ---
    Title: {title}
    Description: {description}
    URL: {url}
    
    --- ANALYSIS INSTRUCTIONS ---
    1. CATEGORIZE: Choose ONE word from this list: [Recipe, Travel, Tech, Education, Entertainment, Fitness, News, Movies, Books, Inbox].
       - CRITICAL: If the content is random, personal, a meme, or does not fit a specific niche, strictly select 'Inbox'.
    
    2. LOCATION_NAME (STRICT): 
       - ONLY extract a location if the video is EXPLICITLY about visiting that specific place (Travel guide, Restaurant review, Hiking trail, Event).
       - DO NOT extract locations for: Movie settings, Tech company HQs, News studios, or general "vlogs" where the location is irrelevant.
       - If not a travel/place recommendation, write "None".
    
    3. COORDINATES: If you identified a valid LOCATION_NAME above, provide estimated coordinates (12.345, 67.890). Otherwise "None".
    
    4. SUMMARY (CRITICAL):
       - GENERAL RULE: If the video shows a LIST of text items (Movies, Books, Tools, Specs), YOU MUST TRANSCRIBE THE VISUAL TEXT (OCR).
       
       - IF RECIPE: List ingredients with measurements (if heard/seen) and step-by-step instructions.
       - IF TRAVEL: Name the specific location/landmark, best time to visit, and cost if mentioned.
       - IF TECH: List the specific Product Name, Key Specs mentioned, and the Verdict (Good/Bad).
       - IF EDUCATION: Summarize the main lesson into bullet points. Capture any specific tools or websites mentioned.
       - IF FITNESS: List the specific Exercises, Sets, and Reps shown or spoken.
       - IF MOVIES/BOOKS: List the exact Titles and Authors/Directors shown on screen.
       - IF NEWS: Summarize the Headline, the "Who/What/Where", and the outcome.
       - IF ENTERTAINMENT: Summarize the plot of the skit or the key punchline.
       - IF INBOX: Provide a general description of what happens in the video.
    
    REQUIRED OUTPUT FORMAT:
    CATEGORY: [One Word]
    LOCATION_NAME: [Landmark, City, Country OR None]
    COORDINATES: [Lat, Lon OR None]
    SUMMARY: [Bulleted list of content or detailed paragraph]
    """
    try:
        response = model.generate_content([video_file, prompt])
        text = response.text
        try: genai.delete_file(video_file.name)
        except: pass
        
        category, location_str, ai_coords, summary = "Inbox", None, None, text
        
        # Robust regex for Category
        match = re.search(r'CATEGORY:\s*(.+)', text, re.IGNORECASE)
        if match: 
            raw_cat = match.group(1).strip().replace('*', '').replace('_', '').strip()
            category = raw_cat.split(' ')[0].capitalize()
        
        match = re.search(r'LOCATION_NAME:\s*(.+)', text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip().replace('*','').replace('_','').strip()
            if raw.lower() not in ["none", "unknown", "n/a"] and len(raw) > 2: 
                location_str = raw
                
        match = re.search(r'COORDINATES:\s*(-?\d+\.\d+),\s*(-?\d+\.\d+)', text)
        if match: ai_coords = (float(match.group(1)), float(match.group(2)))
        
        summary = re.sub(r'(CATEGORY|LOCATION_NAME|COORDINATES):.*\n?', '', summary, flags=re.IGNORECASE).strip()
        summary = re.sub(r'SUMMARY:\s*', '', summary, flags=re.IGNORECASE).strip()
        return (summary, category, location_str, ai_coords)
    except Exception: return ("⚠️ Analysis Failed.", "Inbox", None, None)

def generate_rag_answer(query, context_text):
    if not model: return "⚠️ AI Offline."
    rag_prompt = f"""
    You are Nexus, a personal knowledge assistant.
    User Question: "{query}"
    
    {context_text}
    
    TASK: Answer the user's question based ONLY on the items above.
    """
    try:
        response = model.generate_content(rag_prompt)
        return response.text
    except Exception:
        return "⚠️ Error generating answer."