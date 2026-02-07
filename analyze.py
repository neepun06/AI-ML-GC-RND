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

# UPDATE MODEL NAME IF NEEDED
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config=generation_config,
)

def analyze_company(target_file, company_name):
    print(f"🧠 Analyzing {company_name} for HIGH DENSITY data...")
    full_context = build_full_context(target_file, company_name)
   
    # ============================
    # IMPROVED BANKER-STYLE PROMPT
    # ============================
    prompt = f"""
You are a Senior Investment Banking Associate preparing an M&A teaser.

Your job is NOT summarization.
Your job is to extract HIGH-DENSITY INVESTMENT DATA.

The output feeds directly into professional investment slides.

---------------------------
CRITICAL WRITING RULES
---------------------------

1. NEVER use marketing language:
   Forbidden phrases include:
   "leading", "innovative", "renowned", "strong presence",
   "trusted", "customer-centric", "cutting-edge".

2. Prefer NUMBERS over adjectives.

BAD:
"Strong global presence."

GOOD:
"Operations across India, USA and UAE serving enterprise clients."

3. Every bullet or statement should contain:
   • numbers
   • scale
   • capabilities
   • locations
   • certifications
   • or customer footprint

4. Sentences must be slide-ready.
   Maximum 20 words per bullet.

5. Avoid fluff. Avoid generic words.

6. Use consulting / banker tone.

7. NEVER output N/A.
   If missing:
      • infer from context
      • estimate logically
      • append "(est.)" when estimated.

Example:
"$120M (est.)"

8. Prefer operational facts:
   capacity, customers, exports, plants, employees,
   certifications, market presence, revenue, margins.

9. Keep descriptions concise and factual.

10. Include technical tools ONLY when they demonstrate delivery capability.
    Do NOT dump tool lists.

BAD:
"Uses Kafka, Spark, Hadoop, Airflow, Hive."

GOOD:
"Builds real-time analytics pipelines using Kafka and Spark for enterprise clients."

Mention tools only when they prove capability or differentiation.

---------------------------
EXTRACTION LOGIC
---------------------------

• Extract end-use industries as "applications".
Examples: Bakery, Oil & Gas, Mining, Textile, Pharma, FMCG.

• Extract certifications and regulatory approvals separately.
Examples: ISO certifications, FDA approvals, FSSAI, FSSC, CE, Kosher, etc.

• Extract key enterprise or global customers if mentioned.
Examples: Nestle, Danone, Shell, Tata, Unilever, etc.

Limit each list to max 6 items.
Prefer widely recognized names.

• Split compound statements into atomic metrics.

Example:
"2 factories in Gujarat producing 18k MT annually"

becomes:
Value = 2
Label = Facilities
Context = Gujarat – 18k MT capacity

• Always provide complete grids.

If data insufficient, infer reasonable industry proxies.

---------------------------
REQUIRED JSON STRUCTURE
---------------------------

{{
  "slide_1": {{
    "project_name": "Project [CodeName]",
    "sector": "String",
    "header_tagline": "Investment-grade positioning sentence",

    "business_overview_card": {{
         "main_narrative": "Two factual sentences max",
         "bullets": ["Bullet 1", "Bullet 2"]
    }},

    "infrastructure_highlights": [
         {{ "value": "String", "label": "String", "subtext": "String" }},
         {{ "value": "String", "label": "String", "subtext": "String" }},
         {{ "value": "String", "label": "String", "subtext": "String" }}
    ],

    "key_products_grid": [
         {{ "name": "Prod A", "desc": "Short factual spec" }},
         {{ "name": "Prod B", "desc": "Short factual spec" }},
         {{ "name": "Prod C", "desc": "Short factual spec" }},
         {{ "name": "Prod D", "desc": "Short factual spec" }}
    ],

    "applications": [
         "Industry A",
         "Industry B"
    ],

    "certifications": [
         "Certification A",
         "Certification B"
    ],

    "key_customers": [
         "Customer A",
         "Customer B"
    ],

    "image_query": "Industry-relevant facility or product"
  }},

  "slide_2": {{
    "financial_card": {{
         "cagr_value": "Revenue CAGR %",
         "ebitda_value": "EBITDA margin %",
         "revenue_fy24": "Revenue value",
         "revenue_fy25": "Projected revenue"
    }},

    "graph_data": {{
        "years": ["23", "24", "25"],
        "revenue": [10, 20, 30]
    }},

    "operational_kpi_grid": [
         {{ "metric": "Value", "label": "Metric Name", "context": "Short context" }},
         {{ "metric": "Value", "label": "Metric Name", "context": "Short context" }},
         {{ "metric": "Value", "label": "Metric Name", "context": "Short context" }},
         {{ "metric": "Value", "label": "Metric Name", "context": "Short context" }}
    ]
  }},

  "slide_3": {{
    "thesis_points": [
         {{ "title": "Investment Hook", "detail": "Evidence-backed explanation" }},
         {{ "title": "Investment Hook", "detail": "Evidence-backed explanation" }},
         {{ "title": "Investment Hook", "detail": "Evidence-backed explanation" }}
    ]
  }},

  "citations": ["Source 1", "Source 2"]
}}

---------------------------
TARGET DATA
---------------------------

{full_context}
"""

    print("✨ Sending to Gemini...")
    try:
        response = model.generate_content(prompt)
        data = json.loads(response.text)
       
        with open(f"{company_name}_ANALYSIS.json", "w") as f:
            json.dump(data, f, indent=4)

        print(f"✅ Atomic Analysis Saved.")
        return data

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    analyze_company("example_company.md", "Test Company Name")