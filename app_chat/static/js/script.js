// ----------------------
// ✅ API URL Configuration
// ----------------------
// If deploying on Render → use your live Render domain
const API_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000/chat"
    : "https://chatbot-jrda.onrender.com/chat";
console.log("✅ Using API:", API_URL);

// const API_URL = "http://127.0.0.1:8000/chat";
// console.log("✅ Using API:", API_URL);

// ----------------------
// DOM Elements
// ----------------------
const inputField = document.getElementById("input");
const messages = document.getElementById("messages");
const sendBtn = document.getElementById("send-btn");

const userTemplate = document.getElementById("user-message-template");
const botTemplate = document.getElementById("bot-message-template");

// ----------------------
// Escape HTML (for user input only)
// ----------------------
function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ----------------------
// Append message to chat
// ----------------------
function appendMessageNode(textHTML, sender) {
  const template = sender === "user" ? userTemplate : botTemplate;
  const node = template.content.cloneNode(true);
  const messageEl = node.querySelector(".message");

  if (sender === "bot") {
    // ✅ Bot message supports HTML
    messageEl.innerHTML = textHTML;
  } else {
    // ✅ User message escapes HTML
    messageEl.innerHTML = escapeHtml(textHTML).replace(/\n/g, "<br>\n");
  }

  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  const rows = messages.querySelectorAll(
    sender === "user" ? ".user-row .message" : ".bot-row .message"
  );
  return rows[rows.length - 1];
}

// ----------------------
// ✅ Fixed PDF URL (from backend API source)
// ----------------------
const PDF_URL = "https://renaicon.in/course_details_api";

// ----------------------
// Send Message to Backend
// ----------------------
async function sendMessage() {
  const input = inputField.value.trim();
  if (!input) return;

  // Disable input while sending
  inputField.disabled = true;
  sendBtn.disabled = true;

  // Show user message
  appendMessageNode(input, "user");
  inputField.value = "";

  // Show typing indicator
  const typingNode = appendMessageNode("Typing...", "bot");

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: input,
        url: PDF_URL,
      }),
    });

    if (!res.ok) throw new Error("Network response was not ok");
    const data = await res.json();
    
  if (data.top_matches && data.top_matches.length > 0) {
    typingNode.innerHTML = `
      <b>📄 PDF:</b> ${data.pdf_name}<br>
      <b>🔍 Top Matches:</b><br><br>
      ${data.top_matches
        .map(
          (m, i) =>
            `<button class="answer-btn" data-index="${i}">
              ${i + 1}. ${m.keyword} (${(m.confidence * 100).toFixed(1)}%)
            </button>`
        )
        .join("<br>")}
    `;

    // When user clicks a button, show the full answer
    typingNode.querySelectorAll(".answer-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const index = parseInt(e.target.getAttribute("data-index"));
        const match = data.top_matches[index];
        e.target.parentElement.innerHTML = `
          <b>📘 ${match.keyword}</b><br><br>
          ${match.answer}
        `;
      });
    });
  } else {
    typingNode.innerHTML = "❌ No relevant answer found for your question.";
  }


  } catch (err) {
    console.error("Error:", err);
    typingNode.innerHTML = "⚠️ Unable to connect to the server.";
  } finally {
    inputField.disabled = false;
    sendBtn.disabled = false;
    inputField.focus();
  }
}

// ----------------------
// Event Listeners
// ----------------------
inputField.addEventListener("keypress", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);
