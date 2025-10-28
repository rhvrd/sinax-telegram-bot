import os, re, requests
from flask import Flask, request
from openai import OpenAI

# ===== ENV VARS (set in Render → Environment) =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")     # BotFather token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")     # OpenAI API key
SETUP_SECRET  = os.getenv("SETUP_SECRET")        # temporary secret for /setup /unset

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing env vars: TELEGRAM_TOKEN / OPENAI_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
import openai as _oai
import json

# نسخه SDK را در لاگ نشان بده
print("OPENAI_SDK_VERSION:", getattr(_oai, "__version__", "unknown"))

# --- DIAG: تست مستقیم OpenAI از طریق مرورگر (محافظت با همان SETUP_SECRET) ---
@app.get("/diag")
def diag():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)
    try:
        r = client.responses.create(
            model="gpt-5-mini",
            instructions="Say OK",
            input="ping",
            max_output_tokens=16,
        )
        return {"ok": True, "output": r.output_text}
    except Exception as e:
        # خروجی خطا را واضح برگردان
        return {"ok": False, "error": repr(e)}

# ===== SinaX persona =====
DEFAULT_SINAX_PROMPT = r"""
You are SinaX – Smart Industrial Navigation Assistant eXpert, a bilingual (Persian–English) AI industrial consultant and technical advisor.
Mission: practical, unbiased guidance for Iran/MENA.
Constraints: no shopping links, no live prices; focus on specs, selection criteria, compatibility, safety hints (IEC/ISO/ASME/NEC).
Response style: Persian by default (English if user writes English); concise, structured.
Template: Summary; Suggested Options (≤3); Key Specs; Equivalents; References; Follow-up Question.
"""
SYSTEM_PROMPT_SINAX = os.getenv("SINAX_PROMPT", DEFAULT_SINAX_PROMPT).strip()

def detect_lang(txt: str) -> str:
    return "fa" if re.search(r"[\u0600-\u06FF]", txt) else "en"

def ask_openai(user_text: str) -> str:
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

# ===== TELEGRAM WEBHOOK =====
@app.route("/telegram-webhook", methods=["POST","GET"])
def telegram_webhook():
    if request.method == "GET":
        return "ok"  # تست مرورگر / پینگ
    upd = request.get_json(silent=True) or {}
    print("TG_UPDATE:", upd)  # ← در Logs ببین
    msg = upd.get("message") or upd.get("edited_message")
    if not msg or "text" not in msg:
        return "ok"
    chat_id = msg["chat"]["id"]
    user_text = msg["text"]
    try:
        answer = ask_openai(user_text)
    except Exception as e:
        print("OPENAI_ERROR:", repr(e))
        answer = "SINAX: error occurred. Try again."
    r = requests.post(f"{TELEGRAM_API}/sendMessage",
                      json={"chat_id": chat_id, "text": answer}, timeout=20)
    print("TG_SEND_STATUS:", r.status_code, r.text)  # پاسخ تلگرام
    return "ok"


# ===== HEALTH =====
@app.get("/")
def health():
    return "SINAX is up"

# ===== TEMP: SET/UNSET WEBHOOK (remove after use) =====
@app.get("/setup")
def setup_webhook():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)
    target = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url=https://{request.host}/telegram-webhook"
    r = requests.get(target, timeout=20)
    return r.text

@app.get("/unset")
def unset_webhook():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)
    target = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"
    r = requests.get(target, timeout=20)
    return r.text
