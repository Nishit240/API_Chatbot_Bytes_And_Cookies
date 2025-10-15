const API_URL = "http://127.0.0.1:8000/chat";

const inputField = document.getElementById("input");
const messages = document.getElementById("messages");
const sendBtn = document.getElementById("send-btn");
const renderToggle = document.getElementById("render-html-toggle");

const userTemplate = document.getElementById("user-message-template");
const botTemplate = document.getElementById("bot-message-template");

function appendMessageNode(textHTML, sender) {
    const template = sender === "user" ? userTemplate : botTemplate;
    const node = template.content.cloneNode(true);
    const messageEl = node.querySelector(".message");
    messageEl.innerHTML = textHTML;
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
    const rows = messages.querySelectorAll(sender === "user" ? ".user-row .message" : ".bot-row .message");
    return rows[rows.length - 1];
}

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

async function sendMessage() {
    const input = inputField.value.trim();
    if (!input) return;
    inputField.disabled = true;
    sendBtn.disabled = true;

    const userNode = appendMessageNode(escapeHtml(input).replace(/\n/g, "<br>\n"), "user");
    inputField.value = "";
    const typingNode = appendMessageNode("Typing...", "bot");

    try {
        const res = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: input })
        });

        if (!res.ok) throw new Error("Network response was not ok");

        const data = await res.json();

        // If toggle is ON => render HTML raw
        const renderHtml = renderToggle && renderToggle.checked;
        if (renderHtml) {
            // WARNING: only enable this for trusted PDFs!
            // Expect the backend to send unescaped HTML with <br> for newlines
            typingNode.innerHTML = data.answer || "No answer returned.";
        } else {
            // safe mode (backend escapes <, >). We just insert innerHTML (it contains &lt; &gt; and <br>)
            typingNode.innerHTML = data.answer || "No answer returned.";
        }

        if (typeof data.confidence === "number") appendConfidence(typingNode, data.confidence);

    } catch (err) {
        console.error("Error:", err);
        typingNode.innerHTML = "⚠️ Unable to connect to the server. Please try again later.";
    } finally {
        inputField.disabled = false;
        sendBtn.disabled = false;
        inputField.focus();
    }
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

inputField.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
sendBtn.addEventListener("click", sendMessage);
