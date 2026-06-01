"""
AI Real Estate Lead Concierge — demo backend (Marina Homes Dubai).

A single Flask app that:
  1. Serves the demo UI.
  2. Runs an AI concierge ("Aya") that replies instantly to a lead,
     qualifies them (budget / area / timeline / readiness),
     and returns a structured lead profile.
  3. Scores the lead deterministically in Python and builds a clean
     summary the agent can act on.

Primary brain: Groq (free tier, no card). Falls back to a built-in
rule-based concierge if no GROQ_API_KEY is set — so the repo runs the
moment you clone it, even before you add a key.
"""

import os
import re
import json
import time
import requests
from collections import defaultdict
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

AGENCY = "Marina Homes Dubai"
CONCIERGE = "Aya"

# --------------------------------------------------------------------------- #
#  Rate limiting — protect Groq credits (25 messages per IP, rolling 24h)      #
# --------------------------------------------------------------------------- #

MAX_MESSAGES_PER_IP = 25
RATE_WINDOW_SECONDS = 60 * 60 * 24   # rolling 24-hour window (per day)
_ip_counts = defaultdict(list)


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    _ip_counts[ip] = [t for t in _ip_counts[ip] if now - t < RATE_WINDOW_SECONDS]
    if len(_ip_counts[ip]) >= MAX_MESSAGES_PER_IP:
        return True
    _ip_counts[ip].append(now)
    return False


# --------------------------------------------------------------------------- #
#  Agents & lead routing (Option A: team inbox, Option B: by area)             #
# --------------------------------------------------------------------------- #

# In production these come from the agency. WhatsApp numbers are international
# format WITHOUT "+" or spaces, ready for wa.me links.
AGENTS = [
    {"name": "Layla", "whatsapp": "971500000001", "areas": ["Dubai Marina", "JBR"]},
    {"name": "Omar",  "whatsapp": "971500000002", "areas": ["Downtown", "Business Bay"]},
    {"name": "Sara",  "whatsapp": "971500000003", "areas": ["Palm Jumeirah", "Jumeirah", "Emirates Hills"]},
]
TEAM_WHATSAPP = "971500000000"
_round_robin = {"i": 0}


def route_lead(lead: dict) -> dict:
    """Option B (smart): match by area. Option A (fallback): round-robin."""
    area = (lead.get("area") or "").strip().lower()
    if area:
        for agent in AGENTS:
            if any(area == a.lower() for a in agent["areas"]):
                return {"agent": agent["name"], "whatsapp": agent["whatsapp"],
                        "reason": f"area match: {agent['areas'][0]}"}
    agent = AGENTS[_round_robin["i"] % len(AGENTS)]
    _round_robin["i"] += 1
    return {"agent": agent["name"], "whatsapp": agent["whatsapp"],
            "reason": "round-robin"}

# --------------------------------------------------------------------------- #
#  The concierge's brain (system prompt)                                       #
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = f"""You are {CONCIERGE}, the AI concierge for {AGENCY}, a high-end
real estate agency in Dubai. A new lead has just messaged. Your job is to reply
INSTANTLY, warmly and professionally, and qualify the lead so a human agent only
spends time on serious buyers.

You must collect, conversationally and one question at a time:
- the area / community they want (e.g. Dubai Marina, Downtown, Palm Jumeirah, JVC)
- their budget (in AED)
- their timeline (how soon they want to buy/move)
- whether they are a serious buyer, an investor, or just browsing
- financing: cash or mortgage (ask only if natural)

Rules:
- Sound human and concise. Never robotic. One clear question per message.
- Never invent property listings or prices. You qualify; the agent follows up.
- Once you have area + budget + timeline + readiness, thank them and tell them an
  agent will reach out shortly. Do not keep asking after that.

You MUST respond with a single valid JSON object and nothing else, in this shape:

{{
  "reply": "<your next message to the lead>",
  "lead": {{
    "name": <string or null>,
    "budget": <human string like "3M AED" or null>,
    "budget_aed": <integer AED or null>,
    "area": <string or null>,
    "timeline": <human string or null>,
    "timeline_bucket": <"immediate" | "1-3 months" | "3-6 months" | "browsing" | null>,
    "buyer_type": <"Serious Buyer" | "Investor" | "Browsing" | null>,
    "financing": <"cash" | "mortgage" | null>
  }},
  "stage_complete": <true once area + budget + timeline + readiness are known, else false>
}}

Always re-derive the full lead object from the ENTIRE conversation so far.
"""


# --------------------------------------------------------------------------- #
#  Deterministic scoring (runs in Python, not the LLM, so it is consistent)    #
# --------------------------------------------------------------------------- #

def score_lead(lead: dict) -> dict:
    score = 0

    aed = lead.get("budget_aed")
    if aed:
        if aed >= 5_000_000:
            score += 30
        elif aed >= 2_000_000:
            score += 25
        elif aed >= 1_000_000:
            score += 18
        else:
            score += 10

    bucket = lead.get("timeline_bucket")
    score += {"immediate": 30, "1-3 months": 22,
              "3-6 months": 12, "browsing": 4}.get(bucket, 0)

    if lead.get("area"):
        score += 15

    bt = (lead.get("buyer_type") or "").lower()
    if "serious" in bt or "ready" in bt:
        score += 15
    elif "investor" in bt:
        score += 12
    elif "browsing" in bt:
        score += 3

    fin = lead.get("financing")
    if fin == "cash":
        score += 10
    elif fin == "mortgage":
        score += 6

    score = max(0, min(100, score))

    if score >= 75:
        urgency = "High"
        next_action = "Call within 1 hour and send 2-3 matching properties."
    elif score >= 45:
        urgency = "Medium"
        next_action = "Call back today and follow up with listings."
    else:
        urgency = "Low"
        next_action = "Add to nurture list; follow up this week."

    return {"score": score, "urgency": urgency, "next_action": next_action}


def build_summary(lead: dict, scoring: dict) -> str:
    name = lead.get("name") or "This lead"
    area = lead.get("area") or "an unspecified area"
    budget = lead.get("budget") or "an unstated budget"
    timeline = lead.get("timeline") or "no clear timeline"
    buyer = lead.get("buyer_type") or "Unknown profile"
    fin = f", paying {lead['financing']}" if lead.get("financing") else ""
    return (
        f"{name} is looking in {area}, budget {budget}, timeline: {timeline}{fin}. "
        f"Profile: {buyer}. Priority: {scoring['urgency']}. "
        f"Recommended: {scoring['next_action']}"
    )


# --------------------------------------------------------------------------- #
#  Groq call                                                                   #
# --------------------------------------------------------------------------- #

def call_groq(messages: list) -> dict:
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


# --------------------------------------------------------------------------- #
#  Offline fallback concierge (no API key needed)                              #
# --------------------------------------------------------------------------- #

DUBAI_AREAS = [
    "Dubai Marina", "Downtown", "Palm Jumeirah", "JVC", "Business Bay",
    "Dubai Hills", "Jumeirah", "Emirates Hills", "Arabian Ranches", "JBR",
]


def extract_signals(text: str, lead: dict) -> dict:
    t = text.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*(m|million|k|aed|,?\d{3,})", t)
    if m and not lead.get("budget_aed"):
        num = float(m.group(1))
        unit = m.group(2)
        if "m" in unit or "million" in unit:
            aed = int(num * 1_000_000)
        elif "k" in unit:
            aed = int(num * 1_000)
        else:
            digits = re.sub(r"[^\d]", "", text)
            aed = int(digits) if digits else int(num)
        lead["budget_aed"] = aed
        lead["budget"] = f"{aed/1_000_000:.1f}M AED" if aed >= 1_000_000 else f"{aed:,} AED"

    for area in DUBAI_AREAS:
        if area.lower() in t and not lead.get("area"):
            lead["area"] = area

    if not lead.get("timeline_bucket"):
        if any(w in t for w in ["this month", "asap", "immediately", "now", "ready"]):
            lead["timeline_bucket"] = "immediate"
            lead["timeline"] = "this month"
        elif any(w in t for w in ["month", "soon", "few weeks"]):
            lead["timeline_bucket"] = "1-3 months"
            lead["timeline"] = "1-3 months"
        elif any(w in t for w in ["year", "later", "next year"]):
            lead["timeline_bucket"] = "3-6 months"
            lead["timeline"] = "3-6 months"
        elif any(w in t for w in ["browsing", "looking around", "just curious"]):
            lead["timeline_bucket"] = "browsing"
            lead["timeline"] = "just browsing"

    if not lead.get("buyer_type"):
        if "invest" in t:
            lead["buyer_type"] = "Investor"
        elif any(w in t for w in ["browsing", "curious", "maybe", "just looking", "exploring"]):
            lead["buyer_type"] = "Browsing"
        elif any(w in t for w in ["ready", "serious", "buy now", "this month",
                                  "live in", "to live", "move in", "family", "primary"]):
            lead["buyer_type"] = "Serious Buyer"

    if not lead.get("financing"):
        if "cash" in t:
            lead["financing"] = "cash"
        elif any(w in t for w in ["mortgage", "loan", "finance"]):
            lead["financing"] = "mortgage"

    return lead


def fallback_concierge(messages: list) -> dict:
    lead = {}
    for msg in messages:
        if msg["role"] == "user":
            lead = extract_signals(msg["content"], lead)

    if not lead.get("area"):
        reply = (f"Hi! Thanks for reaching out to {AGENCY}. I'm {CONCIERGE}. "
                 "Which area or community in Dubai are you interested in?")
    elif not lead.get("budget_aed"):
        reply = f"Great choice. What budget range are you working with (in AED)?"
    elif not lead.get("timeline_bucket"):
        reply = "Perfect. How soon are you looking to buy or move in?"
    elif not lead.get("buyer_type"):
        reply = "Got it. Are you buying to live in, to invest, or just exploring options right now?"
    elif not lead.get("financing"):
        reply = "Understood. Will this be a cash purchase or via mortgage?"
    else:
        reply = (f"Thank you! I have everything I need. One of our {AGENCY} "
                 "agents will reach out to you very shortly with tailored options.")

    complete = bool(lead.get("area") and lead.get("budget_aed")
                    and lead.get("timeline_bucket") and lead.get("buyer_type"))
    lead.setdefault("name", None)
    return {"reply": reply, "lead": lead, "stage_complete": complete}


# --------------------------------------------------------------------------- #
#  Routes                                                                      #
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    return render_template("index.html", agency=AGENCY, concierge=CONCIERGE,
                           live=bool(GROQ_API_KEY))


def make_whatsapp_link(phone: str, text: str) -> str:
    """Build a wa.me link that opens WhatsApp with the message pre-filled.

    No WhatsApp Business API needed — works today. The agent just taps send.
    For full auto-send (no tap), swap this for the WhatsApp Business API later.
    """
    from urllib.parse import quote
    return f"https://wa.me/{phone}?text={quote(text)}"


@app.route("/api/chat", methods=["POST"])
def chat():
    # --- rate limit per IP (protects Groq credits) ---
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()
    if is_rate_limited(ip):
        return jsonify({
            "reply": ("You've reached the demo message limit. "
                      "Please refresh later or contact us directly."),
            "lead": {}, "score": 0, "urgency": "—",
            "next_action": "", "summary": None, "complete": False,
            "rate_limited": True,
        }), 429

    data = request.get_json(force=True) or {}
    messages = data.get("messages", [])

    try:
        if GROQ_API_KEY:
            result = call_groq(messages)
        else:
            result = fallback_concierge(messages)
    except Exception as exc:  # graceful: fall back so the demo never breaks
        app.logger.warning("Groq call failed (%s); using fallback.", exc)
        result = fallback_concierge(messages)

    lead = result.get("lead", {}) or {}
    scoring = score_lead(lead)
    complete = bool(result.get("stage_complete"))

    payload = {
        "reply": result.get("reply", ""),
        "lead": lead,
        "score": scoring["score"],
        "urgency": scoring["urgency"],
        "next_action": scoring["next_action"],
        "summary": build_summary(lead, scoring) if complete else None,
        "complete": complete,
    }

    # --- on completion: route the lead + build the WhatsApp hand-off ---
    if complete:
        routing = route_lead(lead)
        summary = payload["summary"]
        wa_text = f"New qualified lead for {routing['agent']} ({AGENCY}):\n\n{summary}"
        payload["routing"] = {
            "agent": routing["agent"],
            "reason": routing["reason"],
            "whatsapp_link": make_whatsapp_link(routing["whatsapp"], wa_text),
        }

    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
