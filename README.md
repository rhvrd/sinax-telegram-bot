SinaX – Smart Industrial Navigation Assistant eXpert (Telegram Bot)

SinaX is a bilingual (Persian–English) AI industrial consultant and technical advisor designed for Iran & MENA users. It helps select and compare equipment, spare parts, machines, materials, tools, lighting, electrical, HVAC, automation, and more—delivering concise, actionable, safety-aware guidance.

Tech stack: Python · Flask (webhook) · Telegram Bot API · OpenAI API (gpt-5-mini by default)
Hosting: Works great on Render (free tier).

✨ Features

Bilingual: Persian by default; replies in English if the user writes in English.

Industrial domains: Tools & Hardware, Automotive (ICE/Hybrid/EV), Welding, Electrical/Lighting, HVAC & Plumbing, Automation, Lab/Testing, Chemicals & Lubricants, Paints & Coatings, Construction, Safety & PPE.

Structured answers using a Standard Response Template (Summary → Options → Key Specs → Equivalents → References → Follow-up).

Safety/Standards hints (IEC/ISO/ASME/NEC) without substituting formal HSE review.

Configurable persona via SINAX_PROMPT (no redeploy needed).

📁 Repository Structure
sinax-telegram-bot/
├─ bot.py                 # Flask webhook + OpenAI call (gpt-5-mini)
├─ requirements.txt       # flask, requests, openai, gunicorn
└─ README.md              # this file


Optional files you can add:

runtime.txt               # e.g. python-3.11 (Render)
.gitignore                # include .env, __pycache__/

🤖 SinaX Persona (Default)

Mission: Practical, unbiased guidance for industrial selection and troubleshooting in Iran/MENA.

Constraints:

No shopping links or random sellers.

No live prices unless user supplies data.

Focus on specs, selection criteria, comparisons, compatibility, and safe use.

Response Style: Professional, concise, bullet-based, Persian by default.

Template:

🔧 Summary

📋 Suggested Options (≤3): Name/Model — Advantages — Limitations

🧩 Key Specs to Check

📦 Related Parts / Equivalents

📚 References (catalogs/standards)

❓ Follow-up Question

Meta (internal guidance): sinaX_meta.intent, sector, confidence, needed_info, refs, user_role, safety_flags.

You can override the persona with the SINAX_PROMPT env var.

🚀 Quick Start (Render – recommended)

Fork/clone this repo (or create your own with the same files).

In Render
 → New → Web Service → connect your GitHub repo.

Build/Start

Build command:

pip install -r requirements.txt


Start command:

gunicorn bot:app --bind 0.0.0.0:$PORT


Environment Variables (Render → Environment):

TELEGRAM_TOKEN = your BotFather token (e.g. 123456:AA...)

OPENAI_API_KEY = your OpenAI API key (e.g. sk-...)

(optional) SINAX_PROMPT = custom persona text

Deploy (if editing after creation: Manual Deploy → Clear cache & deploy).

Set Telegram webhook (replace token & domain):

https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<your-render-url>/telegram-webhook


Check status:

https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo

🧪 Local Development (optional)

You need a public HTTPS tunnel (e.g., ngrok) to receive Telegram webhooks locally.

Create a local .env (do not commit):

TELEGRAM_TOKEN=123456:ABC...
OPENAI_API_KEY=sk-...


Install deps:

pip install -r requirements.txt


Run Flask:

python -m flask --app bot run --port 8080


Expose via ngrok and set webhook:

ngrok http 8080
curl "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook?url=https://<ngrok-url>/telegram-webhook"

🛡️ Security & Secrets

Never hard-code tokens/keys in bot.py.

Use Render Environment Variables or a local .env (git-ignored).

If you accidentally exposed a key, revoke/rotate immediately.

Limit logs; don’t log user secrets/tokens.

🧠 Model & Tuning

Default model: gpt-5-mini (fast & cost-effective for Telegram).

Temperature: 0.2 (stable/engineering tone).

Output tokens: ≤ 800 (Telegram-friendly).

For tough requests, you can temporarily switch to gpt-5 per request.

Example toggle (pseudo):

model = "gpt-5-mini"
if len(user_text) > 700 or any(k in user_text.lower() for k in ["root cause","asme","iec","trade-off"]):
    model = "gpt-5"

❓FAQ

Q: Where do I put tokens?
A: Render → Environment → add TELEGRAM_TOKEN, OPENAI_API_KEY. Save → Redeploy.

Q: My service deployed, but the bot doesn’t reply.

Ensure webhook is set to .../telegram-webhook.

Check Render Logs for errors.

Verify your OpenAI billing/limits and token names.

Q: Can I connect to my Custom GPT page directly?
A: No. Custom GPTs don’t expose an API. We replicate the persona via SINAX_PROMPT.

🧩 Troubleshooting

Create requirements.txt error (Render)
Ensure requirements.txt is in the repo root and named exactly requirements.txt.

404/405 on webhook
Route must be POST /telegram-webhook and your webhook must point there.

401/403 from OpenAI
Check API key & billing status.

Timeout/slow
Keep responses concise; consider gpt-5-mini; reduce max_output_tokens.

📝 License

You own your content and branding. This example code can be used in your projects; consider adding your preferred license (e.g., MIT).

🙌 Credits

Telegram Bot API

OpenAI API

Flask + Gunicorn

Thanks to the SinaX team for the domain taxonomy and persona.
