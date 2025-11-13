import os
import re
import requests
from flask import Flask, request
from openai import OpenAI

# ================== ENV VARS ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")     # BotFather token (Render → Environment)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")     # OpenAI API key    (Render → Environment)
SETUP_SECRET  = os.getenv("SETUP_SECRET")        # Optional key for /setup & /unset

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing TELEGRAM_TOKEN or OPENAI_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# =============== DEFAULT PERSONA FOR SINAX ===============
DEFAULT_SINAX_PROMPT = r"""
You are SinaX – a bilingual (FA/EN) industrial consultant for Iran/MENA.

FOCUS:
1) Tools & Hardware (power & hand tools, accessories, safety tools)
2) Automotive spare parts (ICE/Hybrid/EV)
(Also: welding, electrical/lighting/cabling, HVAC/plumbing, automation, lab/test, chemicals/lubes, paints/coatings, construction, safety/PPE.)

HARD RULES (STRICT):
- Default Persian unless user writes English.
- Answers must stay short but technically dense: max 8–10 lines OR 6 bullets.
- Avoid generic advice; every bullet should contain a concrete technical point (component name, failure mode, spec range, test method, etc.).
- Always give a concrete best-guess diagnosis and practical steps even with limited info.
- Prefer root-cause thinking (why it happens) over superficial tips.
- Ask EXACTLY ONE precise follow-up tailored to user’s text (e.g. missing spec, model, environment).
- No shopping links or live prices.
- If user is vague: 1-line greeting + ONE focused clarifying question.
- Keep context from the last turn when possible.

STANDARD FORMAT (technical replies, still short):
1) Summary (۱–۲ جمله‌ی فنی، بدون حاشیه)
2) Likely causes / Options (≤3 bullets – هرکدام با علت فنی یا مکانیزم خرابی)
3) Key checks (3–6 bullets – تست‌ها یا بازرسی‌های مشخص، ترجیحاً با ابزار/واحد اندازه‌گیری)
4) Next action (1 خط – گام عملی بعدی)
5) One precise follow-up (1 خط – فقط یک سؤال دقیق)
""".strip()

SINAX_PROMPT = os.getenv("SINAX_PROMPT", "").strip()
SINAX_PROMPT_URL = os.getenv("SINAX_PROMPT_URL", "").strip()

def load_persona() -> str:
    if SINAX_PROMPT:
        return SINAX_PROMPT
    if SINAX_PROMPT_URL:
        try:
            r = requests.get(SINAX_PROMPT_URL, timeout=10)
            if r.ok and r.text.strip():
                return r.text
        except Exception:
            pass
    return DEFAULT_SINAX_PROMPT

SYSTEM_PROMPT_SINAX = load_persona()

# =============== HELPERS ======================
def detect_lang(s: str) -> str:
    return "fa" if re.search(r"[\u0600-\u06FF]", s or "") else "en"

def _extract_text(resp) -> str:
    try:
        t = (resp.output_text or "").strip()
        if t:
            return t
    except:
        pass

    try:
        for block in getattr(resp, "output", []) or []:
            for c in block.get("content", []):
                if c.get("type") in ("text", "output_text"):
                    tx = (c.get("text") or "").strip()
                    if tx:
                        return tx
    except:
        pass

    return ""

def _fallback_short(user_text: str, lang: str) -> str:
    if lang == "fa":
        return (
            "🔧 احتمال ایراد رایج در تنظیم/مصرفی‌ها.\n"
            "• عدم کالیبراسیون/لقی\n"
            "• مصرفی فرسوده (تیغه/زغال/یاتاقان)\n"
            "• تطابق‌نبودن ابزار/متریال/ولتاژ\n"
            "🧩 بررسی: هم‌راستایی، پیچ‌ها، مصرفی‌ها، ولتاژ\n"
            "➡ یک سرویس سریع + کالیبراسیون انجام بده.\n"
            "❓ مدل دقیق ابزار چیست؟"
        )
    return (
        "Likely a setup/consumable issue.\n"
        "Check alignment, fasteners, consumables, voltage.\n"
        "Next: quick service + calibration.\n"
        "Question: exact model?"
    )

# =============== MAIN OPENAI CALL =================
def ask_openai(user_text: str) -> str:
    lang = detect_lang(user_text)
    lang_hint = (
        "پاسخ کوتاه، اما فنی، بولت‌وار و دقیق به فارسی بده؛ روی علت‌های محتمل، تست‌های عملی و گام بعدی تمرکز کن."
        if lang == "fa"
        else "Answer briefly but technically: compact bullets focusing on likely causes, practical checks, and next actions."
    )

    try:
        resp = client.responses.create(
            model="gpt-4o-mini",    # UPDATED & CORRECT
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

# =============== TELEGRAM SEND ====================
def tg_send(chat_id: int, text: str):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20
    )

# =============== WEBHOOK HANDLER ==================
@app.route("/telegram-webhook", methods=["GET", "POST"])
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

    # ----- custom /start message -----
    if user_text.strip().startswith("/start"):
        welcome = (
            "سلام! چطور می‌توانم به شما کمک کنم؟\n"
            "آیا سؤال خاصی در مورد ابزار برقی و دستی یا قطعات خودرو و موتور سیکلت دارید؟"
        )
        tg_send(chat_id, welcome)
        return "ok"
    # ---------------------------------

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

# =============== HEALTH CHECK =====================
@app.get("/")
def health():
    return "SINAX is up"

# =============== SELF SETUP HELPERS ===============
@app.get("/setup")
def setup_webhook():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)

    url = f"https://{request.host}/telegram-webhook"
    r = requests.get(
        f"{TELEGRAM_API}/setWebhook",
        params={"url": url},
        timeout=20
    )
    return r.text

@app.get("/unset")
def unset_webhook():
    key = request.args.get("key")
    if not SETUP_SECRET or key != SETUP_SECRET:
        return ("forbidden", 403)

    r = requests.get(
        f"{TELEGRAM_API}/deleteWebhook",
        timeout=20
    )
    return r.text
