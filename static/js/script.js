// If deployed on Render → use your live Render domain
// const API_URL =
//   window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
//     ? "http://127.0.0.1:8000/chat"
//     : "https://chatbot-jrda.onrender.com/chat";
// console.log("✅ Using API:", API_URL);

// ----------------------
// ✅ API URL Configuration
// ----------------------
// If deploying on Render → use your live Render domain

// ✅ API URL of FastAPI backend 
const API_URL = "http://127.0.0.1:8000/chat"; 
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
// Escape HTML for user input only
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
    // ✅ Render bot’s message as HTML (don’t escape)
    messageEl.innerHTML = textHTML;
  } else {
    // ✅ Render user’s message as safe text
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
// Fixed PDF URL (backend authorized one)
// ----------------------
const PDF_URL =
  "https://renaicon.in/storage/syllabus/images/A8YRAiNXEIX05H33IQbtVVyUd3HKCO9LjQ8FJBLG.pdf";

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
        pdf_url: PDF_URL,
      }),
    });

    if (!res.ok) throw new Error("Network response was not ok");
    const data = await res.json();

   if (data.top_matches && data.top_matches.length > 0) {
    typingNode.innerHTML = "<b>✅ Found related topics:</b><br><br>";

    // Create buttons for top matches
    data.top_matches.forEach((match, index) => {
      const btn = document.createElement("button");
      btn.innerHTML = `<b>Match ${index + 1}:</b> ${match.keyword} <small>(${(
        match.confidence * 100
      ).toFixed(1)}%)</small>`;
      btn.classList.add("match-btn");
      btn.onclick = () => showAnswer(match, index);
      typingNode.appendChild(btn);
      typingNode.appendChild(document.createElement("br"));
    });
  } else {
    typingNode.innerHTML = "❌ No relevant answer found.";
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
// Show Answer when Button Clicked
// ----------------------
function showAnswer(match, index) {
  const messagesDiv = document.getElementById("messages");

  // Create bot message container
  const botMessageRow = document.createElement("div");
  botMessageRow.classList.add("message-row", "bot-row");

  // Avatar
  const avatarDiv = document.createElement("div");
  avatarDiv.classList.add("avatar");
  const img = document.createElement("img");
  img.src = "image/technical-support.png";
  img.alt = "Bot";
  avatarDiv.appendChild(img);

  // ✅ Message content: render HTML directly
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", "bot");

  messageDiv.innerHTML = `
    <b>Match ${index + 1}:</b> ${match.keyword}<br><br>
    ${match.answer ? match.answer : "<i>No snippet found</i>"}
  `;

  botMessageRow.appendChild(avatarDiv);
  botMessageRow.appendChild(messageDiv);
  messagesDiv.appendChild(botMessageRow);

  // Scroll to bottom
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
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
