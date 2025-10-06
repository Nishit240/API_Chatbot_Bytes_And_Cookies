from bs4 import BeautifulSoup
import mysql.connector
import json

# Connect to MySQL
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="chatbot_db"
)
cursor = conn.cursor(dictionary=True)

cursor.execute("SELECT keyword, html_details FROM syllabus_topics")
rows = cursor.fetchall()

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
            # Process table rows
            rows = element.find_all("tr")
            table_text = ""
            for r in rows:
                cols = r.find_all(["th", "td"])
                col_text = [c.get_text().strip() for c in cols]
                # Remove any "Try it »"
                col_text = [c.replace("Try it »", "").strip() for c in col_text]
                # Join remaining columns
                table_text += " |➜| ".join(col_text) + "<br>\n<br>"
            clean_text += table_text
        elif element.name == "pre":
            clean_text += f"{element.get_text().strip()}<br>\n<br>"

    data_list.append({
        "keyword": keyword,
        "answer": clean_text.strip()
    })

# Save JSON
with open("qa_data.json", "w", encoding="utf-8") as f:
    json.dump(data_list, f, ensure_ascii=False, indent=4)

conn.close()
print("Data exported to qa_data.json successfully!")

