from fastapi.testclient import TestClient
from app import app   # import FastAPI app from app.py

client = TestClient(app)

def test_name_question():
    response = client.post("/chat", json={"question": "What is your name?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "confidence" in data
    assert "chatbot" in data["answer"].lower()

def test_python_question():
    response = client.post("/chat", json={"question": "Explain Python"})
    assert response.status_code == 200
    data = response.json()
    assert "python" in data["answer"].lower()

def test_fastapi_question():
    response = client.post("/chat", json={"question": "What is FastAPI?"})
    assert response.status_code == 200
    data = response.json()
    assert "fastapi" in data["answer"].lower()

def test_ai_question():
    response = client.post("/chat", json={"question": "Tell me about Artificial Intelligence"})
    assert response.status_code == 200
    data = response.json()
    assert "intelligence" in data["answer"].lower()

def test_unknown_question():
    response = client.post("/chat", json={"question": "What is the meaning of life?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
