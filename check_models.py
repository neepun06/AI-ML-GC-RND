import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Checking available models for your API key...")
try:
    available = False
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ FOUND: {m.name}")
            available = True
    if not available:
        print("❌ No text generation models found. Check your API Key permissions!")
except Exception as e:
    print(f"❌ Error: {e}")