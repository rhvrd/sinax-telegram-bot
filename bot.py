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
You are SinaX, a bilingual (FA/EN) industrial advisor for Iran/MENA with PRIORITY on:
1) Tools & Hardware (power tools, hand tools, accessories, safety tools)
2) Automotive spare parts (engine/powertrain, brake, suspension, electrical incl. Hybrid/EV)

Rules:
- Default Persian unless user writes English.
- Keep answers SHORT: ≤10 lines (یا ≤6 بولت).
- No shopping links / live prices. Focus on specs, selection, compatibility, safety/standards.
- Use layout ONLY for technical questions:
  1) Summary (1 line)
  2) Suggested options (≤3) – name + 1 advantage + 1 limit
  3) Key specs to check (3–6 bullets)
  4) Follow-up question (1 line)
- If the user greets or sends a vague message, reply with a one-line greeting + one precise question to continue.
- When unclear, ask exactly ONE clarifying question.
"""
SYSTEM_PROMPT_SINAX = os.getenv("SINAX_PROMPT", DEFAULT_SINAX_PROMPT).strip()

def detect_lang(txt: str) -> str:
    return "fa" if re.search(r"[\u0600-\u06FF]", txt) else "en"

# فقط یک‌بار برای هر chat_id تذکر می‌دهیم
ASKED_CLARIFY = set()
GREET_FA = {"سلام","درود","سلاام","salam"}
GREET_EN = {"hi","hello","hey"}
TECH_HINTS = {"خراب","تعویض","عوض","گیر","کارنمیکنه","کار نمی‌کنه","قطع","صدا","سوخته","روشن","خاموش","تیغه","دیسک","بلبرینگ","باتری","ولتاژ","توان","کابل"}

def quick_reply_if_small(text: str, chat_id: int):
    t = text.strip()
    low = t.lower()

    # فقط سلامِ خالی → پاسخ یک‌خطی
    if (low in GREET_EN) or (t in GREET_FA):
        return "سلام! روی کدام مورد کمک می‌خواهی؟ (مثلاً: «فرز انگشتی ۷۲۰وات»، «دیسک ترمز ۲۰۶»، «باتری ۱۸V ماکیتا»)"

    # اگر قبلاً یک‌بار تذکر داده‌ایم، دیگر تکرار نکن
    if chat_id in ASKED_CLARIFY:
        return None

    # اگر پیام خیلی مبهم/کوتاه بود و نشانه فنی هم ندارد → فقط یک‌بار تذکر
    if (len(t) <= 6 or len(t.split()) <= 2) and not any(w in t for w in TECH_HINTS):
        ASKED_CLARIFY.add(chat_id)
        return "لطفاً دقیق‌تر بگو چه ابزاری/قطعه‌ای مدنظرت است (برند/مدل/توان/ولتاژ)."

    return None



def ask_openai(user_text: str, chat_id: int) -> str:
    # روتر: فقط یک‌بار تذکر؛ بعد از آن مستقیماً برو سراغ مدل
    qr = quick_reply_if_small(user_text, chat_id)
    if qr:
        return qr

    lang = "fa" if re.search(r"[\u0600-\u06FF]", user_text) else "en"
    lang_hint = "پاسخ را کوتاه و بولت‌وار به فارسی بده." if lang=="fa" else "Answer briefly in English with bullets."

    resp = client.responses.create(
        model="gpt-5-mini",
        instructions=f"{SYSTEM_PROMPT_SINAX}\n\nLanguage rule: {lang_hint}",
        input=user_text,
        max_output_tokens=300
    )
    return resp.output_text or "باشه—لطفاً چند جزئیات از ابزار/قطعه بگو (برند/مدل/توان/ولتاژ)."




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
        # تغییر مهم: chat_id هم می‌دهیم تا روتر فقط یک‌بار درخواست توضیح بدهد
        answer = ask_openai(user_text, chat_id)

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
