import pdfplumber
import re
from collections import defaultdict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import uvicorn
import html

# -------------------------
# PDF reader that preserves formatting
# -------------------------
def read_pdf_preserve_formatting(pdf_path):
    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                lines = page_text.splitlines()
            else:
                words = page.extract_words()
                rows = defaultdict(list)
                for w in words:
                    row_key = round(float(w["top"]), 1)
                    rows[row_key].append((float(w["x0"]), w["text"]))
                lines = []
                for key in sorted(rows.keys()):
                    row = " ".join([t for _x, t in sorted(rows[key], key=lambda x: x[0])]).strip()
                    lines.append(row)

            # Clean up each line (remove cid artifacts)
            cleaned_lines = []
            for ln in lines:
                # Remove (cid:###) patterns and extra spaces
                ln = re.sub(r'\(cid:\d+\)', '', ln)
                ln = re.sub(r'\s+', ' ', ln).strip()
                cleaned_lines.append(ln.rstrip())

            all_lines.extend(cleaned_lines)
            all_lines.append("")  # blank line between pages

    # Remove trailing blank lines
    while len(all_lines) and all_lines[-1] == "":
        all_lines.pop()

    return "\n".join(all_lines)


# -------------------------
# Extract sections by keywords
# -------------------------
def extract_sections(pdf_text, keywords):
    data_list = []
    text = pdf_text
    url_pattern = re.compile(r'(https?://\S+)')  # Matches http or https links

    for i, kw in enumerate(keywords):
        pattern_line = rf'(?m)^\s*{re.escape(kw)}\b'
        start = re.search(pattern_line, text, flags=re.IGNORECASE)
        if not start:
            start = re.search(rf'\b{re.escape(kw)}\b', text, flags=re.IGNORECASE)
        if not start:
            continue
        start_idx = start.start()

        end_idx = len(text)
        next_positions = []
        for j in range(i + 1, len(keywords)):
            nxt = re.search(rf'(?m)^\s*{re.escape(keywords[j])}\b', text, flags=re.IGNORECASE)
            if not nxt:
                nxt = re.search(rf'\b{re.escape(keywords[j])}\b', text, flags=re.IGNORECASE)
            if nxt:
                next_positions.append(nxt.start())
        if next_positions:
            end_idx = min(next_positions)

        section_text = text[start_idx:end_idx].strip("\n\r ")

        # Convert any URLs to clickable HTML links
        def replace_url(match):
            url = match.group(0)
            return f'<a href="{url}" target="_blank">{url}</a>'

        section_text = url_pattern.sub(replace_url, section_text)

        data_list.append({
            "keyword": kw,
            "answer": section_text
        })
    return data_list



# -------------------------
# Format for safe HTML display
# -------------------------
def format_for_html_display(text):
    # Escape everything first
    escaped = html.escape(text)

    # Restore <a> tags for URLs (allow only <a> tags)
    escaped = re.sub(
        r'&lt;a href=&quot;(https?://[^&]+)&quot; target=&quot;_blank&quot;&gt;(https?://[^&]+)&lt;/a&gt;',
        r'<a href="\1" target="_blank">\2</a>',
        escaped
    )

    # Preserve line breaks
    return escaped.replace("\n", "<br>\n")



# -------------------------
# Load multiple PDFs and build dataset
# -------------------------
pdfs = [
    {
        "path": "pdf/NISHIT JAIN RESUME.pdf",
        "keywords": ["nishit", "programming skills", "training / internship", "internship", "projects", "education", "accomplishments"]
    },
    {
        "path": "pdf/syllabus.pdf",
        "keywords": ["HTML", "CSS", "JavaScript", "Python", "OOPs", "SQL", "Data Structures", "Algorithms", "Networking", "Operating Systems", "Machine Learning"]
    }
]

all_data_list = []

for pdf_info in pdfs:
    print(f"📄 Reading {pdf_info['path']}...")
    pdf_text = read_pdf_preserve_formatting(pdf_info["path"])
    sections = extract_sections(pdf_text, pdf_info["keywords"])
    all_data_list.extend(sections)

answers = [item["answer"] for item in all_data_list]

# -------------------------
# Train TF-IDF on section content
# -------------------------
vectorizer = TfidfVectorizer(lowercase=True)
if len(answers) == 0:
    X = vectorizer.fit_transform([""])
else:
    X = vectorizer.fit_transform(answers)


# -------------------------
# FastAPI app
# -------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


class Query(BaseModel):
    question: str


@app.post("/chat")
def chat(query: Query):
    user_q = query.question.strip()
    if not user_q:
        return {"answer": "Please type something!", "confidence": 1.0}

    if len(answers) == 0:
        return {"answer": "No sections found in the PDFs. Check keywords and files.", "confidence": 0.0}

    # TF-IDF similarity
    user_vec = vectorizer.transform([user_q])
    similarity = cosine_similarity(user_vec, X)
    best_idx = int(similarity.argmax())
    confidence = float(similarity[0][best_idx])

    # --- Exact keyword fallback ---
    user_lower = user_q.lower()
    for i, item in enumerate(all_data_list):
        if user_lower == item["keyword"].lower():
            best_idx = i
            confidence = 1.0
            break

    # Lower threshold for short queries
    threshold = 0.08
    if confidence < threshold:
        return {"answer": "Sorry, I don't understand that question.", "confidence": confidence}

    formatted = format_for_html_display(all_data_list[best_idx]["answer"])
    return {
        "answer": formatted,
        "confidence": confidence,
        "matched_section": all_data_list[best_idx]["keyword"]
    }


@app.get("/")
def root():
    return {"message": "Chatbot API running using multiple PDFs!"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
