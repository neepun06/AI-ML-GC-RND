import os
import sys
# Make sure imports match exactly
from analyze import analyze_company
from ppt_engine import generate_deck
from generate_citations import create_citation_doc 

EXAMPLES_FOLDER = "examples"

def run_pipeline(filename):
    # Clean name: "Gati-OnePager.md" -> "Gati"
    company_name = filename.rsplit('.', 1)[0].replace("-OnePager", "").replace("_", " ")
    file_path = os.path.join(EXAMPLES_FOLDER, filename)
    
    print(f"\n🚀 Processing: {company_name}")
    
    # 1. Brain
    analyze_company(file_path, company_name)
    
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

    files = [f for f in os.listdir(EXAMPLES_FOLDER) if f.endswith(('.md', '.pdf', '.txt'))]
    
    if not files:
        print("❌ No files found.")
        return

    print("\n--- KELP GENERATOR ---")
    for i, f in enumerate(files):
        print(f"[{i+1}] {f}")
    
    try:
        idx = int(input("\nSelect File #: ")) - 1
        if 0 <= idx < len(files):
            run_pipeline(files[idx])
    except ValueError:
        print("Invalid input.")

if __name__ == "__main__":
    show_menu()