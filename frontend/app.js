const apiBaseUrl = "http://127.0.0.1:8000";
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const status = document.querySelector("#status");
const sendButton = document.querySelector("#send-button");

function addMessage(role, text) {
  const article = document.createElement("article");
  const speaker = document.createElement("span");
  const paragraph = document.createElement("p");

  article.className = `message ${role}`;
  speaker.className = "speaker";
  speaker.textContent = role === "assistant" ? "雷姆" : "你";
  paragraph.textContent = text;
  article.append(speaker, paragraph);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

async function checkHealth() {
  try {
    const response = await fetch(`${apiBaseUrl}/api/health`);
    if (!response.ok) throw new Error("health check failed");
    status.textContent = "后端已连接 · 演示模式";
    status.classList.add("online");
  } catch {
    status.textContent = "后端未连接";
    status.classList.remove("online");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  sendButton.disabled = true;
  status.textContent = "正在回复…";

  try {
    const response = await fetch(`${apiBaseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!response.ok) throw new Error("chat request failed");

    const data = await response.json();
    addMessage("assistant", data.reply);
    status.textContent = "后端已连接 · 演示模式";
    status.classList.add("online");
  } catch {
    addMessage("assistant", "我暂时无法连接到本地后端。请先启动后端服务后再试。");
    status.textContent = "后端未连接";
    status.classList.remove("online");
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

checkHealth();
