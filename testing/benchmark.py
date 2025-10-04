import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load dataset
with open("qa_data.json", "r") as f:
    qa_data = json.load(f)

questions = [item["question"] for item in qa_data]
answers = [item["answer"] for item in qa_data]

# TF-IDF model
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(questions)

# Test questions
test_cases = [
    {"question": "Who is the creator of Python?", "expected": "Python was created by Guido van Rossum in 1991."},
    {"question": "Explain AI", "expected": "Artificial Intelligence (AI) is the simulation of human intelligence by machines."},
    {"question": "What is FastAPI?", "expected": "FastAPI is a modern, fast web framework for building APIs with Python."},
    {"question": "What is Python?", "expected": "Python is a high-level programming language used for web, data science, AI, and more."}
]

# Evaluate accuracy
correct = 0
for case in test_cases:
    user_vec = vectorizer.transform([case["question"]])
    similarity = cosine_similarity(user_vec, X)
    best_idx = similarity.argmax()
    predicted = answers[best_idx]
    print(f"Q: {case['question']}")
    print(f"Predicted: {predicted}")
    print(f"Expected: {case['expected']}")
    print(f"Confidence: {similarity[0][best_idx]:.2f}")
    print("-"*40)
    if predicted.lower() == case["expected"].lower():
        correct += 1

accuracy = (correct / len(test_cases)) * 100
print(f"Accuracy: {accuracy:.2f}%")
