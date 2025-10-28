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
from sklearn.metrics.pairwise import cosine_similarity
import html, re

# -------------------------
# Silence PDF warnings
# -------------------------
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# -------------------------
# Helper: Clean extracted text
# -------------------------
def clean_extracted_html(escaped_html: str):
    """Advanced cleaner specifically for messy law PDF-to-HTML extraction."""

    s = html.unescape(escaped_html)

    # --- 1️⃣ Remove useless single-letter or junk <p> tags ---
    s = re.sub(r'<p>\s*[a-zA-Z]\s*</p>', '', s)
    s = re.sub(r'<p>\s*\d+\s*</p>', '', s)  # remove isolated page numbers
    s = re.sub(r'<p>\s*(n|e|l|a|s|c|g|i|o|w)\s*</p>', '', s, flags=re.IGNORECASE)

    # --- 2️⃣ Fix words broken across tags like "L c" → "Law", "ontract" → "contract" ---
    s = re.sub(r'\bL\s*c\b', 'Law', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(ontract|ontrac|ontr|ontra)\b', 'contract', s, flags=re.IGNORECASE)
    s = re.sub(r'\bconntain(ed)?\b', 'contain', s, flags=re.IGNORECASE)
    s = re.sub(r'1872a\b', '1872', s)
    s = re.sub(r'\bform a shop\b', 'from a shop', s)
    s = re.sub(r'\bride a bus\b', 'rides a bus', s)
    s = re.sub(r'\brelawtes\b', 'relates', s, flags=re.IGNORECASE)
    s = re.sub(r'\bindcian\b', 'Indian', s, flags=re.IGNORECASE)
    s = re.sub(r'\bcontractse\b', 'contracts', s, flags=re.IGNORECASE)
    s = re.sub(r'\btheere\b', 'there', s, flags=re.IGNORECASE)
    s = re.sub(r'\bcommunicalted\b', 'communicated', s, flags=re.IGNORECASE)

    # --- 3️⃣ Join broken lines and normalize whitespace ---
    s = re.sub(r'\s*\n\s*', ' ', s)  # join newlines
    s = re.sub(r'\s{2,}', ' ', s)    # multiple spaces to one
    s = re.sub(r'\s+([.,;:!?])', r'\1', s)
    s = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', s)

    # --- 4️⃣ Normalize HTML paragraph spacing ---
    s = re.sub(r'\s*</p>\s*<p>\s*', '</p>\n<p>', s)
    s = re.sub(r'<p>\s*</p>', '', s)
    s = re.sub(r'<h3>\s*</h3>', '', s)

    # --- 5️⃣ Standardize section headings (Law PDFs often have misaligned H3 tags) ---
    s = re.sub(r'<h3>\s*([A-Z][A-Z ]{2,})\s*</h3>', lambda m: f"<h3>{m.group(1).title()}</h3>", s)

    # --- 6️⃣ Fix mid-word breaks like “agreemenet” → “agreement” ---
    s = re.sub(r'\bagreemenet\b', 'agreement', s)
    s = re.sub(r'\bforbCearances?\b', 'forbearance', s, flags=re.IGNORECASE)
    s = re.sub(r'\bbindling\b', 'binding', s, flags=re.IGNORECASE)
    s = re.sub(r'\bconaditions\b', 'conditions', s, flags=re.IGNORECASE)
    s = re.sub(r'\bwghom\b', 'whom', s, flags=re.IGNORECASE)

    # --- 7️⃣ Add spacing between headings and text for readability ---
    s = re.sub(r'(</h3>)(\s*<p>)', r'\1\n\2', s)
    s = re.sub(r'(</p>)(\s*<h3>)', r'\1\n\2', s)

    # --- 8️⃣ Final cleanup ---
    s = s.strip()
    s = re.sub(r'\s{2,}', ' ', s)
    return s


# -------------------------
# PDF Extraction as HTML
# -------------------------
def extract_pdf_as_html(pdf_path):
    html_content = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_lines = page.extract_text().splitlines() if page.extract_text() else []
            page_html = ""
            for line in text_lines:
                line = line.strip()
                if not line:
                    continue
                if line.isupper() and len(line.split()) <= 10:
                    page_html += f"<h3>{line}</h3>\n"
                elif line.startswith(("-", "•")):
                    page_html += f"<li>{line[1:].strip()}</li>\n"
                else:
                    page_html += f"<p>{line}</p>\n"
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
app = FastAPI(title="PDF Chat API (Local Test)", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class Query(BaseModel):
    query: str

# -------------------------
# PDF and Keywords
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
            "Proper Offer and Acceptance:"
        ]
    }
]

# pdf_keywords = [
#     {
#         "pdf": "pdf/Law of Contract-I_removed.pdf",
#         "keywords": [
#             "Law of contract",
#             "SCHEME OF THE ACT",
#             "PRESENT FORM OF INDIAN CONTRACT ACT",
#             "DEFINITIONS OF CONTRACT",
#             "DISTINCTION BETWEEN CONTRACT & AGREEMENT",
#             "Section 10",
#             "Proper Offer and Acceptance:"
#             # "Intention to Create Legal Relationship",
#             # "Capacity of Parties",
#             # "Lawful Consideration",
#             # "Lawful Object",
#             # "Free Consent",
#             # "On the basis of creation or formation",
#             # "On the basis of validity or enforceability",
#             # "On the basis of execution or performance",
#             # "On the basis of liability",
#             # "BETWEEN VOID AGREEMENT AND VOID CONTRACT",
#             # "BETWEEN VOID AGREEMENT AND VOIDABLE CONTRACT",
#             # "BETWEEN VOID CONTRACT & VOIDABLE CONTRACT",
#             # "BETWEEN VOID AND ILLEGAL AGREEMENT"
#         ]
#     }
# ]

# -------------------------
# Load and Process PDFs
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

os.makedirs("data", exist_ok=True)
with open("data/pdf_chunks.json", "w", encoding="utf-8") as f:
    json.dump(
        [{"keyword": k, "chunk": c} for k, c in zip(chunk_mapping, all_chunks)],
        f, ensure_ascii=False, indent=4
    )

print("✅ PDF sections saved to data/pdf_chunks.json")

# -------------------------
# TF-IDF setup
# -------------------------
vectorizer = TfidfVectorizer(stop_words="english")
tfidf_matrix = vectorizer.fit_transform(all_chunks)

# -------------------------
# Endpoints
# -------------------------
@app.post("/chat")
def chat(query: Query):
    user_q = query.query.strip()
    if not user_q:
        return {"answer": "Please type something!"}

    user_vec = vectorizer.transform([user_q])
    cosine_sim = cosine_similarity(user_vec, tfidf_matrix).flatten()
    top_idx = cosine_sim.argsort()[::-1][:3]

    top_matches = []
    for idx in top_idx:
        top_matches.append({
            "keyword": chunk_mapping[idx],
            "answer": all_chunks[idx],
            "confidence": float(cosine_sim[idx])
        })
    return {"top_matches": top_matches}
 
@app.get("/")
def root():
    return {"status": "running", "message": " 🗃️ PDF Chat API is running locally"}

# Static files (optional UI)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


# -------------------------
# Main entry point
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render injects PORT automatically
    uvicorn.run("app:app", host="0.0.0.0", port=port)