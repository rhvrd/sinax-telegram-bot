import os, re, requests
from flask import Flask, request
from openai import OpenAI

# --- حافظهٔ کوتاه داخل رم (با ری‌استارت پاک می‌شود) ---
CHAT_STATE = {}  # chat_id -> {"topic": "...", "last_model":"...", "last_blade_mm": 0}

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

    import os, requests

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
"""


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

import re

def _parse_blade(text: str) -> int:
    """
    تلاش برای فهم قطر تیغه: برحسب میلی‌متر برگردان.
    ورودی‌های ممکن: '3 سانت' -> 30mm (احتمال خطا), '30cm' -> 300mm, '305mm', '12\"'
    """
    t = text.replace("اینچ", "\"").replace("سانت", "cm").replace("میلی", "mm")
    # 12" -> 305mm تقریبی
    if re.search(r'(\d{1,2})\s*["”]', t):
        inch = int(re.search(r'(\d{1,2})\s*["”]', t).group(1))
        return int(round(inch * 25.4))
    # 305mm / 300 mm
    if re.search(r'(\d{2,3})\s*mm', t, flags=re.I):
        return int(re.search(r'(\d{2,3})\s*mm', t, flags=re.I).group(1))
    # 30cm / 25 cm
    if re.search(r'(\d{1,3})\s*cm', t, flags=re.I):
        return int(re.search(r'(\d{1,3})\s*cm', t, flags=re.I).group(1)) * 10
    # 3 cm (ambiguous)
    if re.search(r'(\d+)\s*cm', text):
        return int(re.search(r'(\d+)\s*cm', text).group(1)) * 10
    return 0

def _fa_block(summary, causes, checks, next_step, question):
    ln = []
    ln.append(f"🔧 خلاصه: {summary}")
    if causes:
        ln.append("📋 علل محتمل:")
        for c in causes[:3]: ln.append(f"• {c}")
    if checks:
        ln.append("🧩 مواردی که باید چک شود:")
        for c in checks[:6]: ln.append(f"• {c}")
    if next_step: ln.append(f"➡ گام بعدی: {next_step}")
    if question: ln.append(f"❓ سؤال تکمیلی: {question}")
    return "\n".join(ln)

def _rule_based_fallback(user_text: str, lang: str, chat_id: int) -> str:
    t = (user_text or "").strip()
    fa = (lang == "fa")

    # حالت‌های مبهم: «سؤال دیگری دارم»، «خب؟»، «بعدش چی؟»
    if fa and re.fullmatch(r'(حالا\s)?سؤال(ِ|\s)?دیگری\s?دارم\.?', t) or t in {"خب؟", "بعدش چی؟"}:
        st = CHAT_STATE.get(chat_id, {})
        topic = st.get("topic", "")
        if "C12RSH" in topic or "فارسی بر" in topic:
            return _fa_block(
                "ادامهٔ همان موضوع C12RSH: می‌رویم سراغ تنظیمات دقیق زاویه.",
                ["لغزش detent میز، عدم هم‌راستایی فنس/تیغه", "تیغه نابالانس یا کند", "لقی ریل کشویی/یاتاقان"],
                ["با گونیای دقیق، عمود بودن تیغه به فنس را چک و پیچ‌های فنس را تنظیم کن",
                 "detent 45°/90° را دوباره کالیبره کن؛ اگر لق است، پیچ‌های زیر میز را سفت کن",
                 "تیغه را برای تاب/کندی بررسی؛ در صورت نیاز تعویض/بالانس"],
                "یک برش زاویه‌دار 45° بزن و با گونیا کنترل کن؛ اگر خطا ماند، سراغ ریل/یاتاقان برو.",
                "الان خطای زاویه حدوداً چند درجه است و هنگام قفل میز تکان جانبی حس می‌شود؟"
            )
        # اگر موضوع قبلی نداریم، یک پرسش دقیق بپرسیم:
        return "در چه زمینه‌ای سؤال داری؟ ابزار برقی، قطعه خودرویی، یا موضوع دیگر؟ (مثلاً: «C12RSH زاویه دقیق نمی‌زند»)"

    # تشخیص C12RSH و قطر تیغه
    if ("C12RSH" in t) or ("فارسی" in t and "بر" in t):
        blade_mm = _parse_blade(t)
        if blade_mm and blade_mm < 200:  # «۳ سانت» اشتباه رایج
            note = "⚠️ به نظر می‌رسد «۳ سانت» اشتباه تایپی است؛ برای C12RSH معمولاً تیغه ۱۲اینچ ≈ ۳۰۵mm است."
        else:
            note = ""
        # ذخیرهٔ موضوع برای بار بعد
        CHAT_STATE[chat_id] = {"topic": "C12RSH miter saw issue", "last_blade_mm": blade_mm or 305}

        if fa:
            return _fa_block(
                f"عدم دقت زاویه در C12RSH؛ {('قطر تیغه ≈ '+str(blade_mm)+'mm. ' if blade_mm else '')}{note}",
                ["عدم کالیبراسیون فنس/میز یا لقی detent", "تیغه نابالانس/کند یا تاب‌دار", "لقی ریل‌های کشویی/یاتاقان محور"],
                ["عمود بودن تیغه به فنس را با گونیای دقیق چک و فنس را رگلاژ کن",
                 "detentهای 0°/45° را طبق دفترچه کالیبره کن",
                 "ریل‌های کشویی را از نظر لقی سرویس و پیچ‌های پایه را سفت کن",
                 "تیغه را برای تاب/کندی بررسی؛ در صورت نیاز تعویض/بالانس"],
                "اول کالیبراسیون کامل 0°/45°؛ سپس تست برش و کنترل با گونیا.",
                "هنگام قفل‌کردن میز، لقی جانبی داری؟ تیغه فعلی چند دندانه و مخصوص چه متریالی است؟"
            )
        else:
            return "C12RSH miter-saw angle drift: re-calibrate fence/table detents; check rail/bearing play and blade runout. Is the blade 12\" (≈305 mm) and what TPI/material?"
    # دیفالت
    if fa:
        return _fa_block(
            "یک ایراد رایج فنی محتمل است.",
            ["فرسودگی/لقی قطعات مصرفی", "عدم تنظیم/کالیبراسیون", "عدم تطابق ابزار/متریال/ولتاژ"],
            ["سفتی قطعات متحرک و تمیزی", "ولتاژ/جریان ورودی", "سلامت تیغه/زغال/یاتاقان"],
            "یک سرویس سریع + کالیبراسیون انجام بده و دوباره تست کن.",
            "مدل دقیق تجهیز و علائم ایراد را بنویس."
        )
    else:
        return "Likely a common setup issue. Do quick service/alignment and re-test. Share exact model & symptom."

    else:
        return "Likely a common mechanical/electrical setup issue. Check basics (power, consumables, alignment), do a quick service, then re-test. What exact model/symptom?"

def ask_openai(user_text: str, chat_id: int) -> str:
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
            # ذخیرهٔ موضوع ساده
            if "C12RSH" in user_text or ("فارسی" in user_text and "بر" in user_text):
                CHAT_STATE[chat_id] = {"topic": "C12RSH miter saw issue"}
            return out
    except Exception as e:
        print("OPENAI_ERROR:", repr(e))
    # اگر مدل جواب مفید نداد:
    return _rule_based_fallback(user_text, lang, chat_id)


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
        answer = ask_openai(user_text, chat_id)
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
