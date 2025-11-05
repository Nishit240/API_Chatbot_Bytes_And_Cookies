from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
import sys

# Ensure imports work even when uvicorn reloads
sys.path.append(os.path.dirname(__file__))

from utils import convert_pdf_to_html

app = FastAPI(title="📘 Local PDF Cache Builder (Preserve Structure)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# ✅ Configuration
# -----------------------------
PDF_DIR = os.path.join(os.getcwd(), "app_preprocess", "pdf")
CACHE_DIR = os.path.join(os.getcwd(), "app_preprocess", "pdf_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# -----------------------------
# ✅ Request Body Model
# -----------------------------
class PDFListRequest(BaseModel):
    pdf_list: list[str]  # list of URLs or API endpoints

# -----------------------------
# ✅ Main Cache Builder
# -----------------------------
@app.post("/build_cache")
async def build_cache(request: PDFListRequest):
    created = []

    for api_link in request.pdf_list:
        try:
            print(f"🔗 Fetching from API: {api_link}")
            resp = requests.get(api_link.strip(), timeout=10)
            resp.raise_for_status()
            data = resp.json()

            pdf_list = data.get("pdf_list", [])
            if not pdf_list:
                print(f"⚠️ No PDFs found in {api_link}")
                continue

            for pdf_name in pdf_list:
                pdf_path = os.path.join(PDF_DIR, pdf_name.strip())

                if not os.path.exists(pdf_path):
                    print(f"⚠️ File not found locally: {pdf_path}")
                    continue

                name = os.path.basename(pdf_name).replace(".pdf", "")
                html_path = os.path.join(CACHE_DIR, f"{name}.html")

                print(f"📄 Converting local PDF: {pdf_path}")
                try:
                    convert_pdf_to_html(pdf_path, html_path)
                    created.append(name)
                except Exception as e:
                    print(f"❌ Failed to convert {pdf_path}: {e}")

        except Exception as e:
            print(f"❌ Failed for {api_link}: {e}")

    return {"status": "✅ success", "cached_files": created}


@app.get("/")
def home():
    return {"message": "✅ Local PDF Cache Builder running."}


# ===============================
# 🔹 Local Run
# # ===============================
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


# ---------------------
# Main entry point (Render)
## -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render injects PORT automatically
    uvicorn.run("app:app", host="0.0.0.0", port=port)
