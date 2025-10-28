// const API_URL = "http://127.0.0.1:8000/chat";  // 👈 Local backend only
// console.log("✅ Using API:", API_URL);


// If deployed on Render → use your live Render domain
const API_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000/chat"
    : "https://chatbot-550d.onrender.com/chat";
console.log("✅ Using API:", API_URL);

// ----------------------
// DOM Elements
// ----------------------
const inputField = document.getElementById("input");
const messages = document.getElementById("messages");
const sendBtn = document.getElementById("send-btn");

const userTemplate = document.getElementById("user-message-template");
const botTemplate = document.getElementById("bot-message-template");

// ----------------------
// Append message to chat
// ----------------------
function appendMessageNode(textHTML, sender) {
  const template = sender === "user" ? userTemplate : botTemplate;
  const node = template.content.cloneNode(true);
  const messageEl = node.querySelector(".message");

  if (sender === "bot") {
    messageEl.innerHTML = textHTML;
  } else {
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
// Show confidence %
// ----------------------
function appendConfidence(node, confidence) {
  const confEl = document.createElement("div");
  confEl.style.fontSize = "0.75rem";
  confEl.style.color = "#666";
  confEl.style.marginTop = "6px";
  confEl.innerText = `Confidence: ${(confidence * 100).toFixed(1)}%`;
  const parentRow = node.closest(".message-row");
  if (parentRow) parentRow.appendChild(confEl);
  messages.scrollTop = messages.scrollHeight;
}

// ----------------------
// Render multiple matches as clickable buttons
// ----------------------
function renderMatches(matches) {
  const container = document.createElement("div");
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = "6px";

  matches.forEach((match, i) => {
    const btn = document.createElement("button");
    btn.innerHTML = `<b>Match ${i + 1} (${match.keyword})</b> - Accuracy: ${(match.confidence * 100).toFixed(1)}%`;
    btn.style.padding = "6px 10px";
    btn.style.borderRadius = "6px";
    btn.style.border = "1px solid #0052cc";
    btn.style.backgroundColor = "#e1f5fe";
    btn.style.cursor = "pointer";
    btn.addEventListener("click", () => {
      appendMessageNode(
        `<b>Match ${i + 1} (${match.keyword}) Full Answer:</b><br>${match.answer}`,
        "bot"
      );
    });
    container.appendChild(btn);
  });

  return container;
}

// ----------------------
// Send message handler
// ----------------------
async function sendMessage() {
  const input = inputField.value.trim();
  if (!input) return;
  inputField.disabled = true;
  sendBtn.disabled = true;

  appendMessageNode(escapeHtml(input).replace(/\n/g, "<br>\n"), "user");
  inputField.value = "";
  const typingNode = appendMessageNode("Typing...", "bot");

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: input }),

    });

    if (!res.ok) throw new Error("Network response was not ok");
    const data = await res.json();

    if (data.top_matches && data.top_matches.length > 0) {
      typingNode.innerHTML = "Select a match to view full answer:";
      const buttons = renderMatches(data.top_matches);
      typingNode.appendChild(buttons);
    } else {
      typingNode.innerHTML = "❌ No relevant answer found.";
    }
  } catch (err) {
    console.error("Error:", err);
    typingNode.innerHTML = "⚠️ Unable to connect to the server. Please try again later.";
  } finally {
    inputField.disabled = false;
    sendBtn.disabled = false;
    inputField.focus();
  }
}

// ----------------------
// Escape HTML (security)
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
// Event listeners
// ----------------------
inputField.addEventListener("keypress", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);
