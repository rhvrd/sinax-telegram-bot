import os, re, requests
from flask import Flask, request
from openai import OpenAI

# -------- ENV (مقادیر محیطی از Render خوانده می‌شود) --------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")       # ← توکن BotFather اینجا خوانده می‌شود
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")       # ← کلید API از سایت OpenAI
SETUP_SECRET  = os.getenv("SETUP_SECRET")          # ← رمز مخفی دلخواه برای setup/unset

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing TELEGRAM_TOKEN or OPENAI_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# -------- شخصیت SinaX --------
DEFAULT_SINAX_PROMPT = r"""
You are SinaX, FA/EN industrial advisor focused on:
1) Power/hand tools & accessories
2) Automotive spare parts (ICE/Hybrid/EV)

Rules (STRICT):
- Persian by default; if user writes English → English.
- Max 6 bullets OR 10 lines.
- Always give best-guess diagnosis/steps even with limited info.
- Ask EXACTLY ONE precise follow-up question at the end.
- No shopping links or live prices.
"""
SYSTEM_PROMPT_SINAX = os.getenv("SINAX_PROMPT", DEFAULT_SINAX_PROMPT).strip()

def detect_lang(s: str) -> str:
    return "fa" if re.search(r"[\u0600-\u06FF]", s or "") else "en"

def _extract_text(resp) -> str:
    try:
        t = (resp.output_text or "").strip()
        if t: return t
    except Exception:
        pass
    try:
        for block in resp.output:
            for c in block.content:
                if c.get("type") in ("output_text","text"):
                    tx = (c.get("text") or "").strip()
                    if tx: return tx
    except Exception:
        pass
    return ""

def ask_openai(user_text: str) -> str:
    lang = detect_lang(user_text)
    lang_hint = "پاسخ کوتاه، بولت‌وار و دقیق به فارسی." if lang == "fa" else "Answer briefly with precise bullets."
    resp = client.responses.create(
        model="gpt-5-mini",
        instructions=f"{SYSTEM_PROMPT_SINAX}\n\nLanguage rule: {lang_hint}",
        input=user_text,
        max_output_tokens=240
    )
    out = _extract_text(resp)
    return out or ("نام/مدل ابزار یا قطعه را بنویس تا دقیق‌تر راهنمایی کنم." if lang=="fa"
                   else "Share tool/part name & model for a precise answer.")

def tg_send(chat_id: int, text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage",
                  json={"chat_id": chat_id, "text": text}, timeout=20)

@app.route("/telegram-webhook", methods=["GET","POST"])
def telegram_webhook():
    if request.method == "GET":
        return "ok"

    upd = request.get_json(silent=True) or {}
    print("TG_UPDATE:", upd)
    msg = upd.get("message") or upd.get("edited_message")
    if not msg or "text" not in msg:
        return "ok"

    chat_id = msg["chat"]["id"]
    user_text = msg["text"]

    try:
        answer = ask_openai(user_text)
    except Exception as e:
        print("OPENAI_ERROR:", repr(e))
        answer = "SinaX: خطا رخ داد. دوباره تلاش کن."

    r = requests.post(f"{TELEGRAM_API}/sendMessage",
                      json={"chat_id": chat_id, "text": answer}, timeout=20)
    print("TG_SEND_STATUS:", r.status_code, r.text)
    return "ok"

@app.get("/")
def health():
    return "SINAX is up"

@app.get("/setup")
def setup_webhook():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)
    url = f"https://{request.host}/telegram-webhook"
    r = requests.get(f"{TELEGRAM_API}/setWebhook", params={"url": url}, timeout=20)
    return r.text

@app.get("/unset")
def unset_webhook():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)
    r = requests.get(f"{TELEGRAM_API}/deleteWebhook", timeout=20)
    return r.text
