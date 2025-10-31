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

HARD RULES:
- Persian by default; if user writes English → English.
- Max 6 bullets OR 10 lines.
- ALWAYS give a concrete best-guess diagnosis & steps even with little info.
- EXACTLY ONE precise follow-up at the end, tailored to the user’s text.
- NEVER ask for generic details repeatedly. Do not say “be more specific” unless user’s message is empty.
- No shopping links or live prices.
- Format (if technical):
  1) Summary (1 line)
  2) Likely causes / Options (≤3)
  3) Key checks (3–6)
  4) Next action (1 line)
  5) One precise follow-up question (1 line)
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

def _rule_based_fallback(user_text: str, lang: str) -> str:
    t = (user_text or "").strip()
    fa = (lang == "fa")

    def fa_wrap(summary, causes, checks, next_step, question):
        # ساختار کوتاه فارسی
        lines = []
        lines.append(f"🔧 خلاصه: {summary}")
        if causes:
            lines.append("📋 علل محتمل:")
            for c in causes[:3]: lines.append(f"• {c}")
        if checks:
            lines.append("🧩 مواردی که باید چک شود:")
            for c in checks[:6]: lines.append(f"• {c}")
        if next_step: lines.append(f"➡️ گام بعدی: {next_step}")
        if question: lines.append(f"❓ سؤال تکمیلی: {question}")
        return "\n".join(lines)

    # --- الگوی فارسی‌بُر و زاویه ---
    if ("فارسی" in t and "بر" in t) or "C12RSH" in t or "زاویه" in t:
        return fa_wrap(
            "دقت زاویه اره فارسی‌بُر افت کرده؛ احتمالاً از هم‌ترازی یا لقی قطعات است.",
            [
                "شل‌شدن میز گردان/ریل‌های کشویی یا لقی بلبرینگ محور",
                "کالیبره نبودن گونیا/گِیج 45° و 90°",
                "تیغه نابالانس/کند یا دیسک تاب‌دار"
            ],
            [
                "با خط‌کش/گونیای دقیق، 90° و 45° را نسبت به تیغه و فنس چک کن",
                "ریل‌های کشویی را از نظر لقی بررسی و پیچ‌های پایه را سفت کن",
                "تیغه را از نظر تاب‌داشتن و تیزی بررسی؛ در صورت نیاز تعویض/بالانس",
                "مارک‌های توقف (detent) میز را دوباره تنظیم کن"
            ],
            "اول کالیبراسیون 90°/45° را انجام بده؛ اگر لقی باقی بود، یاتاقان/ریل سرویس شود.",
            "مدل دقیق دستگاه و نوع/قطر تیغه فعلی چیست؟"
        ) if fa else "Miter saw angle inaccuracy: check table detents, rail play, fence/blade squareness, and blade runout; then re-calibrate 90°/45°. What exact model/blade are you using?"

    # --- الگوی فرز/سنگ فرز وقتی «نمی‌برد/قدرت کم است» ---
    if ("فرز" in t or "سنگ" in t) and ("قدرت" in t or "نمی" in t or "کار" in t):
        return fa_wrap(
            "افت توان/عدم برش مناسب در فرز.",
            [
                "زغال موتور کوتاه یا کالکتور سیاه‌شده",
                "گیرکردن یاتاقان یا گریس خشک",
                "کابل/سوئیچ نیم‌سوز یا ولتاژ ورودی افت‌دار"
            ],
            [
                "طول زغال و وضعیت کالکتور را چک و پاک‌سازی کن",
                "صدای غیرعادی/لرزش = احتمال خرابی بلبرینگ",
                "افت ولتاژ پریز/کابل رابط را اندازه بگیر",
                "دیسک مناسب متریال استفاده کن"
            ],
            "زغال و دیسک را عوض کن و یک تست با ولتاژ مطمئن بگیر.",
            "مدل دقیق فرز و نوع دیسک فعلی چیست؟"
        ) if fa else "Angle grinder low power: check brushes/commutator, bearings, mains voltage, and disc type. What exact model/disc?"

    # --- الگوی باتری/شارژی «شارژ نمی‌شود/زود خالی می‌شود» ---
    if ("باتری" in t or "شارژی" in t) and ("شارژ" in t or "خالی" in t):
        return fa_wrap(
            "مشکل در پک باتری/شارژر.",
            [
                "سلول‌های ضعیف/عدم بالانس پک",
                "خرابی ترمیستور/برد BMS",
                "شارژر ناسازگار یا معیوب"
            ],
            [
                "ولتاژ پک و هر سلول را اندازه بگیر (اگر دسترسی داری)",
                "با شارژر دیگری تست متقاطع کن",
                "دمای کارکرد حین شارژ/دشارژ را چک کن"
            ],
            "با شارژر سالم تست کن؛ اگر پایدار نشد، پک نیازمند سرویس/تعویض است.",
            "ولتاژ نامی، ظرفیت (Ah) و مدل پک/شارژر چیست؟"
        ) if fa else "Battery/charger issue: test with known-good charger, check pack/BMS and cell balance."

    # --- الگوی دیفالت کوتاه و کاربردی ---
    if fa:
        return fa_wrap(
            "بر اساس توضیحت، یک ایراد رایج فنی محتمل است.",
            ["فرسودگی/لقی قطعات مصرفی", "عدم تنظیم/کالیبراسیون", "تطابق‌نبودن ابزار/متریال/ولتاژ"],
            ["تمیزی و سفتی قطعات متحرک", "ولتاژ/جریان ورودی", "سلامت مصرفی‌ها (تیغه/زغال/یاتاقان)"],
            "اول یک سرویس سریع و کالیبراسیون انجام بده، سپس تست مجدد.",
            "مدل دقیق تجهیز و علائم ایراد را در یک جمله بفرست."
        )
    else:
        return "Likely a common mechanical/electrical setup issue. Check basics (power, consumables, alignment), do a quick service, then re-test. What exact model/symptom?"

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

    # اگر خروجی مدل خالی/خطا بود، از فالبک قاعده‌محور استفاده کن
    return _rule_based_fallback(user_text, lang)

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
