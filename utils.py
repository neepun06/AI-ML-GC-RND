import os
import requests
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

def download_image(query, orientation="landscape"):
    """
    Searches Pexels for a high-quality, generic business image.
    Returns: BytesIO object (image in memory) or None.
    """
    if not PEXELS_API_KEY:
        print("⚠️ No PEXELS_API_KEY found. Using placeholders.")
        return None

    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1&orientation={orientation}"
    
    try:
        print(f"🖼️ Searching Pexels for: '{query}'...")
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        if data.get('photos'):
            img_url = data['photos'][0]['src']['large']
            img_response = requests.get(img_url)
            return BytesIO(img_response.content)
        else:
            print("   No images found.")
            return None
    except Exception as e:
        print(f"   Image fetch failed: {e}")
        return None