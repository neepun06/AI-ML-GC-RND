import os
import json
import glob
import google.generativeai as genai
from dotenv import load_dotenv
from ingest import build_full_context

# 1. SETUP
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = {
    "temperature": 0.2,
    "top_p": 0.95,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

# UPDATE MODEL NAME IF NEEDED (e.g., "gemini-1.5-pro")
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    generation_config=generation_config,
)

def analyze_company(target_file, company_name):
    print(f"🧠 Analyzing {company_name} for HIGH DENSITY data...")
    full_context = build_full_context(target_file, company_name)
    
    # 2. THE ATOMIC PROMPT
    prompt = f"""
    You are an M&A Analyst. Do NOT summarize. **EXTRACT ATOMIC DATA.**
    High-quality slides require specific numbers, proper nouns, and locations.
    
    ### INSTRUCTIONS:
    1. **Deconstruct Text:** If the text says "2 factories in Gujarat producing 18k MT", split it into: Value="2", Label="Facilities", Context="Gujarat (18k MT)".
    2. **Fill the Grid:** I need exactly 4 "Key Highlights" for Slide 1, and 4 "Operational Metrics" for Slide 2.
    
    ### REQUIRED JSON STRUCTURE:
    {{
      "slide_1": {{
        "project_name": "Project [CodeName]",
        "sector": "String",
        "header_tagline": "String (e.g. 'Leading Manufacturer of...')",
        
        "business_overview_card": {{
             "main_narrative": "String (2 sentences max)",
             "bullets": ["Detail 1", "Detail 2"]
        }},
        
        "infrastructure_highlights": [ 
             {{ "value": "Big Number (e.g. '2')", "label": "Label (e.g. 'Units')", "subtext": "Context (e.g. 'Gujarat')" }},
             {{ "value": "String", "label": "String", "subtext": "String" }},
             {{ "value": "String", "label": "String", "subtext": "String" }}
        ],
        
        "key_products_grid": [
             {{ "name": "Prod A", "desc": "Short Spec" }},
             {{ "name": "Prod B", "desc": "Short Spec" }},
             {{ "name": "Prod C", "desc": "Short Spec" }},
             {{ "name": "Prod D", "desc": "Short Spec" }}
        ],
        "image_query": "String"
      }},
      
      "slide_2": {{
        "financial_card": {{
             "cagr_value": "18.5%",
             "ebitda_value": "22%",
             "revenue_fy24": "1,150",
             "revenue_fy25": "1,380"
        }},
        "graph_data": {{ "years": ["23", "24", "25"], "revenue": [10, 20, 30] }},
        
        "operational_kpi_grid": [
             {{ "metric": "600+", "label": "Employees", "context": "R&D Focus" }},
             {{ "metric": "45%", "label": "Exports", "context": "US & EU Markets" }},
             {{ "metric": "ISO 9001", "label": "Certified", "context": "Quality Standard" }},
             {{ "metric": "Zero", "label": "Debt", "context": "Net Cash Positive" }}
        ]
      }},
      
      "slide_3": {{
        "thesis_points": [
             {{ "title": "Bold Hook", "detail": "Detailed explanation..." }},
             {{ "title": "Bold Hook", "detail": "Detailed explanation..." }},
             {{ "title": "Bold Hook", "detail": "Detailed explanation..." }}
        ]
      }},
      "citations": ["Source 1", "Source 2"]
    }}

    ### TARGET DATA:
    {full_context}
    """

    print("✨ Sending to Gemini...")
    try:
        response = model.generate_content(prompt)
        data = json.loads(response.text)
        
        # Save
        with open(f"{company_name}_ANALYSIS.json", "w") as f:
            json.dump(data, f, indent=4)
        print(f"✅ Atomic Analysis Saved.")
        return data
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    analyze_company("example_company.md", "Test Company Name")