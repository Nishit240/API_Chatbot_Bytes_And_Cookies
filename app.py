import os
import re
import html
import logging
import warnings
import requests
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------------------------
# Setup
# -------------------------
warnings.filterwarnings("ignore")
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="📘 Smart PDF Chatbot", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Config
# -------------------------
PDF_KEYWORD_DATA = {
    "https://renaicon.in/storage/syllabus/images/A8YRAiNXEIX05H33IQbtVVyUd3HKCO9LjQ8FJBLG.pdf": {
        "keywords": [
            "Fundamentals of Contract Laws",
            "Law of Contract",
            "INDIAN CONTRACT ACT, 1872",
            "DISTINCTION BETWEEN CONTRACT & AGREEMENT",
            "Offer and Acceptance",
            "ESSENTIAL ELEMENTS OF A VALID CONTRACT",
            "Intention to Create Legal Relationship",
            "CLASSIFICATION OF CONTRACTS",
            "Void and Voidable Contracts"
        ]
    },
    # Added Extended Sample link
    # "https://extended-sample-table.tiiny.site": {
    #     "keywords": [
    #         "Extended Sample PDF with Table",
    #         "Table Example",
    #         "Column Structure",
    #         "Row Details",
    #         "Data Representation",
    #         "Sample Chart"
    #     ]
    # }
}

PDF_CACHE: Dict[str, Dict[str, Any]] = {}

# -------------------------
# PDF Extraction
# -------------------------
def clean_extracted_html(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("", "→").replace("•", "→")
    s = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", s)
    s = re.sub(r"([a-z])\s*\n\s*([A-Z])", r"\1. \2", s)
    s = re.sub(r"\bL\s*aw\b", "Law", s, flags=re.I)
    s = re.sub(r"\b(ontract|ontrac|ontra)\b", "contract", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s)
    s = s.replace("\n", "<br>")
    return s.strip()


def extract_pdf_as_html_from_url(url: str) -> str:
    import pdfplumber
    from io import BytesIO
    if url in PDF_CACHE:
        return PDF_CACHE[url]["html"]

    logger.info(f"📥 Fetching PDF or HTML source: {url}")
    resp = requests.get(url, timeout=25)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "pdf" not in content_type:
        logger.warning("⚠️ Non-PDF content detected, treating as HTML text.")
        PDF_CACHE[url] = {"html": html.escape(resp.text)}
        return PDF_CACHE[url]["html"]

    pdf_data = BytesIO(resp.content)
    html_content = ""
    with pdfplumber.open(pdf_data) as pdf:
        # ✅ Skip first page
        for page in pdf.pages[1:]:
            tables = page.extract_tables() or []
            text_lines = page.extract_text().splitlines() if page.extract_text() else []
            page_html = ""

            for line in text_lines:
                line = line.strip()
                if not line:
                    continue
                if re.match(r"^[A-Z][A-Z\s&\-]{2,}$", line) and len(line.split()) <= 10:
                    page_html += f"<h3>{html.escape(line.title())}</h3>\n"
                elif re.match(r"^(\s*[-•→]|^\d+\.)", line):
                    page_html += f"<li>{html.escape(line.lstrip('-•→').strip())}</li>\n"
                else:
                    page_html += f"<p>{html.escape(line)}</p>\n"

            for t in tables:
                table_html = "<table border='1' style='border-collapse:collapse;width:100%;margin:10px 0;'>"
                for row in t:
                    table_html += "<tr>" + "".join(
                        f"<td style='padding:6px;border:1px solid #999;font-family:Arial;'>{html.escape(str(cell or ''))}</td>"
                        for cell in row
                    ) + "</tr>"
                table_html += "</table>\n"
                page_html += table_html

            html_content += page_html + "<hr>\n"

    cleaned = clean_extracted_html(html_content)
    PDF_CACHE[url] = {"html": cleaned}
    return cleaned

# -------------------------
# Models
# -------------------------
class QueryRequest(BaseModel):
    query: str
    pdf_url: str

# -------------------------
# Extract section after heading
# -------------------------
def extract_section_after_heading(html_text: str, heading: str, word_limit: int = 400):
    if not html_text or not heading:
        return None

    merged = re.sub(r"\s{2,}", " ", html_text)
    head_tokens = re.escape(heading.strip()).replace("\\ ", r"\s+")
    head_re = re.compile(rf"(?i){head_tokens}")

    m = head_re.search(merged)
    if not m:
        parts = heading.strip().split()
        if len(parts) >= 2:
            partial = re.escape(" ".join(parts[:2])).replace("\\ ", r"\s+")
            m = re.search(rf"(?i){partial}", merged)
    if not m:
        return None

    start = m.end()
    region = merged[start:start + 8000]

    table_match = re.search(r"(<table\b.*?>.*?</table>)", region, flags=re.I | re.S)
    if table_match:
        table_html = table_match.group(1)
        if "style=" not in table_html:
            table_html = table_html.replace(
                "<table",
                "<table border='1' style='border-collapse:collapse;width:100%;margin:10px 0;'>",
                1
            )
        return f"<div class='formatted-answer'><h4>{heading}</h4>{table_html}</div>"

    text_only = re.sub(r"<[^>]+>", " ", region)
    text_only = re.sub(r"\s{2,}", " ", text_only).strip()
    words = text_only.split()
    snippet = " ".join(words[:word_limit])
    if not snippet:
        return None

    snippet = re.sub(r'\s*([.?!])\s*', r'\1 ', snippet)
    snippet = re.sub(r'([.?!])\s+(?=[A-Z])', r'\1<br><br>', snippet)
    snippet = snippet.strip()

    snippet = "<p>" + snippet.replace("\n", "<br>") + "</p>"
    return f"<div class='formatted-answer'><h4>{heading}</h4>{snippet}</div>"

# -------------------------
# Formatting
# -------------------------
def format_for_readability(raw_text: str) -> str:
    if not raw_text or raw_text.startswith("❌"):
        return raw_text

    if re.search(r"</?(table|tr|td|th)[\s>]", raw_text, flags=re.I):
        formatted = re.sub(r'([.?!])\s+(?=[A-Z])', r'\1<br><br>', raw_text)
        return f"<div class='formatted-answer'>{formatted}</div>"

    text = html.escape(raw_text)
    text = text.replace("->", "→").replace("➢", "→").replace("", "→")
    text = re.sub(r'\s{2,}', ' ', text)

    bold_words = [
        "Section", "Definition", "Case", "Elements", "Types", "Basis",
        "Example", "Law", "Contract", "Agreement", "Offer", "Acceptance",
        "Consideration", "Enforceability", "Void", "Valid", "Essential",
        "Consent", "Object", "Proposal", "Promise", "Obligation", "Remedies",
        "Specific", "Relief", "Act"
    ]
    for word in bold_words:
        text = re.sub(rf"\b({word}s?)\b", r"<b>\1</b>", text, flags=re.I)

    text = re.sub(r"(UNIT\s+[IVXLC]+:?)", r"<h4>\1</h4>", text, flags=re.I)

    parts = re.split(r"(<h4>.*?</h4>)", text)
    formatted = []

    for part in parts:
        if not part.strip():
            continue

        if part.startswith("<h4>"):
            formatted.append(part)
            continue

        lines = re.split(r"(?=→)", part)
        list_items = []
        normal_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("→"):
                clean_item = line.lstrip("→").strip()
                list_items.append(f"<li>{clean_item}</li>")
            else:
                line = re.sub(r'([.?!])\s+(?=[A-Z])', r'\1<br><br>', line)
                normal_lines.append(f"<p>{line}</p>")

        if list_items:
            formatted.append("<ul>" + "".join(list_items) + "</ul>")
        formatted.extend(normal_lines)

    final_html = "\n".join(formatted)
    return f"<div class='formatted-answer'>{final_html}</div>"

# -------------------------
# /chat Endpoint
# -------------------------
@app.post("/chat")
def chat_endpoint(req: QueryRequest):
    try:
        pdf_url = req.pdf_url.strip()
        query = req.query.strip()

        if pdf_url not in PDF_KEYWORD_DATA:
            return JSONResponse(
                content={"error": f"PDF URL not authorized: {pdf_url}"}, status_code=403
            )

        html_text = extract_pdf_as_html_from_url(pdf_url)
        keywords = PDF_KEYWORD_DATA[pdf_url]["keywords"]

        vectorizer = TfidfVectorizer(stop_words="english")
        corpus = [query] + keywords
        vectors = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

        top_idxs = sims.argsort()[::-1][:3]
        top_matches = []

        for idx in top_idxs:
            kw = keywords[idx]
            conf = float(sims[idx])
            section_text = extract_section_after_heading(html_text, kw)

            if not section_text or len(section_text.strip()) < 20:
                section_text = "❌ No relevant content found in the PDF."

            formatted = format_for_readability(section_text)

            top_matches.append({
                "keyword": kw,
                "answer": formatted,
                "confidence": round(conf, 4)
            })

        top_matches = sorted(top_matches, key=lambda x: x["confidence"], reverse=True)
        response_data = {"pdf_url": pdf_url, "top_matches": top_matches}
        return JSONResponse(content=response_data)

    except Exception as e:
        logger.exception("Error in chat endpoint")
        return JSONResponse(
            content={"error": f"Internal Server Error: {str(e)}"},
            status_code=500
        )


@app.get("/")
def root():
    return {"message": "✅ Smart Legal PDF Chatbot API running!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


# ---------------------
# Main entry point (Render)
# -------------------------
# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.environ.get("PORT", 8000))  # Render injects PORT automatically
#     uvicorn.run("app:app", host="0.0.0.0", port=port)
