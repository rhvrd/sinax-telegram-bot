import os
import re
import requests
from flask import Flask, request
from openai import OpenAI

# ================== ENV VARS ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")     # ← BotFather token (در Render → Environment)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")     # ← OpenAI API key    (در Render → Environment)
SETUP_SECRET  = os.getenv("SETUP_SECRET")        # ← رمز موقت برای /setup و /unset

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing TELEGRAM_TOKEN or OPENAI_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# =============== PERSONA LOADER ===============
DEFAULT_SINAX_PROMPT = r"""
You are SinaX – a bilingual (FA/EN) industrial consultant for Iran/MENA.

FOCUS:
1) Tools & Hardware (power & hand tools, accessories, safety tools)
2) Automotive spare parts (ICE/Hybrid/EV)
(Also: welding, electrical/lighting/cabling, HVAC/plumbing, automation, lab/test, chemicals/lubes, paints/coatings, construction, safety/PPE.)

HARD RULES (STRICT):
- Default Persian unless user writes English.
- Max 10 lines OR 6 bullets.
- Always give a concrete best-guess diagnosis/steps even with limited info.
- Ask EXACTLY ONE precise follow-up tailored to user’s text (no generic “be specific”).
- No shopping links or live prices. Emphasize specs/selection/compatibility/safety.
- If user greets or is vague: 1-line greeting + ONE clarifying question.
- When user continues (“next question”), keep context from last turn if possible.

STANDARD FORMAT (when technical):
1) Summary (1 line)
2) Likely causes / Options (≤3)
3) Key checks (3–6)
4) Next action (1 line)
5) One precise follow-up (1 line)

REFERENCES (when useful): name standards/catalogs only (e.g., IEC 60745, Hilti Catalog).
""".strip()

SINAX_PROMPT = os.getenv("SINAX_PROMPT", "").strip()
SINAX_PROMPT_URL = os.getenv("SINAX_PROMPT_URL", "").strip()

def load_persona() -> str:
    # اگر در ENV متن مستقیم گذاشتی:
    if SINAX_PROMPT:
        return SINAX_PROMPT
    # اگر URL خام به متن دادی (مثل GitHub Gist Raw):
    if SINAX_PROMPT_URL:
        try:
            r = requests.get(SINAX_PROMPT_URL, timeout=10)
            if r.ok and r.text.strip():
                return r.text
        except Exception:
            pass
    # دیفالت
    return DEFAULT_SINAX_PROMPT

SYSTEM_PROMPT_SINAX = load_persona()

# =============== HELPERS ======================
def detect_lang(s: str) -> str:
    return "fa" if re.search(r"[\u0600-\u06FF]", s or "") else "en"

def _extract_text(resp) -> str:
    # سازگار با نسخه‌های مختلف SDK
    try:
        t = (resp.output_text or "").strip()
        if t:
            return t
    except Exception:
        pass
    try:
        for block in getattr(resp, "output", []) or []:
            for c in block.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    tx = (c.get("text") or "").strip()
                    if tx:
                        return tx
    except Exception:
        pass
    return ""

# فالبک کوتاه و کاربردی اگر مدل چیزی برنگرداند
def _fallback_short(user_text: str, lang: str) -> str:
    fa = (lang == "fa")
    if fa:
        return (
            "🔧 خلاصه: احتمال ایراد رایج در تنظیم/مصرفی‌ها.\n"
            "📋 علل محتمل:\n"
            "• عدم کالیبراسیون/لقی\n"
            "• مصرفیِ فرسوده (تیغه/زغال/یاتاقان)\n"
            "• تطابق‌نبودن ابزار/متریال/ولتاژ\n"
            "🧩 بررسی‌ها: هم‌راستایی، سفتی پیچ‌ها، سلامت مصرفی‌ها، ولتاژ ورودی\n"
            "➡ گام بعدی: یک سرویس سریع + کالیبراسیون انجام بده سپس تست کن.\n"
            "❓ سؤال: نام/مدل دقیق و علامت خرابی را بنویس."
        )
    else:
        return (
            "Likely a common setup/consumable issue.\n"
            "- Check alignment, fasteners, consumables, and input voltage.\n"
            "Next: do a quick service + calibration, then re-test.\n"
            "Question: exact model & symptom?"
        )

def ask_openai(user_text: str) -> str:
    lang = detect_lang(user_text)
    lang_hint = "پاسخ کوتاه، بولت‌وار و دقیق به فارسی." if lang == "fa" else "Answer briefly with precise bullets."
    try:
        resp = client.responses.create(
            model="gpt-5-mini",
            instructions=f"{SYSTEM_PROMPT_SINAX}\n\nLanguage rule: {lang_hint}",
            input=user_text,
            max_output_tokens=260
        )
        out = _extract_text(resp).strip()
        if out:
            return out
    except Exception as e:
        print("OPENAI_ERROR:", repr(e))
    return _fallback_short(user_text, lang)

def tg_send(chat_id: int, text: str):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20
    )

# =============== WEBHOOK ======================
@app.route("/telegram-webhook", methods=["GET", "POST"])
def telegram_webhook():
    if request.method == "GET":
        return "ok"  # health for webhook path

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

    r = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": answer},
        timeout=20
    )
    print("TG_SEND_STATUS:", r.status_code, r.text)
    return "ok"

# =============== HEALTH =======================
@app.get("/")
def health():
    return "SINAX is up"

# ========== SET/UNSET WEBHOOK (TEMP) ==========
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
