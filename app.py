import os
import pdfplumber
import re
import html
import json
import logging
import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
import torch

# -------------------------
# Silence PDF warnings
# -------------------------
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# -------------------------
# Helper: Clean OCR / Extracted HTML
# -------------------------
def clean_extracted_html(escaped_html: str):
    s = html.unescape(escaped_html)
    replacements = [
        (r'\bL c\b', 'Law'),
        (r'\bL c\w*\b', 'Law'),
        (r'\bontract\b', 'contract'),
        (r'\bconntain(ed)?\b', 'contain'),
        (r'1872a\b', '1872'),
        (r'\bform a shop\b', 'from a shop'),
        (r'\bride a bus\b', 'rides a bus'),
        (r'\b\.\s*([A-Za-z])\s*</p>', r'.</p><p>\1'),
    ]
    for pat, repl in replacements:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    s = re.sub(r'<p>\s*[A-Za-z]\s*</p>', '', s)
    s = re.sub(r'\b(?:[A-Za-z]\s+){2,5}\b', lambda m: m.group(0).replace(' ', ''), s)
    s = re.sub(r'\s+\n', '\n', s)
    s = re.sub(r'\s{2,}', ' ', s)
    s = re.sub(r'\s+([,.;:])', r'\1', s)
    s = re.sub(r'(\w)\s+(\')\s+(\w)', r"\1'\3", s)
    s = re.sub(r'\s*</p>\s*<p>\s*', '</p>\n<p>', s)
    return s

# -------------------------
# PDF Extraction as HTML
# -------------------------
def extract_pdf_as_html(pdf_path):
    html_content = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            table_lines = set()
            for table in tables:
                for row in table:
                    table_lines.add(" ".join([cell for cell in row if cell]))

            text_lines = page.extract_text().splitlines() if page.extract_text() else []
            page_html = ""

            for line in text_lines:
                line = line.strip()
                if not line or line in table_lines:
                    continue
                if line.isupper() and len(line.split()) <= 10:
                    page_html += f"<h3>{line}</h3>\n"
                elif line.startswith(("-", "•")):
                    page_html += f"<li>{line[1:].strip()}</li>\n"
                else:
                    page_html += f"<p>{line}</p>\n"

            # Add tables
            for table in tables:
                table_html = "<table border='1' style='border-collapse: collapse; width: 100%;'>\n"
                for row in table:
                    table_html += "<tr>"
                    for cell in row:
                        table_html += f"<td>{cell if cell else ''}</td>"
                    table_html += "</tr>\n"
                table_html += "</table>\n"
                page_html += table_html

            html_content += page_html + "<hr>\n"

    return clean_extracted_html(html_content)

# -------------------------
# Extract sections by keywords
# -------------------------
def extract_sections_by_keywords(text, keywords, window=300):
    sections = {}
    lower_text = text.lower()
    words = text.split()
    for kw in keywords:
        kw_lower = kw.lower()
        idx = lower_text.find(kw_lower)
        if idx != -1:
            word_index = len(text[:idx].split())
            start = max(0, word_index - int(window / 4))
            end = min(len(words), word_index + window)
            sections[kw] = " ".join(words[start:end])
        else:
            sections[kw] = "❌ Keyword not found in PDF."
    return sections

# -------------------------
# FastAPI setup
# -------------------------
app = FastAPI(title="PDF Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class Query(BaseModel):
    query: str

# -------------------------
# PDF files and keywords
# -------------------------
pdf_keywords = [
    {
        "pdf": "pdf/extended_sample_table.pdf",
        "keywords": ["Extended Sample PDF with Table"]
    },
    {
        "pdf": "pdf/Law of Contract-I_removed.pdf",
        "keywords": [
            "Law of contract",
            "SCHEME OF THE ACT",
            "PRESENT FORM OF INDIAN CONTRACT ACT",
            "DEFINITIONS OF CONTRACT",
            "DISTINCTION BETWEEN CONTRACT & AGREEMENT",
            "Section 10",
            "Proper Offer and Acceptance:",
            "Intention to Create Legal Relationship",
            "Capacity of Parties",
            "Lawful Consideration",
            "Lawful Object",
            "Free Consent",
            "On the basis of creation or formation",
            "On the basis of validity or enforceability",
            "On the basis of execution or performance",
            "On the basis of liability",
            "BETWEEN VOID AGREEMENT AND VOID CONTRACT",
            "BETWEEN VOID AGREEMENT AND VOIDABLE CONTRACT",
            "BETWEEN VOID CONTRACT & VOIDABLE CONTRACT",
            "BETWEEN VOID AND ILLEGAL AGREEMENT"
        ]
    }
]

# -------------------------
# Load PDF content
# -------------------------
all_chunks = []
chunk_mapping = []

for item in pdf_keywords:
    if not os.path.exists(item["pdf"]):
        print(f"⚠️ Missing file: {item['pdf']}")
        continue
    pdf_content = extract_pdf_as_html(item["pdf"])
    keyword_sections = extract_sections_by_keywords(pdf_content, item["keywords"])
    for kw, section in keyword_sections.items():
        all_chunks.append(section)
        chunk_mapping.append(kw)

# Save chunks to JSON
os.makedirs("data", exist_ok=True)
with open("data/pdf_chunks.json", "w", encoding="utf-8") as f:
    json.dump(
        [{"keyword": k, "chunk": c} for k, c in zip(chunk_mapping, all_chunks)],
        f, ensure_ascii=False, indent=4
    )
print("✅ PDF sections saved to data/pdf_chunks.json")

# -------------------------
# Lazy load SentenceTransformer model
# -------------------------
model = None
emb_chunks = None

def get_model():
    global model, emb_chunks
    if model is None:
        from sentence_transformers import SentenceTransformer, util
        print("⏳ Loading SentenceTransformer model...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb_chunks = model.encode(all_chunks, convert_to_tensor=True)
        print("✅ Model loaded successfully!")
    return model, emb_chunks

# -------------------------
# Chat endpoint
# -------------------------
# -------------------------
# Chat endpoint
# -------------------------

@app.post("/chat")
def chat(query: Query):
    from sentence_transformers import util
    user_q = query.query.strip()
    if not user_q:
        return {"answer": "Please type something!", "confidence": 1.0}

    model, emb_chunks = get_model()
    user_emb = model.encode([user_q], convert_to_tensor=True)
    similarity = util.cos_sim(user_emb, emb_chunks.clone()).squeeze(0)
    sorted_idx = torch.argsort(similarity, descending=True)

    top_matches = []
    for idx in sorted_idx[:3]:
        top_matches.append({
            "keyword": chunk_mapping[idx],
            "answer": all_chunks[idx],
            "confidence": float(similarity[idx])
        })

    return {"top_matches": top_matches}

# -------------------------
# Health checks
# -------------------------
@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.get("/")
def root():
    return {"status": "running", "message": "PDF Chat API is live!"}

# Serve static files separately (prevents route collision)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# -------------------------
# Main entry point
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render injects PORT automatically
    uvicorn.run("app:app", host="0.0.0.0", port=port)
