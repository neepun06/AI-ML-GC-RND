import os
import time
from dotenv import load_dotenv
from llama_parse import LlamaParse
from tavily import TavilyClient
import pandas as pd

# 1. LOAD API KEYS
load_dotenv()

# Initialize Tools
try:
    parser = LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        result_type="markdown",  # Crucial for tables
        verbose=True
    )
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    print("✅ Tools initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing tools: {e}")

def get_public_data(company_name):
    print(f"🔎 Deep-Scanning public web for: {company_name}...")
    
    # WE ASK 3 SPECIFIC QUESTIONS NOW
    queries = [
        f"{company_name} product portfolio technical specifications and manufacturing capacity",
        f"{company_name} recent awards certifications and client case studies 2024 2025",
        f"{company_name} revenue breakdown by geography and segment annual report"
    ]
    
    combined_context = ""
    for q in queries:
        try:
            print(f"   ...searching: {q}")
            # Increase max_tokens to get more detail
            context = tavily.get_search_context(query=q, search_depth="advanced", max_tokens=1500)
            combined_context += f"\n\n--- SEARCH: {q} ---\n{context}\n"
        except Exception as e:
            print(f"   ⚠️ Search failed for {q}: {e}")
            
    return combined_context

def ingest_private_file(file_path):
    print(f"📂 Ingesting file: {file_path}")
    
    if file_path.endswith(".pdf"):
        # LlamaParse is great for complex PDFs
        documents = parser.load_data(file_path)
        return f"\n\n--- PRIVATE FILE CONTENT (PDF) ---\n{documents[0].text}\n"
    
    elif file_path.endswith(".md") or file_path.endswith(".txt"):
        # Handle simple text files too
        with open(file_path, "r", encoding="utf-8") as f:
            return f"\n\n--- PRIVATE FILE CONTENT (TEXT) ---\n{f.read()}\n"

    elif file_path.endswith(".xlsx") or file_path.endswith(".xls"):
        # Basic Excel Handler - dumps all sheets to string
        try:
            df_dict = pd.read_excel(file_path, sheet_name=None)
            text_output = ""
            for sheet_name, df in df_dict.items():
                text_output += f"\nSheet: {sheet_name}\n{df.to_string()}\n"
            return f"\n\n--- PRIVATE FILE CONTENT (EXCEL) ---\n{text_output}\n"
        except Exception as e:
            print(f"⚠️ Excel ingest failed: {e}")
            return ""
    
    else:
        # Don't crash on unknown files, just skip them
        print(f"⚠️ Skipping unsupported file: {file_path}")
        return ""

def build_full_context(file_path, company_name):
    """
    Fusion: Combines Private + Public data into one 'Truth' block.
    """
    # 1. Get Private Data
    private_text = ingest_private_file(file_path)
    
    # 2. Get Public Data
    public_text = get_public_data(company_name)
    
    # 3. Fuse them
    full_context = private_text + public_text
    
    # Save to a debug file (Optional, but good for checking what the AI sees)
    with open(f"{company_name}_FULL_CONTEXT.txt", "w", encoding="utf-8") as f:
        f.write(full_context)
        
    return full_context

# --- TEST RUNNER (Remove or Comment out after testing) ---
if __name__ == "__main__":
    # Test with one of your EXISTING markdown files
    # REPLACE 'example_company.md' with the actual name of one file you have
    test_file = "example_company.md" 
    test_company = "Test Company Name"
    
    # Only run if the file actually exists
    if os.path.exists(test_file):
        print("🚀 Starting Test Run...")
        data = build_full_context(test_file, test_company)
        print("\n✅ DATA FUSION COMPLETE!")
        print(f"Preview (First 500 chars):\n{data[:500]}...")
    else:
        print(f"⚠️ Test file '{test_file}' not found. Please create a dummy file or point to a real one.")