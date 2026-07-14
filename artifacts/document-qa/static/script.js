const BASE_URL = "https://luna-doc-qa-api.onrender.com";

const pdfInput = document.getElementById("pdf-input");
const uploadStatus = document.getElementById("upload-status");
const uploadStatusText = document.getElementById("upload-status-text");
const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const chatSubtitle = document.getElementById("chat-subtitle");
let documentReady = false;

function setUploadStatus(state, text) {
  uploadStatus.classList.remove("upload-status-empty", "upload-status-ready", "upload-status-error");
  uploadStatus.classList.add(`upload-status-${state}`);
  uploadStatusText.textContent = text;
}

function setChatEnabled(enabled) {
  documentReady = enabled;
  chatInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
  if (enabled) chatSubtitle.textContent = "Ready! Ask me anything.";
}

function appendMessage(role, content) {
  const message = document.createElement("div");
  message.className = `message message-${role}`;
  const bubble = document.createElement("div");
  bubble.className = `bubble bubble-${role}`;
  bubble.textContent = content;
  message.appendChild(bubble);
  chatWindow.appendChild(message);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return message;
}

function appendTypingIndicator() {
  const message = document.createElement("div");
  message.className = "message message-ai";
  message.id = "typing-indicator";
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-ai typing";
  bubble.innerHTML = "<span></span><span></span><span></span>";
  message.appendChild(bubble);
  chatWindow.appendChild(message);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

pdfInput.addEventListener("change", async () => {
  const file = pdfInput.files[0];
  if (!file) return;
  setUploadStatus("empty", `Uploading ${file.name}...`);
  const formData = new FormData();
  formData.append("file", file);
  try {
    const response = await fetch(`${BASE_URL}/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed.");
    }
    const data = await response.json();
    setUploadStatus("ready", `${data.filename} · ${data.pages} pages`);
    appendMessage("ai", "Ready! Ask me anything.");
    setChatEnabled(true);
    chatInput.focus();
  } catch (error) {
    setUploadStatus("error", error.message || "Upload failed.");
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = chatInput.value.trim();
  if (!question || !documentReady) return;
  appendMessage("user", question);
  chatInput.value = "";
  chatInput.disabled = true;
  sendBtn.disabled = true;
  appendTypingIndicator();
  try {
    const response = await fetch(`${BASE_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Something went wrong.");
    }
    const data = await response.json();
    removeTypingIndicator();
    appendMessage("ai", data.answer);
  } catch (error) {
    removeTypingIndicator();
    appendMessage("ai", error.message || "Something went wrong.");
  } finally {
    chatInput.disabled = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
});
