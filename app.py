import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import uvicorn

# -------------------------
# Load data from JSON
# -------------------------
with open("qa_data.json", "r", encoding="utf-8") as f:
    data_list = json.load(f)

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

    # Transform user question
    user_vec = vectorizer.transform([user_q])
    similarity = cosine_similarity(user_vec, X)
    best_idx = similarity.argmax()
    best_answer = answers[best_idx]
    confidence = float(similarity[0][best_idx])

    # ✅ Set a minimum threshold
    threshold = 0.2  # you can adjust this (0.0 - 1.0)
    if confidence < threshold:
        return {"answer": "Sorry, I don't understand that question.", "confidence": confidence}

    return {"answer": best_answer, "confidence": confidence}

# -------------------------
# Root endpoint
# -------------------------
@app.get("/")
def root():
    return {"message": "Chatbot API running using JSON data!"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
