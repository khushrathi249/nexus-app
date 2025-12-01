import requests
from geopy.geocoders import Nominatim
from settings import OLA_MAPS_API_KEY # UPDATED IMPORT

def get_coordinates_ola(location_name):
    if not OLA_MAPS_API_KEY: return None, None
    print(f"📍 Trying Ola Maps for: '{location_name}'")
    try:
        base_url = "https://api.olamaps.io/places/v1/geocode" 
        params = {"address": location_name, "api_key": OLA_MAPS_API_KEY}
        response = requests.get(base_url, params=params, timeout=5)
        data = response.json()
        if "geocodingResults" in data and len(data["geocodingResults"]) > 0:
            result = data["geocodingResults"][0]
            lat = result.get("geometry", {}).get("location", {}).get("lat")
            lng = result.get("geometry", {}).get("location", {}).get("lng")
            if lat and lng: return lat, lng
    except Exception as e: print(f"⚠️ Ola Maps Error: {e}")
    return None, None

def get_coordinates_osm(location_name):
    if not location_name or location_name.lower() == "none": return None, None
    geolocator = Nominatim(user_agent="NexusBot_v1")
    attempts = [location_name]
    if "," in location_name:
        parts = [p.strip() for p in location_name.split(",")]
        if len(parts) >= 2: attempts.append(f"{parts[0]}, {parts[1]}")
        attempts.append(parts[0]) 
    for search_query in attempts:
        try:
            print(f"📍 Trying OSM: '{search_query}'...")
            location = geolocator.geocode(search_query, timeout=5)
            if location: return location.latitude, location.longitude
        except Exception as e: print(f"   ❌ OSM Error: {e}")
    return None, None

def get_best_coordinates(location_name):
    lat, lon = get_coordinates_ola(location_name)
    if lat and lon: return lat, lon
    lat, lon = get_coordinates_osm(location_name)
    if lat and lon: return lat, lon
    return None, None