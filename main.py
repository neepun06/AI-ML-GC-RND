import os
import sys
from analyze import analyze_company
from ppt_engine import generate_deck
from generate_citations import create_citation_doc 

EXAMPLES_FOLDER = "examples"

def run_pipeline(item_name):
    # LOGIC UPDATE: Handle both Files and Folders
    full_path = os.path.join(EXAMPLES_FOLDER, item_name)
    
    if os.path.isdir(full_path):
        # Case A: It's a Data Pack Folder (e.g., "Company_A_Data")
        # Use folder name as company name (replace underscores with spaces)
        company_name = item_name.replace("_", " ").strip()
        print(f"\n🚀 Processing Data Pack for: {company_name}")
    else:
        # Case B: It's a Single File (e.g., "Gati-OnePager.md")
        company_name = item_name.rsplit('.', 1)[0].replace("-OnePager", "").replace("_", " ")
        print(f"\n🚀 Processing File for: {company_name}")
    
    # 1. Brain (Passes the full path - analyze.py calls ingest.py which now handles folders)
    analyze_company(full_path, company_name)
    
    # 2. Artist
    try:
        generate_deck(company_name)
    except Exception as e:
        print(f"❌ PPT Error: {e}")

    # 3. Docs
    try:
        create_citation_doc(company_name)
    except Exception as e:
        print(f"⚠️ Citation Error: {e}")

def show_menu():
    if not os.path.exists(EXAMPLES_FOLDER):
        print(f"❌ '{EXAMPLES_FOLDER}' folder missing.")
        return

    # UPDATED: List both supported files AND directories
    items = []
    for entry in os.listdir(EXAMPLES_FOLDER):
        full_path = os.path.join(EXAMPLES_FOLDER, entry)
        
        # Add if it's a Folder (Data Pack)
        if os.path.isdir(full_path) and not entry.startswith('.'):
            items.append(entry)
        
        # Add if it's a supported File
        elif os.path.isfile(full_path) and entry.endswith(('.md', '.pdf', '.txt', '.xlsx')):
            items.append(entry)
    
    if not items:
        print("❌ No files or data packs found in 'examples/'.")
        return

    print("\n--- KELP GENERATOR ---")
    print("Files and Data Pack Folders found:")
    for i, item in enumerate(items):
        type_label = "[FOLDER]" if os.path.isdir(os.path.join(EXAMPLES_FOLDER, item)) else "[FILE]  "
        print(f"[{i+1}] {type_label} {item}")
    
    try:
        idx = int(input("\nSelect Item #: ")) - 1
        if 0 <= idx < len(items):
            run_pipeline(items[idx])
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")

if __name__ == "__main__":
    show_menu()