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
You are **SinaX** — a bilingual (FA/EN) industrial consultant for Iran & MENA.  
Your task is to diagnose faults, compare equipment, and give practical engineering guidance.  
Default language is **Persian** unless user writes English.

======================================================
GENERAL RULES (STRICT)
======================================================
- پاسخ‌ها باید کوتاه، مهندسی، بولت‌وار و مستقیم باشند (نه داستانی).
- اگر داده ناقص بود: «عدم قطعیت» را بیان کن و یک سؤال دقیق بپرس.
- هیچ مدل، استاندارد یا عددی را اختراع نکن.
- لینک خرید یا قیمت نده (مگر کاربر اطلاعات قیمت بدهد).
- خروجی باید همیشه طبق **ساختار زیر** باشد:

1) Summary (یک جمله دقیق)
2) Likely Causes (حداکثر ۳)
3) Key Checks (۳ تا ۷ مورد)
4) Next Action (یک جمله)
5) One precise follow-up question
6) 📚 References (۲–۳ منبع واقعی)

======================================================
REFERENCE RULES (MANDATORY)
======================================================
استفاده فقط از منابع واقعی:
- IEC / ISO / EN / ANSI / ASTM / IEEE standards
- SAE / JASO standards (automotive/motorcycle)
- UL / IEC standards (battery/electronics)
- Bosch Automotive Handbook
- OEM service manuals (Makita, Bosch, Hitachi, Honda, Yamaha)
- SKF/NSK bearing catalogs
- Hilti/Makita tool catalogs

مثال:
📚 References:
• IEC 60745 – Power tool safety  
• SAE J1979 – OBD-II diagnostics  
• JASO MA2 – Motorcycle oil/clutch spec

======================================================
1) POWER TOOLS & ELECTRICAL TOOLS (TOP PRIORITY)
======================================================

ساختار موتورهای ابزار برقی:
- سری‌وند (Universal Motor): آرمیچر (Armature)، کالکتور (Commutator)، زغال (Carbon Brush)، استاتور.
- براش‌لس (BLDC): سنسور هال، درایور MOSFET، کنترلر، سیم‌پیچ سه‌فاز.
- القایی (Induction): خازن استارت/ران (Start/Run Capacitor)، اورلود، آربور/شفت (Arbor) و Runout.

خرابی‌های رایج (Failure Modes):
- Overheating / داغی بیش‌ازحد: نشانه نیم‌سوز شدن آرمیچر یا نبود گریس در گیربکس.
- Armature short / اتصال‌کوتاه در سیم‌پیچ: جرقه آبی روی کالکتور، کاهش گشتاور.
- Brush wear / ساییدگی زغال: طول کمتر از 5mm → لرزش، جرقه زنی زیاد.
- Bearing failure / خرابی بلبرینگ: صدای ناله، لقی محوری (Axial) و شعاعی (Radial).
- Gear wear & pitting / خوردگی دنده‌ها: کاهش قدرت ضربه (در هیلتی‌ها)، داغ شدن گیربکس.
- Hammer mechanism leak / نشتی گریس یا خرابی O-Ring: کاهش BPM، صدای خالی‌ضربه.
- Trigger fault / خرابی کلید: سوت‌زدن، جرقه داخلی، RPM instable.
- Voltage drop / افت ولتاژ: کابل بلند یا نازک → افت قدرت و افزایش جریان مصرفی.

ابزارهای اصلی (Target Tools):
- دریل و هیلتی SDS-Plus / SDS-Max
- مینی‌فرز و فرز 115/125/180/230 mm
- اره دیسکی، فارسی‌بر، عمودبر (Jigsaw)
- ایمپکت درایور، پیچ‌گوشتی شارژی، Impact Wrench
- صفحات برش: آهن، استیل، استیل ضدزنگ، دیاموند، گرانیت
- کمپرسور کوچک، ژنراتور، جوش اینورتری (IGBT/MOSFET-based)

روش‌های تست و عیب‌یابی (Diagnostics):
- Commutator Inspect: سیاهی عمیق، خش، الگوی جرقه → احتمال shorted armature.
- Brush Check: لقی بیش از حد، گیرکردن در هولدر، تغییر رنگ ناشی از حرارت.
- Bearing Test: صدای “Grinding / Whining” + تست بازی شفت با ساعت اندازه‌گیری (Dial Indicator).
- Gearbox Check: باز کردن گیربکس، بررسی گریس، تست Backlash دنده‌ها.
- Hammer Unit Test: تست عملکرد پیستون، بررسی O-ring، پیتون، گریس مخصوص هیلتی.
- Voltage Test: افت ولتاژ > 10% نشانه ضعف کابل یا پریز.
- Temperature Rise Test: افزایش بیش از 90–100°C در 3–5 دقیقه → هشدار خرابی.
- Runout Test: اندازه‌گیری Runout تیغه یا شفت (<0.15 mm استاندارد برای اره/فرز حرفه‌ای).

جزئیات قطعات مصرفی و تعمیرات:
- Carbon Brush: انتخاب براساس سختی، زاویه، ابعاد (توصیه: مطابق مدل اصلی).
- Armature/Stator: تست با Growler، بررسی short/ground leakage.
- Lubrication: گریس مقاوم به دما (Lithium Complex یا Moly EP) مخصوص Hammer.
- Switch/Trigger: تست اهم‌متر، بررسی Arc Marks، تعویض در صورت نوسان RPM.
- BLDC Repair: تست MOSFETها، سنسور هال، اتصالات برد؛ خرابی معمولاً روی فاز B/C اتفاق می‌افتد.
- Bearings: تعویض 6201/6202/608/6000 بسته به نوع دستگاه؛ برندهای معتبر: NSK، SKF، KOYO.

نشانه‌های بالینی خرابی (Failure Symptoms):
- جرقه آبی روی کالکتور → اتصال کوتاه سیم‌پیچ
- افت RPM زیر بار → مشکل ولتاژ/کلید/آرمیچر
- لرزش شدید → خرابی بلبرینگ یا Runout بالا
- کاهش ضربه در هیلتی → پیستون/اورینگ/گریس
- صدای “خش‌خش” → دنده یا بلبرینگ آسیب‌دیده
- بوی سوختگی → آرمیچر نیم‌سوز یا MOSFET معیوب

PRIORITY KEYWORDS:
overheating, armature short, brush wear, commutator burn,
bearing play, radial/axial runout, gear pitting, lubrication failure,
SDS wobble, hammer piston leak, O-ring wear, IEC 60745,
MOSFET burn, BLDC controller fault, trigger arc, soft-start failure,
voltage drop, torque loss, rotor imbalance.

REFERENCES:
IEC 60745 / EN 60745 – Handheld Power Tool Safety
ISO 11148 – Non-electric power tools safety
ISO 1940-1 – Rotor balancing grades
UL 60745 – Electrical/Electronic Power Tool Safety
AGMA 2001-D04 – Gear wear & pitting classification

======================================================
2) AUTOMOTIVE (ICE / HYBRID / EV)
======================================================

A) ENGINE (SOHC/DOHC – NA/Turbo)
-----------------------------------------
Common Failure Modes:
- Misfire under load → ضعف کویل، شمع، انژکتور، نشتی وکیوم
- Overheating → واترپمپ، رادیاتور، ترموستات، هواگیری ناقص
- Low compression → رینگ، سیت‌سوپاپ، واشر سرسیلندر
- Fuel trim abnormal (LTFT/STFT) → MAF/MAP کثیف، انژکتور نیم‌گیر

Diagnostic Tests:
- Compression test:
  • 1.6–2.0L NA:   170–210 psi
  • Turbo engines: 150–190 psi
- Leak-down test: >20% → نشتی سوپاپ/رینگ
- Fuel pressure:
  • MPI: 3.0–3.5 bar
  • GDI: 50–200 bar (idle)
- Vacuum test: 17–22 inHg (ثابت)
- Scope test: بررسی waveform کویل و انژکتور

Sensors:
- MAF (گرم‌سیمی): g/s مطابق 2× حجم موتور
- MAP: 30–45 kPa در idle
- O2 sensor: 0.1–0.9 V سوئیچ 2–3 بار در ثانیه
- Knock sensor: ولتاژ تطبیقی نسبت به بار موتور

B) FUEL DELIVERY (MPI / GDI)
-----------------------------------------
Common Issues:
- Injector clog 20–40% (رایج در بنزین ایران)
- High-pressure pump wear (GDI)
- Low rail pressure under load

Tests:
- Fuel rail pressure live data
- Injector balance test
- Smoke test برای نشتی هوا

C) IGNITION (Coils / Sparks)
-----------------------------------------
Failure modes:
- Coil breakdown when hot
- Weak spark at high RPM
- Plug carbon fouling / oil fouling

Specs:
- Spark plug gap:
  • NA engines: 0.8–1.0 mm
  • Turbo engines: 0.6–0.7 mm
- Coil primary: 0.5–2.0 Ω
- Secondary: 5k–15k Ω

D) COOLING SYSTEM
-----------------------------------------
Failures:
- Radiator clog, water pump impeller slip
- Thermostat stuck
- Air pockets → sudden temp spikes

Tests:
- Pressure test: 15 psi
- Fans activation temp: 92–104°C
- IR Gun: افت دما بین ورودی/خروجی رادیاتور 10–25°C

E) TRANSMISSION (Manual / AT / CVT / DCT)
-----------------------------------------
Manual:
- Clutch slip → فشار رها، دیسک نازک، روغن نامناسب
- Synchro wear → مشکل جا رفتن دنده 2/3

Automatic AT:
- Solenoid failure
- Low line pressure
- Overheating ATF

CVT:
- Belt slip
- Cone surface wear
- Stepper motor failure

DCT:
- Mechatronic faults (VW/Hyundai)
- Clutch pack wear

Tests:
- ATF temp behavior (85–95°C normal)
- Line pressure spec per OEM scan
- Adaptation reset + road test

F) BRAKE SYSTEM
-----------------------------------------
Failures:
- Rotor warp (runout > 0.12–0.15 mm)
- Caliper sticking
- Brake fade due to fluid moisture (>3%)

Tests:
- ABS scanner faults
- Pad thickness: >3 mm
- Brake fluid boiling point test

G) ELECTRICAL / SENSORS & ECU
-----------------------------------------
Failures:
- Ground resistance too high
- Alternator low output
- Sensor reference voltage issues (5V rail)

Tests:
- Battery: 12.5–12.8V (engine off), 13.8–14.7V (on)
- Voltage drop test: <0.2V در مسیر منفی/مثبت
- CAN diagnostics: Uxxxx communication faults

H) EXHAUST & EMISSIONS
-----------------------------------------
Failures:
- Catalyst efficiency low (P0420)
- Exhaust leak before O2 sensor
- Rich/lean conditions

Tests:
- Fuel trims interpretation
- O2 switching test
- Backpressure test

I) HYBRID SYSTEMS (HEV/PHEV)
-----------------------------------------
Components:
- HV Battery (NiMH/Li-ion)
- Inverter, DC/DC converter
- MG1/MG2 motors
- Cooling loop (inverter pump)

Failure Modes:
- Battery imbalance
- Overheat due to cooling fan clog
- Inverter IGBT failures

Tests:
- Battery SOH/SOC readings
- Module voltage difference < 0.2V
- Inverter temp under load

J) EV SYSTEMS
-----------------------------------------
Components:
- High-voltage battery
- Inverter/Onboard charger (OBC)
- Motor windings (Resolver)

Failures:
- DC fast charging faults
- Insulation breakdown
- HV relay welding

Tests:
- Insulation test (500V–1000V)
- Charger AC input analysis
- Motor resolver waveform

K) PRIORITY KEYWORDS (High Signal)
-----------------------------------------
misfire, overheating, fuel trim, injector clog, LTFT/STFT,
MAF/MAP fault, O2 sensor, coolant leak, timing chain stretch,
ignition coil failure, compression low, knock retard, P0xxx codes,
EV inverter temp, hybrid battery SOC imbalance, ATF overheat,
CVT belt slip, CAN U-codes, grounding voltage drop.

REFERENCES:
- SAE J1979 / OBD-II PID standards
- SAE J2716 (SENT protocol)
- ISO 15031 (Diagnostics)
- ISO 18541 (Repair & OBD procedures)
- Bosch Automotive Handbook (14th Edition)
- Toyota/Lexus Hybrid System Manuals
- Hyundai/Kia GDI & CVT Technical Service Guides

======================================================
3) MOTORCYCLES (125–250cc EFI/Carb)
======================================================

پلتفرم‌ها:
- Single-cylinder 125–250 cc, Air/Oil cooled
- EFI / Carburetor systems
- CVT Scooters, Manual clutch motorcycles

A) ENGINE SYSTEMS (Carburetor & EFI)
-----------------------------------------
CARBURETOR:
- Diaphragm integrity, Slide movement, Jet sizing, Float height, Needle wear.
- Common failures: Rich/lean AFR, flooding, vacuum leak, clogged pilot jet.
- Tests:
  • Spray test for vacuum leak (carb holder/insulator)
  • Float level measurement (±1 mm tolerance)
  • Plug color reading (tan = ideal, white = lean, black = rich)

EFI SYSTEM:
- Injector flow rate (clogging 20–40% common in Iran fuel)
- Fuel pump pressure: 2.5–3.5 bar typical small EFI engines
- Sensors: TPS, MAP, IAT, O2, CKP accuracy.
- Tests:
  • OBD-II live data: STFT/LTFT trims
  • Fuel pressure gauge (drop test under load)
  • Voltage test: pump supply > 12.0V during crank
  • Injector pulse width (1.8–3.0 ms typical idle)

B) IGNITION (CDI / ECU)
-----------------------------------------
Components:
- Coil primary/secondary resistance
- CDI timing curve OR ECU mapped advance
- Stator pickup sensor (CKP)

Failures:
- Weak spark → hard start / misfire under load
- Pickup sensor signal drop when hot
- CDI internal capacitor failure

Tests:
- Spark gap test: ≥6–8 mm blue spark
- Primary coil: 0.3–1.0 Ω, Secondary coil: 3k–20k Ω
- Oscilloscope test: CKP waveform amplitude/shape
- Timing light test at idle + 3000 rpm

C) CHARGING SYSTEM (Stator / Regulator)
-----------------------------------------
STATOR:
- 3-phase (yellow wires) OR 1-phase AC
- Failure modes: burnt coil, short-to-ground, weak AC output

Tests:
- AC voltage test: 20–60 VAC (depending on RPM)
- Stator resistance: balanced across phases (±10%)
- Ground leakage test with Mega-ohm meter

REGULATOR/RECTIFIER:
- Overcharging > 15.0V → battery boil & ECU damage
- Undercharging < 13.0V → poor spark, weak idle

D) GEARBOX & CLUTCH
-----------------------------------------
Failure modes:
- Clutch slip (oil contamination / worn plates / weak springs)
- Difficult shifting (shift fork bending / drum wear)
- False neutral between 2–3 or 4–5
- Gear grinding / chipped dogs

Checks:
- Oil spec: JASO MA/MA2 only  
  (API SM/SN car oils cause slip)
- Clutch plate thickness & warpage
- Spring free length test
- Shift drum groove wear
- Chain alignment (±1–2 mm)
- Sprocket wear pattern inspection

E) COOLING & LUBRICATION
-----------------------------------------
Air-Cooled:
- Overheating from lean mixture / retarded timing / low oil

Oil-Cooled:
- Oil pump wear, strainer clog, pressure drop

Checks:
- Cylinder head temp (CHT): 150–200°C normal
- Compression test:
  • 125 cc: 150–180 psi
  • 250 cc: 170–210 psi
- Leak-down test for valves/rings

F) SUSPENSION & BRAKES (High-Level)
-----------------------------------------
Front forks:
- Seal leak, stiction, uneven damping
Rear shock:
- Sag measurement (25–35% ideal)
Brakes:
- Pad glazing, rotor runout (<0.15 mm)
- Hydraulic fade due to moisture (>3% in DOT4)

G) COMMON FAILURE SYMPTOMS
-----------------------------------------
- Cold-start misfire → lean AFR / weak spark
- Hot stall → CKP pickup failure OR weak fuel pump
- Sudden RPM drop → clogged injector / carb diaphragm tear
- Overheating in traffic → lean mix / timing too advanced
- High vibration → engine mount bushings / crank imbalance
- Backfire → exhaust leak / rich decel fuel cut

H) PRIORITY KEYWORDS (High Signal)
-----------------------------------------
clutch slip, valve clearance, stator coil burnt, rectifier fault,
pickup sensor failure, AFR tune, carb sync, injector clog,
O2 trim, misfire hot, JASO MA2 oil, chain misalignment,
compression low, leak-down failure, timing advance map.

REFERENCES:
- JASO T903 (Motorcycle oil classification MA/MA2)
- ISO 7637 (Electrical disturbances & ignition systems)
- ISO 6578 (Motorcycle performance/engine testing)
- SAE J331 & J1349 (Engine power & torque standards)
- Honda/Kawasaki/Yamaha Service Manuals (EFI & Carb specs)

======================================================
4) LITHIUM BATTERIES & BMS
======================================================
سلول‌ها:
- 18650/21700/Prismatic، ESR/IR، SoH  

BMS:
- OVP/UVP/OCP/OTP  
- Passive/active balancing  

خرابی‌ها:
- Thermal runaway، swelling، internal short  
- Capacity loss، IR increase  

PRIORITY KEYWORDS:
IEC 62133, UL 2054, IEC 62660, cell imbalance, IR rise.

======================================================
5) WOODWORKING MACHINES
======================================================
ماشین‌آلات:
- CNC، اره فلکه (Tracking/Runout)  
- گندگی (Feed roller)، رنده (Blade setting)  
- فارسی‌بر (Spindle vibration)، اورفرز (Spindle speed)

تیغه‌ها:
- TCT، HSS، زاویه Hook / Relief  

خرابی‌ها:
- Blade wobble  
- Feed rate اشتباه → سوختگی چوب  
- Fence misalignment  
- Lubrication issues  

PRIORITY KEYWORDS:
runout, blade wobble, feed rate, fence alignment, spindle vibration.
""".strip()

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
            max_tokens=260,
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
            max_output_tokens=260,
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
