# Automated Deal Flow & Teaser Generation Pipeline

> **An end-to-end AI pipeline that converts unstructured company data into investment-grade M&A teaser decks.**

This is a deterministic, reproducible pipeline designed to **automate the early-stage investment analysis workflow** typically performed by junior investment banking and private equity teams.

It ingests raw company data (PDFs, Excel models, Markdown briefs), enriches it with targeted public-web intelligence, extracts **high-density, non-marketing investment facts** using a rigorously constrained LLM agent, and programmatically renders:

- a **native, editable PowerPoint teaser deck**
- a **citation audit document** tracing data sources

No screenshots. No slide templates. No manual formatting.

---

## 🔍 Problem Statement

Early-stage M&A analysis suffers from three structural problems:

1. **Unstructured inputs**  
   Company data arrives as PDFs, Excel sheets, one-pagers, and notes.

2. **Low signal-to-noise summaries**  
   Generic AI summaries produce marketing fluff rather than investment facts.

3. **Manual slide production**  
   Analysts spend hours formatting decks instead of thinking.

We solves this by enforcing:
- **data density over prose**
- **strict schemas over free-form text**
- **code-driven slide construction**

---

## 🧠 What This Pipeline Does (High Level)

1. **Ingests private company data**  
   PDFs, Excel files, Markdown, and text files.

2. **Augments missing context via public web search**  
   Focused queries for products, certifications, customers, and financials.

3. **Builds a unified “truth context”**  
   Private + public data fused into a single analysis source.

4. **Runs a highly constrained LLM extraction agent**  
   Outputs *structured JSON only* — no prose.

5. **Renders investment slides programmatically**  
   Business overview, financials, KPIs, and thesis.

6. **Generates a citation audit document**  
   Ensures traceability of claims.

---

## 🏗️ Architecture Overview
```
flowchart TD

    A[Private Data<br/>(PDF · Excel · MD · TXT)] --> B[Ingestion Layer(ingest.py)]

    B --> C[Public Web Search<br/>(Tavily)]
    C --> D[Unified Context]

    B --> D
    D --> E[LLM Extraction Agent<br/>(analyze.py)]

    E --> F[Structured JSON]

    F --> G[PPT Engine<br/>(ppt_engine.py)]
    F --> H[Citation Engine<br/>(generate_citations.py)]

    G --> I[Teaser Deck]
    H --> J[Source Audit Document]

```

---

## 📁 Project Structure

```
.
├── analyze.py # LLM agent & extraction logic
├── ingest.py # Data ingestion + web enrichment
├── ppt_engine.py # Programmatic PowerPoint renderer
├── generate_citations.py # Citation audit document generator
├── main.py # CLI entrypoint & pipeline orchestration
├── check_models.py # Gemini model availability checker
├── utils.py # Image download helper (Pexels)
├── requirements.txt # Python dependencies
├── examples/ # INPUT: files or data-pack folders
└── Final_Submissions/ # OUTPUT: PPT + citations
```


---

## 🔬 Pipeline Components (Deep Dive)

### 1️⃣ Ingestion Layer — `ingest.py`

**Purpose:**  
Convert heterogeneous inputs into a single, analyzable text corpus.

**Supported Inputs**
- `.pdf` → parsed via **LlamaParse** (handles tables & scanned docs)
- `.xlsx / .xls` → flattened using **pandas**
- `.md / .txt` → read directly
- Folder-based “data packs” (multiple files per company)

**Public Web Augmentation**
- Uses **Tavily Search**
- Executes targeted queries for:
  - product capabilities
  - certifications & awards
  - revenue / geography indicators

**Key Design Choice**
> The pipeline never assumes private data is complete.  
> Public data is *always* used to fill analytical gaps.

All extracted text is saved to: {CompanyName}_FULL_CONTEXT.txt
for full transparency and debugging.

---

### 2️⃣ Extraction Agent — `analyze.py`

This is the **core intelligence layer**.

**Model**
- Google Gemini (`gemini-2.5-flash` or compatible)
- Chosen for:
  - very large context windows
  - reliable JSON compliance

**Critical Constraints Enforced**
- ❌ No marketing language
- ❌ No vague adjectives
- ❌ No “N/A”
- ✅ Numbers preferred over words
- ✅ Explicit inference with `(est.)` tagging
- ✅ Slide-ready sentences (≤20 words)

**Output**
A rigid, predefined JSON schema covering:
- business overview
- infrastructure metrics
- product capabilities
- applications & certifications
- financial indicators
- investment thesis

Saved as: {CompanyName}_ANALYSIS.json


This file is the **single source of truth** for all downstream steps.

---

### 3️⃣ Presentation Engine — `ppt_engine.py`

**Purpose:**  
Render investment-grade slides using **code, not templates**.

**Key Characteristics**
- Uses `python-pptx`
- Draws:
  - vector shapes
  - text boxes
  - metric tiles
  - native charts
- All text remains editable in PowerPoint

**Slides Generated**
1. **Business Overview**
   - company profile
   - infrastructure highlights
   - product & capability grid

2. **Financial Performance**
   - revenue & margin cards
   - revenue growth chart
   - operational KPIs

3. **Investment Thesis**
   - evidence-backed investment hooks

4. **Legal Disclaimer**

**Design Philosophy**
- No fragile XML hacks
- No version-specific PowerPoint features
- Clean, conservative “consulting-grade” layout

---

### 4️⃣ Citation Engine — `generate_citations.py`

**Purpose:**  
Create an audit trail for extracted insights.

- Reads the `citations` field from analysis JSON
- Generates a `.docx` file listing data sources
- Intended for:
  - internal review
  - compliance checks
  - analyst validation

Output: Final_Submissions/{CompanyName}_Citations.docx


---

### 5️⃣ Orchestration Layer — `main.py`

This is the **CLI controller**.

**Capabilities**
- Detects whether input is:
  - a single file
  - a multi-file data pack folder
- Automatically derives company name
- Runs:
  1. analysis
  2. slide generation
  3. citation generation

Users interact via a simple numeric menu.

---

## 🛠️ Installation & Setup

### Prerequisites
- Python **3.10+**
- API keys for:
  - Google Gemini
  - Tavily Search
  - LlamaParse
  - Pexels (optional, for images)

---

### 1️⃣ Clone Repository

```bash
git clone https://github.com/neepun06/AI-ML-GC-RND.git
cd AI-ML-GC-RND
```

### 2️⃣ Create Virtual Environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

### 3️⃣ Install Dependencies
```
pip install -r requirements.txt
```

### 4️⃣ Configure Environment Variables

Create a .env file in the project root:
```
GEMINI_API_KEY=your_gemini_key
TAVILY_API_KEY=your_tavily_key
LLAMA_CLOUD_API_KEY=your_llama_key
PEXELS_API_KEY=your_pexels_key   
```

## ▶️ How to Run
### Step 1: Prepare Input
Option A — Single File
```
examples/
 └── Company-OnePager.md
```

Option B — Data Pack Folder
```
examples/
 └── Company_Data/
     ├── annual_report.pdf
     ├── financials.xlsx
     └── notes.md
```

### Step 2: Run the pipeline
```
python main.py
```

### Step 3: Select input
```
--- GENERATOR ---
Files and Data Pack Folders found:
[1] [FOLDER] Company_Data
[2] [FILE]   Company-OnePager.md
```

Select Item #: 1

### Step 4: Retrieve Outputs
```
Final_Submissions/
 ├── Company_Teaser_Atomic.pptx
 └── Company_Citations.docx
```

## ⚙️ Design Decisions & Trade-offs
- Strict JSON schema was chosen over flexibility to guarantee slide safety.
- Estimation over N/A reflects real analyst behavior.
- Programmatic slides avoid template lock-in.
- Public web enrichment reduces dependency on perfect private data.
- Fail-soft design ensures partial data never breaks the pipeline.

## 🔐 Security & Data Handling
- API keys are excluded via .gitignore
- No data is transmitted except to configured APIs
- Generated outputs are local only

## 📄 License
Private project / hackathon submission.
Not intended for public commercial redistribution.

## 📌 Final Note
This is a deterministic analytical system that treats LLMs as controlled extraction engines, not creative writers.
This design choice is intentional.












