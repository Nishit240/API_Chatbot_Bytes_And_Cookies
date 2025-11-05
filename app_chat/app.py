import os, re, html, time, logging, warnings, requests, sys
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rapidfuzz import fuzz, process

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(__file__))
app = FastAPI(title="🧠 Structured PDF Chatbot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PDF_CACHE: Dict[str, str] = {}  # key = pdf_name, value = html content
CACHE_DIR = os.path.join(os.getcwd(), "app_preprocess", "pdf_cache")


# -------------------------
# Helpers
# -------------------------
def extract_pdf_as_html(pdf_name: str) -> str:
    cache_path = os.path.join(CACHE_DIR, pdf_name.replace(".pdf", ".html"))
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"❌ Cached HTML not found for {pdf_name}")

    if pdf_name in PDF_CACHE:
        return PDF_CACHE[pdf_name]

    with open(cache_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    PDF_CACHE[pdf_name] = html_content
    return html_content


def extract_section_after_heading(html_text: str, heading: str, word_limit: int = 400):
    if not html_text or not heading:
        return None
    heading_norm = heading.strip()

    header_re = re.compile(r"(<h[1-6][^>]*>.*?</h[1-6]>)", re.I | re.S)
    headers = []
    for m in header_re.finditer(html_text):
        headers.append({
            "start": m.start(),
            "title": re.sub(r"<[^>]+>", "", m.group(0)).strip()
        })

    if headers:
        for i, h in enumerate(headers):
            start = h["start"]
            end = headers[i + 1]["start"] if i + 1 < len(headers) else len(html_text)
            if h["title"].lower() == heading_norm.lower():
                return html_text[start:end]

    # fallback: approximate snippet near heading
    m = re.search(rf"(?i){re.escape(heading_norm)}", html_text)
    if not m:
        return None
    snippet = html_text[m.start(): m.start() + 8000]
    snippet = re.sub(r"<[^>]+>", " ", snippet)
    snippet = " ".join(snippet.split()[:word_limit])
    return f"<div class='formatted-answer'><h4>{heading}</h4><p>{snippet}</p></div>"


def format_for_readability(raw_html: str) -> str:
    if not raw_html:
        return "❌ No relevant section found."
    text = raw_html.replace("->", "→").replace("➢", "→")
    text = re.sub(r"([.?!])\s+(?=[A-Z])", r"\1<br><br>", text)
    return f"<div class='formatted-answer'>{text}</div>"


# -------------------------
# API Model
# -------------------------
class ChatRequest(BaseModel):
    url: str  # returns pdf_name, keywords, question


# -------------------------
# Chat Endpoint
# -------------------------
@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    start_time = time.time()
    try:
        # Step 1 — fetch request data
        resp = requests.get(req.url.strip(), timeout=10)
        if resp.status_code != 200:
            return JSONResponse(content={"error": "Failed to fetch data"}, status_code=502)
        data = resp.json()

        pdf_name = data.get("pdf_name")
        keywords = data.get("keywords", [])
        question = data.get("question", "").strip()

        if not pdf_name or not keywords or not question:
            return JSONResponse(content={"error": "Missing required fields"}, status_code=400)

        # Step 2 — load structured HTML from cache
        html_text = extract_pdf_as_html(pdf_name)

        # Step 3 — fuzzy match best 3 keywords
        matches = process.extract(question, keywords, scorer=fuzz.token_set_ratio, limit=3)

        results = []
        for match, score, _ in matches:
            section_html = extract_section_after_heading(html_text, match)
            formatted = format_for_readability(section_html)
            results.append({
                "keyword": match,
                "confidence": round(score / 100.0, 3),
                "answer": formatted
            })

        elapsed = round(time.time() - start_time, 2)
        return {
            "pdf_name": pdf_name,
            "question": question,
            "response_time_sec": elapsed,
            "top_matches": results
        }

    except Exception as e:
        logger.exception("Error in /chat")
        return JSONResponse(content={"error": f"Internal error: {str(e)}"}, status_code=500)

@app.get("/")
def root():
    return {"message": "✅ Structured PDF Chatbot running!"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


# ---------------------
# Main entry point (Render)
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render injects PORT automatically
    uvicorn.run("app:app", host="0.0.0.0", port=port)
