import os
import re
import html
import logging
import requests
import fitz  # PyMuPDF
import pdfplumber
from io import BytesIO
import warnings

# -------------------------
# Setup logging & suppress noisy warnings
# -------------------------
warnings.filterwarnings("ignore", message=".*invalid float value.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Cannot set gray non-stroke color.*", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -------------------------
# Clean and normalize text
# -------------------------
def _clean_text(s: str) -> str:
    s = html.unescape(s or "")
    s = s.replace("", "→").replace("•", "→").replace("➢", "→")
    s = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", s)
    s = re.sub(r"([a-z])\s*\n\s*([A-Z])", r"\1. \2", s)
    s = re.sub(r"\bL\s*aw\b", "Law", s, flags=re.I)
    s = re.sub(r"\b(ontract|ontrac|ontra)\b", "Contract", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s)
    s = s.replace("\n", "<br>")
    return s.strip()

# -------------------------
# Table → HTML
# -------------------------
def _table_to_html(table):
    html_table = (
        "<table border='1' "
        "style='border-collapse:collapse;width:100%;text-align:left;font-family:Calibri,sans-serif;'>"
    )
    for i, row in enumerate(table):
        html_table += "<tr>"
        for cell in row:
            cell_text = html.escape(str(cell or "").strip())
            if i == 0:
                # header row
                html_table += (
                    f"<th style='background-color:#d9ead3;padding:8px;font-weight:bold;'>{cell_text}</th>"
                )
            else:
                html_table += f"<td style='padding:6px'>{cell_text}</td>"
        html_table += "</tr>"
    html_table += "</table><br>"
    return html_table

# -------------------------
# Convert PDF → HTML (Preserves tables)
# -------------------------
def convert_pdf_to_html(pdf_source: str, html_path: str, force: bool = False):
    """
    Convert a local or remote PDF to clean HTML (tables, headings, paragraphs).
    """
    os.makedirs(os.path.dirname(html_path), exist_ok=True)

    if not force and os.path.exists(html_path):
        logger.info("✅ Cache exists — skipping conversion: %s", html_path)
        return

    # Read bytes
    if isinstance(pdf_source, str) and pdf_source.lower().startswith("http"):
        logger.info(f"🌐 Downloading remote PDF: {pdf_source}")
        r = requests.get(pdf_source, timeout=20)
        r.raise_for_status()
        pdf_bytes = r.content
    else:
        if not os.path.exists(pdf_source):
            raise FileNotFoundError(f"❌ PDF not found: {pdf_source}")
        with open(pdf_source, "rb") as f:
            pdf_bytes = f.read()

    pdf_stream = BytesIO(pdf_bytes)
    html_content = ["<html><body>"]

    try:
        # Try structured extraction (tables + text)
        try:
            with pdfplumber.open(pdf_stream) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    html_content.append(f"<h3>Page {i}</h3>")
                    text = page.extract_text() or ""
                    if text.strip():
                        html_content.append(f"<p>{html.escape(text)}</p>")

                    tables = page.extract_tables()
                    for table in tables:
                        if table and any(any(cell for cell in row) for row in table):
                            html_content.append(_table_to_html(table))

                    html_content.append("<hr>")

        except Exception as e:
            logger.warning(f"⚠️ Structured extraction failed: {e}")
            # fallback to PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for i, page in enumerate(doc, start=1):
                html_content.append(f"<h3>Page {i}</h3>")
                html_content.append(page.get_text("html") or "")
                html_content.append("<hr>")

        html_content.append("</body></html>")
        cleaned_html = _clean_text("".join(html_content))

        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(cleaned_html)

        logger.info(f"✅ Converted & cached: {os.path.basename(html_path)}")

    except Exception as e:
        logger.exception(f"❌ Conversion failed for {pdf_source}")
        raise

# -------------------------
# Load from cache
# -------------------------
def load_cached_html(pdf_name: str, cache_dir: str = None) -> str:
    if cache_dir is None:
        cache_dir = os.path.join(os.getcwd(), "app_preprocess", "pdf_cache")
    filename = os.path.basename(pdf_name).replace(".pdf", ".html")
    cache_path = os.path.join(cache_dir, filename)
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"Cached HTML not found: {cache_path}")
    with open(cache_path, "r", encoding="utf-8") as f:
        return f.read()

# -------------------------
# Extract section after heading
# -------------------------
def extract_section_after_heading(html_text: str, heading: str, word_limit: int = 400):
    if not html_text or not heading:
        return None
    heading_norm = heading.strip()
    header_re = re.compile(r"(<h[1-6][^>]*>.*?</h[1-6]>)", re.I | re.S)
    headers = []
    for m in header_re.finditer(html_text):
        title = re.sub(r"<[^>]+>", "", m.group(0)).strip()
        headers.append({"start": m.start(), "title": title})

    if headers:
        for i, h in enumerate(headers):
            start = h["start"]
            end = headers[i + 1]["start"] if i + 1 < len(headers) else len(html_text)
            if h["title"].lower() == heading_norm.lower():
                return html_text[start:end]

    m = re.search(rf"(?i){re.escape(heading_norm)}", html_text)
    if not m:
        return None
    snippet = html_text[m.start() : m.start() + 8000]
    snippet_text = re.sub(r"<[^>]+>", " ", snippet)
    snippet_text = " ".join(snippet_text.split()[:word_limit])
    return f"<div class='formatted-answer'><h4>{heading}</h4><p>{snippet_text}</p></div>"

# -------------------------
# Format for readability
# -------------------------
def format_for_readability(raw_html: str) -> str:
    if not raw_html:
        return "❌ No relevant section found."
    text = raw_html.replace("->", "→").replace("➢", "→")
    text = re.sub(r"([.?!])\s+(?=[A-Z])", r"\1<br><br>", text)
    return f"<div class='formatted-answer'>{text}</div>"
