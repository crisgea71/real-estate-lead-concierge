const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const suggestionsEl = document.getElementById("suggestions");

const scoreNum = document.getElementById("scoreNum");
const ring = document.getElementById("ring");
const urgencyEl = document.getElementById("urgency");
const summaryCard = document.getElementById("summaryCard");
const summaryText = document.getElementById("summaryText");
const nextAction = document.getElementById("nextAction");
const copyBtn = document.getElementById("copyBtn");
const routingBox = document.getElementById("routingBox");
const routedAgent = document.getElementById("routedAgent");
const routedReason = document.getElementById("routedReason");
const waBtn = document.getElementById("waBtn");

const fieldEls = {
  budget: document.getElementById("f-budget"),
  area: document.getElementById("f-area"),
  timeline: document.getElementById("f-timeline"),
  buyer_type: document.getElementById("f-buyer"),
  financing: document.getElementById("f-financing"),
};

let history = [];

const STARTERS = [
  "Hi, I'm looking for an apartment in Dubai Marina.",
  "Do you have anything in Downtown?",
  "I want to invest in Dubai property.",
];

function renderSuggestions(items) {
  suggestionsEl.innerHTML = "";
  items.forEach((text) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = text;
    chip.onclick = () => { inputEl.value = text; send(); };
    suggestionsEl.appendChild(chip);
  });
}

function addBubble(text, who) {
  const b = document.createElement("div");
  b.className = `bubble ${who}`;
  b.textContent = text;
  messagesEl.appendChild(b);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
function showTyping() {
  const t = document.createElement("div");
  t.className = "typing";
  t.id = "typing";
  t.innerHTML = "<span></span><span></span><span></span>";
  messagesEl.appendChild(t);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
function hideTyping() {
  const t = document.getElementById("typing");
  if (t) t.remove();
}

function ringColor(score) {
  if (score >= 75) return "#5fcf8e";
  if (score >= 45) return "#e2b14e";
  return "#e0746a";
}

function animateScore(target) {
  const start = parseInt(scoreNum.textContent || "0", 10);
  const color = ringColor(target);
  const t0 = performance.now();
  const dur = 700;
  function frame(now) {
    const p = Math.min(1, (now - t0) / dur);
    const val = Math.round(start + (target - start) * p);
    scoreNum.textContent = val;
    ring.style.background =
      `radial-gradient(closest-side, var(--panel) 78%, transparent 79%),` +
      `conic-gradient(${color} ${val * 3.6}deg, var(--line) 0deg)`;
    if (p < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function updateField(key, value) {
  const el = fieldEls[key];
  if (!el) return;
  if (value) {
    el.textContent = value;
    el.parentElement.classList.add("filled");
  }
}
function updatePanel(data) {
  animateScore(data.score);
  if (data.urgency && data.urgency !== "—") {
    urgencyEl.textContent = data.urgency;
    urgencyEl.className = "urgency-pill " + data.urgency;
  }
  const lead = data.lead || {};
  updateField("budget", lead.budget);
  updateField("area", lead.area);
  updateField("timeline", lead.timeline);
  updateField("buyer_type", lead.buyer_type);
  updateField("financing", lead.financing);

  if (data.complete && data.summary) {
    summaryText.textContent = data.summary;
    nextAction.textContent = "→ " + data.next_action;
    summaryCard.classList.remove("hidden");

    if (data.routing) {
      routedAgent.textContent = data.routing.agent;
      routedReason.textContent = "· " + data.routing.reason;
      waBtn.href = data.routing.whatsapp_link;
      routingBox.classList.remove("hidden");
    }

    summaryCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

async function send() {
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  suggestionsEl.innerHTML = "";
  addBubble(text, "user");
  history.push({ role: "user", content: text });
  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await res.json();
    hideTyping();
    addBubble(data.reply, "ai");
    history.push({ role: "assistant", content: data.reply });
    updatePanel(data);
  } catch (e) {
    hideTyping();
    addBubble("Connection error. Please try again.", "ai");
  }
}
copyBtn.onclick = () => {
  navigator.clipboard.writeText(summaryText.textContent + "\n" + nextAction.textContent);
  copyBtn.textContent = "Copied ✓";
  setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
};

sendBtn.onclick = send;
inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

addBubble(
  `Hi! Welcome to ${window.AGENCY}. I'm ${window.CONCIERGE}, here 24/7. ` +
  `How can I help you find your home in Dubai today?`,
  "ai"
);
renderSuggestions(STARTERS);