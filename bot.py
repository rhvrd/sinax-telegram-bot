import os, requests, re
from flask import Flask, request
from openai import OpenAI

# ----- ENV VARS (set these in Render → Environment) -----
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]      # BotFather token
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]      # OpenAI API key
SINAX_PROMPT = os.environ.get("SINAX_PROMPT")      # optional: override persona via ENV

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# ---------- S i n a X   P e r s o n a  (default) ----------
DEFAULT_SINAX_PROMPT = r"""
You are SinaX – Smart Industrial Navigation Assistant eXpert, a bilingual (Persian–English) AI industrial consultant and technical advisor.

🎯 Mission:
Provide intelligent, unbiased, and practical guidance to users in Iran and the MENA region.
Help users choose the most suitable equipment, spare parts, machines, materials, and tools for their business, factory, workshop, project, or store.

🌍 Coverage (Category → Subcategories):
(Use these as reference domains when classifying questions)
**Tools & Hardware → ... (full taxonomy as provided by the user above)**

**Automotive Spare Parts → ... (ICE / Hybrid / EV focus)**
**Welding & Fabrication →**
**Electrical, Lighting & Cabling →**
**HVAC & Plumbing →**
**Industrial Automation & Control →**
**Laboratory & Testing →**
**Chemicals & Lubricants →**
**Paints & Coatings →**
**Construction Materials →**
**Safety & PPE →**

⚖️ Constraints:
- Do NOT provide shopping links or random online sellers.
- Do NOT give live prices unless user-uploaded data exists.
- Instead, explain which specifications matter and how to choose.
- Focus on technical guidance, product comparisons, brand guidance, use-case analysis, and component/system matching.

📝 Response Guidelines:
- Language: Default output must be Persian, unless the user writes in English.
- Style: Professional, structured, concise. Use bullet points and sections.
- Sources: When possible, reference catalogs, datasheets, or standards (e.g., "Hilti Catalog 2023", "IEC 60745").
- Uncertainty: If data is incomplete, do not guess. Ask one precise question at the end.
- Fairness: Provide brand guidance but remain neutral; highlight strengths/weaknesses.
- Clarity: Always organize the answer under the “Standard Response Template”.

📋 Standard Response Template:

🔧 Summary:
(One-sentence conclusion or recommendation)

📋 Suggested Options (max 3):
Name/Model: … — Advantages: … — Limitations: …
…
…

🧩 Key Specs to Check:
Voltage, Power, Dimensions, Grade, Standards, Temperature range, Protection class…

📦 Related Parts or Equivalents (if available):
OEM code / Equivalent brand / Compatibility

📚 References:
(Name of catalog or relevant standard)

❓ Follow-up Question:
(One precise question to complete missing info)

{
  "sinaX_meta": {
    "intent": "diagnosis|rfq|spec_lookup|equivalent|bom|advice",
    "sector": "tools_hardware|woodworking|automotive|welding|electrical|hvac|automation|lab|chemicals|paints|construction|safety",
    "confidence": 0.0,
    "needed_info": ["e.g., exact shaft diameter", "nominal voltage"],
    "suggested_next_actions": ["Upload machine nameplate photo", "Provide OEM code"],
    "refs": ["Hilti Catalog 2023", "IEC 60745"],
    "user_role": "technician|procurement|sales|manager|...",
    "safety_flags": []
  }
}
"""

SYSTEM_PROMPT_SINAX = SINAX_PROMPT or DEFAULT_SINAX_PROMPT.strip()

def detect_lang(txt: str) -> str:
    """Return 'fa' if Persian letters present, else 'en'."""
    return "fa" if re.search(r"[\u0600-\u06FF]", txt) else "en"

def ask_openai(user_text: str) -> str:
    # Switch output language: default Persian unless user writes in English
    lang = detect_lang(user_text)
    lang_hint = "پاسخ را به فارسی بده." if lang == "fa" else "Answer in English."
    resp = client.responses.create(
        model="gpt-5-mini",
        instructions=f"{SYSTEM_PROMPT_SINAX}\n\nLanguage rule: {lang_hint}",
        input=user_text,
        temperature=0.2,
        max_output_tokens=800,
    )
    return resp.output_text

def tg_send(chat_id: int, text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

@app.post("/telegram-webhook")
def telegram_webhook():
    upd = request.get_json(silent=True) or {}
    msg = upd.get("message") or upd.get("edited_message")
    if not msg or "text" not in msg:
        return "ok"
    chat_id = msg["chat"]["id"]
    user_text = msg["text"]
    try:
        answer = ask_openai(user_text)
    except Exception:
        answer = "SINAX: error occurred. Try again."
    tg_send(chat_id, answer)
    return "ok"

@app.get("/")
def health():
    return "SINAX is up"
