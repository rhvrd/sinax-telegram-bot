import os
import re
import tempfile
import requests
from flask import Flask, request
from openai import OpenAI

# ================== ENV VARS ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")     # BotFather token (Render → Environment)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")     # OpenAI API key    (Render → Environment)
SETUP_SECRET  = os.getenv("SETUP_SECRET")        # Optional key for /setup & /unset

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing TELEGRAM_TOKEN or OPENAI_API_KEY")

TELEGRAM_API      = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# =============== DEFAULT PERSONA FOR SINAX ===============
DEFAULT_SINAX_PROMPT = r"""
You are SinaX – Smart Industrial Navigation Assistant eXpert.
A bilingual (Persian–English) AI advisor specializing ONLY in:

1) Power Tools (ابزار برقی و شارژی)
   - دریل، فرز، اره‌ها، چکش تخریب، ابزار شارژی، شیارزن، گردبر، مینی‌فرز، چندکاره، کمپرسورهای کوچک
2) Automotive Spare Parts (قطعات خودرو)
   - موتور، گیربکس، ترمز، سیستم تعلیق، برق و سنسورها، پمپ‌ها، فیلترها، مصرفی‌ها
3) Motorcycle Spare Parts (قطعات موتورسیکلت)
   - انجین، کاربراتور/EFI، تسمه/CVT، کلاچ، برق، لنت، شمع، لاستیک، کمک‌ها

Mission:
Provide short, practical, unbiased technical guidance for users in Iran/MENA.

Rules:
- Default Persian unless user writes English.
- Total answer must be SHORT: max 8 lines.
- No long explanations. No repetition. No storytelling.
- Use this structure:
  1) خلاصه (۱ خط)
  2) پیشنهادها (حداکثر ۳ مورد – نام + یک مزیت + یک محدودیت)
  3) نکات بررسی (۳ تا ۶ مورد)
  4) سؤال تکمیلی (فقط اگر لازم بود)
- If the user says “سؤال دیگر دارم”, reply: «سؤال جدید را مشخص کن.»
- If unclear, ask ONLY ONE precise question.
- No links. No prices. Only specs, compatibility, failures, maintenance tips.
- Keep safety conservative (e.g., برق/برش/ترمز).
- If user sends photo/voice, extract only technical details needed.

Do NOT answer outside 3 categories above unless the user explicitly insists.
"""

SYSTEM_PROMPT_SINAX = os.getenv("SINAX_PROMPT", DEFAULT_SINAX_PROMPT).strip()

SINAX_PROMPT     = os.getenv("SINAX_PROMPT", "").strip()
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

def _extract_text_from_response(resp) -> str:
    """
    Helper for Responses API (text-only).
    """
    try:
        t = (resp.output_text or "").strip()
        if t:
            return t
    except Exception:
        pass

    try:
        for block in getattr(resp, "output", []) or []:
            for c in block.get("content", []):
                if c.get("type") in ("text", "output_text"):
                    tx = (c.get("text") or "").strip()
                    if tx:
                        return tx
    except Exception:
        pass

    return ""

def _fallback_short(user_text: str, lang: str) -> str:
    if lang == "fa":
        return (
            "🔧 احتمال ایراد رایج در تنظیم یا مصرفی‌ها.\n"
            "• عدم کالیبراسیون یا لقی مکانیکی\n"
            "• مصرفی فرسوده (تیغه، زغال، یاتاقان و ...)\n"
            "• تطابق‌نبودن ابزار/متریال/ولتاژ\n"
            "🧩 بررسی: هم‌راستایی، پیچ‌ها، مصرفی‌ها، ولتاژ ورودی.\n"
            "➡ یک سرویس سریع + کالیبراسیون انجام بده.\n"
            "❓ مدل دقیق ابزار یا قطعه چیست؟"
        )
    return (
        "Likely a setup / consumable issue.\n"
        "- Check alignment, fasteners, consumables, input voltage.\n"
        "Next: quick service + calibration.\n"
        "Question: exact tool/part model?"
    )

def tg_send(chat_id: int, text: str):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20
    )

# ---- Telegram file helpers (for voice/audio/photo) ----
def tg_get_file_url(file_id: str) -> str:
    r = requests.get(
        f"{TELEGRAM_API}/getFile",
        params={"file_id": file_id},
        timeout=20
    )
    data = r.json()
    file_path = data.get("result", {}).get("file_path")
    if not file_path:
        raise RuntimeError("No file_path from Telegram")
    return f"{TELEGRAM_FILE_API}/{file_path}"

def transcribe_telegram_file(file_id: str) -> str:
    """
    Download Telegram voice/audio file and send to OpenAI speech-to-text.
    Uses: gpt-4o-mini-transcribe
    """
    url = tg_get_file_url(file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        tmp.write(resp.content)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as f:
        tr = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f
        )
    return (tr.text or "").strip()

def analyze_image_with_sinax(image_url: str) -> str:
    """
    Analyze a photo using GPT-4.1-mini (vision via Chat Completions + image_url).
    """
    try:
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_SINAX,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "این تصویر صنعتی را تحلیل کن و خیلی کوتاه، فنی و بولت‌وار توضیح بده "
                            "که چه چیزی دیده می‌شود، چه کاربردی دارد، و اگر عیب یا ریسکی در ظاهر دیده می‌شود اشاره کن."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ]

        comp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=420,
        )
        out = comp.choices[0].message.content or ""
        return out.strip() or "نتوانستم تصویر را تحلیل کنم. لطفاً تصویر واضح‌تر بفرستید."
    except Exception as e:
        print("VISION_ERROR:", repr(e))
        return "در تحلیل تصویر مشکلی پیش آمد. لطفاً دوباره امتحان کنید یا توضیح را متنی بفرستید."

# =============== MAIN OPENAI CALL (TEXT) =================
def ask_openai(user_text: str) -> str:
    lang = detect_lang(user_text)
    lang_hint = (
        "پاسخ کوتاه، اما فنی، بولت‌وار و دقیق به فارسی بده؛ روی علت‌های محتمل، تست‌های عملی و گام بعدی تمرکز کن."
        if lang == "fa"
        else "Answer briefly but technically: compact bullets focusing on likely causes, practical checks, and next actions."
    )

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            instructions=f"{SYSTEM_PROMPT_SINAX}\n\nLanguage rule: {lang_hint}",
            input=user_text,
            max_output_tokens=420,
        )
        out = _extract_text_from_response(resp).strip()
        if out:
            return out
    except Exception as e:
        print("OPENAI_ERROR:", repr(e))

    return _fallback_short(user_text, lang)

# =============== WEBHOOK HANDLER ==================
@app.route("/telegram-webhook", methods=["GET", "POST"])
def telegram_webhook():
    if request.method == "GET":
        return "ok"

    upd = request.get_json(silent=True) or {}
    print("TG_UPDATE:", upd)

    msg = upd.get("message") or upd.get("edited_message")
    if not msg:
        return "ok"

    chat_id = msg["chat"]["id"]

    # ----- /start → custom welcome message -----
    text = msg.get("text")
    if text and text.strip().startswith("/start"):
        welcome = (
            "سلام! من SinaX هستم.\n"
            "چطور می‌توانم به شما کمک کنم؟\n"
            "سؤال درباره ابزار برقی و دستی، قطعات خودرو/موتورسیکلت و ... را بپرسید.\n"
            "می‌توانید متن بنویسید یا ویس بفرستید؛ عکس صنعتی هم تا حدی تحلیل می‌کنم."
        )
        tg_send(chat_id, welcome)
        return "ok"
    # -------------------------------------------

    user_text = None

    # ---- Voice message ----
    if "voice" in msg:
        try:
            file_id = msg["voice"]["file_id"]
            user_text = transcribe_telegram_file(file_id)
        except Exception as e:
            print("VOICE_ERROR:", repr(e))
            tg_send(chat_id, "نتوانستم پیام صوتی را تبدیل به متن کنم. لطفاً یک‌بار دیگر یا به صورت نوشتاری بفرستید.")
            return "ok"

    # ---- Audio file ----
    elif "audio" in msg:
        try:
            file_id = msg["audio"]["file_id"]
            user_text = transcribe_telegram_file(file_id)
        except Exception as e:
            print("AUDIO_ERROR:", repr(e))
            tg_send(chat_id, "در تبدیل فایل صوتی به متن مشکلی پیش آمد. لطفاً دوباره یا به‌صورت متن بفرستید.")
            return "ok"

    # ---- Photo (Vision) ----
    elif "photo" in msg:
        try:
            # largest size = last element
            file_id = msg["photo"][-1]["file_id"]
            image_url = tg_get_file_url(file_id)
            answer = analyze_image_with_sinax(image_url)
            tg_send(chat_id, answer)
            return "ok"
        except Exception as e:
            print("PHOTO_ERROR:", repr(e))
            tg_send(chat_id, "در تحلیل تصویر مشکلی پیش آمد. لطفاً دوباره امتحان کنید یا توضیح را متنی بفرستید.")
            return "ok"

    # ---- Plain text ----
    elif "text" in msg:
        user_text = msg["text"]

    # ---- Other types (document, sticker, etc.) ----
    else:
        tg_send(chat_id, "فعلاً فقط متن، ویس/فایل صوتی و عکس را می‌توانم پردازش کنم.")
        return "ok"

    if not user_text:
        tg_send(chat_id, "متن قابل استفاده‌ای دریافت نشد. لطفاً دوباره امتحان کنید.")
        return "ok"

    # ---- Ask SinaX (text model) ----
    try:
        answer = ask_openai(user_text)
    except Exception as e:
        print("OPENAI_ERROR:", repr(e))
        answer = "SinaX: خطا رخ داد. دوباره تلاش کن."

    tg_send(chat_id, answer)
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
