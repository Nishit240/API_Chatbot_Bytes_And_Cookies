import mysql.connector
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
import uvicorn

# -------------------------
# Connect to MySQL (XAMPP server)
# -------------------------
def fetch_data_from_mysql():
    conn = mysql.connector.connect(
        host="127.0.0.1",   # or your XAMPP server IP / domain
        user="root",
        password="",        # update if needed
        database="chatbot_db"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT keyword, html_details FROM syllabus_topics")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    data_list = []

    for row in rows:
        keyword = row["keyword"]
        html = row["html_details"]

        soup = BeautifulSoup(html, "html.parser")
        clean_text = ""

        for element in soup.descendants:
            if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                clean_text += f"<b>{element.get_text().strip()}</b><br>\n<br>"
            elif element.name == "p":
                clean_text += f"{element.get_text().strip()}<br>\n<br>"
            elif element.name == "li":
                clean_text += f"• {element.get_text().strip()}<br>\n<br>"
            elif element.name == "table":
                rows = element.find_all("tr")
                table_text = ""
                for r in rows:
                    cols = r.find_all(["th", "td"])
                    col_text = [c.get_text().strip() for c in cols]
                    col_text = [c.replace("Try it »", "").strip() for c in col_text]
                    table_text += " |➜| ".join(col_text) + "<br>\n<br>"
                clean_text += table_text
            elif element.name == "pre":
                clean_text += f"{element.get_text().strip()}<br>\n<br>"

        data_list.append({
            "keyword": keyword,
            "answer": clean_text.strip()
        })

    return data_list

# -------------------------
# Load data from MySQL
# -------------------------
print("Fetching data from MySQL...")
data_list = fetch_data_from_mysql()
print(f"✅ Loaded {len(data_list)} records from MySQL")

keywords = [item["keyword"] for item in data_list]
answers = [item["answer"] for item in data_list]

# -------------------------
# Train TF-IDF
# -------------------------
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(keywords)

# -------------------------
# FastAPI setup
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

# -------------------------
# Chat endpoint
# -------------------------
@app.post("/chat")
def chat(query: Query):
    user_q = query.question.strip()
    if not user_q:
        return {"answer": "Please type something!", "confidence": 1.0}

    user_vec = vectorizer.transform([user_q])
    similarity = cosine_similarity(user_vec, X)
    best_idx = similarity.argmax()
    best_answer = answers[best_idx]
    confidence = float(similarity[0][best_idx])

    threshold = 0.2
    if confidence < threshold:
        return {"answer": "Sorry, I don't understand that question.", "confidence": confidence}

    return {"answer": best_answer, "confidence": confidence}

# -------------------------
# Root endpoint
# -------------------------
@app.get("/")
def root():
    return {"message": "Chatbot API running using MySQL database!"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
