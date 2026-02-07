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
        result_type="markdown", 
        verbose=True
    )
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    print("✅ Tools initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing tools: {e}")

def get_public_data(company_name):
    print(f"🔎 Deep-Scanning public web for: {company_name}...")
    
    queries = [
        f"{company_name} product portfolio technical specifications and manufacturing capacity",
        f"{company_name} recent awards certifications and client case studies 2024 2025",
        f"{company_name} revenue breakdown by geography and segment annual report"
    ]
    
    combined_context = ""
    for q in queries:
        try:
            print(f"   ...searching: {q}")
            context = tavily.get_search_context(query=q, search_depth="advanced", max_tokens=1500)
            combined_context += f"\n\n--- PUBLIC WEB SEARCH: {q} ---\n{context}\n"
        except Exception as e:
            print(f"   ⚠️ Search failed for {q}: {e}")
            
    return combined_context

def ingest_private_file(file_path):
    """
    Ingests a single file. Returns empty string if file type is unsupported.
    """
    filename = os.path.basename(file_path)
    print(f"   📄 Reading: {filename}")
    
    header = f"\n\n--- PRIVATE DATA SOURCE: {filename} ---\n"
    
    try:
        if file_path.endswith(".pdf"):
            documents = parser.load_data(file_path)
            return header + documents[0].text
        
        elif file_path.endswith(".md") or file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                return header + f.read()

        elif file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df_dict = pd.read_excel(file_path, sheet_name=None)
            text_output = header
            for sheet_name, df in df_dict.items():
                text_output += f"\n[Sheet: {sheet_name}]\n{df.to_string()}\n"
            return text_output
        
        else:
            print(f"   ⚠️ Skipping unsupported file: {filename}")
            return ""
            
    except Exception as e:
        print(f"   ❌ Error reading {filename}: {e}")
        return ""

def build_full_context(path, company_name):
    """
    Smart Fusion: Handles both Single Files AND Folders (Data Packs).
    """
    private_text = ""
    
    # 1. Check if input is a Data Pack (Folder) or Single File
    if os.path.isdir(path):
        print(f"📂 Detected Data Pack Folder: {path}")
        # Iterate through all files in the folder
        for filename in os.listdir(path):
            if filename.startswith("."): continue # Skip hidden files
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                private_text += ingest_private_file(file_path)
    else:
        # It's just a single file (Backward compatibility)
        print(f"📂 Detected Single File: {path}")
        private_text = ingest_private_file(path)
    
    # 2. Get Public Data
    public_text = get_public_data(company_name)
    
    # 3. Fuse them
    full_context = private_text + public_text
    
    # Debug save
    with open(f"{company_name}_FULL_CONTEXT.txt", "w", encoding="utf-8") as f:
        f.write(full_context)
        
    return full_context

if __name__ == "__main__":
    # Test block
    pass