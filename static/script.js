// --------------------
// Chatbot JS
// --------------------
const API_URL = "http://127.0.0.1:8000/chat";

const inputField = document.getElementById("input");
const messages = document.getElementById("messages");
const sendBtn = document.getElementById("send-btn");

// --------------------
// Append message using template
// --------------------
function appendMessage(text, sender) {
    const templateId = sender === "user" ? "user-message-template" : "bot-message-template";
    const template = document.getElementById(templateId);
    const messageRow = template.content.cloneNode(true);
    messageRow.querySelector(".message").innerHTML = text;
    messages.appendChild(messageRow);
    messages.scrollTop = messages.scrollHeight;
}

// --------------------
// Send Message
// --------------------
async function sendMessage() {
    const input = inputField.value.trim();
    if (!input) return;

    appendMessage(input, "user");
    inputField.value = "";

    // Show bot typing
    appendMessage("Typing...", "bot");

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: input })
        });

        const data = await response.json();
        // Update last bot message
        const botMessages = messages.querySelectorAll(".bot-row .message");
        botMessages[botMessages.length - 1].innerHTML = data.answer;
    } catch (err) {
        console.error("Error:", err);
        const botMessages = messages.querySelectorAll(".bot-row .message");
        botMessages[botMessages.length - 1].innerHTML = 
            "⚠️ Unable to connect to server. Please try again later.";
    }
}

// --------------------
// Events
// --------------------
inputField.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});
sendBtn.addEventListener("click", sendMessage);
