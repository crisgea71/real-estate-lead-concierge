# AI Real Estate Lead Concierge

An AI concierge that replies to real estate leads **instantly**, qualifies them
(area, budget, timeline, readiness), scores them, and hands the right agent a
clean, ready-to-act summary — so agents only spend time on serious buyers.

Built for high-volume agencies and developers who lose leads because nobody
replies fast enough. A lead contacted within minutes converts far better than
one contacted an hour later — this closes that gap, 24/7.

> Demo agency: **Marina Homes Dubai**. Concierge name: **Aya**.

## What it does

1. **Instant reply** — greets the lead the moment they message.
2. **Qualifies** — asks area, budget, timeline and readiness, one question at a time.
3. **Scores the lead** — deterministic 0–100 score + urgency (High / Medium / Low).
4. **Routes to the right agent** — by area, with round-robin fallback.
5. **Hands off on WhatsApp** — one tap sends the qualified lead to that agent.

The lead-intelligence panel fills in **live** as the conversation happens.

## Tech

- **Backend:** Flask (Python)
- **AI:** Groq API (free tier) — `llama-3.3-70b-versatile`
- **Frontend:** vanilla HTML/CSS/JS (no build step)
- **Scoring:** deterministic, in Python (consistent, explainable)
- **Rate limiting:** 25 messages per IP per day (protects API credits)
- **Deploy:** Render

Runs with **zero setup** even without an API key — a built-in rule-based
fallback keeps the demo working, so you can clone and see it instantly.

## Run locally

```bash
git clone <your-repo-url>
cd real-estate-lead-concierge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then paste your free Groq key
export $(cat .env | xargs)

python3 app.py
# open http://localhost:5000
```

Get a free Groq key (no card) at https://console.groq.com/keys

## Deploy to Render

1. Push this repo to GitHub.
2. On render.com → **New → Web Service** → connect the repo.
3. Render reads `render.yaml` automatically. Add your `GROQ_API_KEY` in the
   dashboard (Environment tab).
4. Deploy. Live in ~2 minutes.

## Roadmap (post-demo, per client)

- WhatsApp Business API (full auto-send, bilingual EN/AR)
- Real calendar booking (Cal.com / Google Calendar)
- CRM sync + lead persistence
- Property matching from the agency's live feed

## License

MIT
