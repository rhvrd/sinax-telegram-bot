SinaX – Smart Industrial Navigation Assistant eXpert (Telegram Bot)

Bilingual Industrial AI Consultant for Iran & MENA (FA/EN)

SinaX یک دستیار هوشمند و صنعتی پیشرفته است برای انتخاب، عیب‌یابی، تشخیص فنی، مقایسه تجهیزات, و ارائه‌ی تحلیل‌های مهندسی کوتاه و دقیق در حوزه‌های:

Power Tools / ابزار برقی و کارگاهی (نسخهٔ فوق‌پیشرفته)

Automotive (ICE / Hybrid / EV)

Motorcycle (Carb / EFI / Electrical / Transmission)

Welding

Electrical

Lighting

HVAC / Plumbing

Automation

Lab/Test

Chemicals/Lubes

Paints/Coatings

Construction

PPE/Safety

SinaX for Telegram is powered by GPT-4.1-mini (default), hosted on Render (Free Tier) و کاملاً دو‌زبانه است (FA → پیش‌فرض، EN → در صورت دریافت پیام انگلیسی).

✨ Features
✔ Bilingual AI Assistant (FA/EN)

پاسخ‌ها فارسی هستند مگر اینکه کاربر انگلیسی بنویسد.

✔ 3 Advanced Technical Domains (New!)

Power Tools – Ultra Engineering Version
شامل موتورهای Series-wound، Brushless، Induction، Hammer Mechanism، Failure Modes، تست‌ها، Runout، Bearings، Gearbox، MOSFET، SDS، IEC/ISO references.

Automotive – ICE / Hybrid / EV
شامل Engine، Fuel، GDI، Ignition، Cooling، Transmission (AT, CVT, DCT)، Hybrid battery, Inverter, EV insulation tests، SAE/ISO references.

Motorcycles – Advanced
شامل Carb/EFI، AFR، Injector flow، CDI/ECU، Stator، Charging, Clutch، Gearbox، Compression، Chain alignment، JASO references.

✔ Structured Responses

همهٔ پاسخ‌ها طبق قالب زیر هستند:
Summary → Failure Modes → Key Tests → Next Action → Follow-up Question → References

✔ Technical Standards Awareness

اشاره به استانداردهای معتبر بدون جایگزینی HSE رسمی:
IEC / ISO / ASME / AGMA / SAE / JASO

✔ Configurable Persona

با متغیر SINAX_PROMPT بدون نیاز به redeploy.

📁 Repository Structure
sinax-telegram-bot/
│─ bot.py
│─ requirements.txt
└─ README.md


اختیاری:

runtime.txt

.gitignore (بخصوص .env, pycache)

🤖 SinaX Persona (Updated Summary Version)

SinaX یک دستیار صنعتی فوق‌فنی است که:

فارسی پیش‌فرض

پاسخ کوتاه، دقیق، مهندسی

حداکثر ۱۰ خط یا ۶ بولت

فقط یک Follow-up

بدون لینک خرید، بدون قیمت لحظه‌ای

تمرکز: Failure Modes، Diagnostics، Safety، Compatibility

بخش‌های پیشرفته‌ی Persona

(این‌ها در محیط ENV یا پرامپت اصلی قرار می‌گیرند)

POWER TOOLS – Advanced Engineering Version

AUTOMOTIVE – Advanced ICE/Hybrid/EV

MOTORCYCLE – Advanced Carb/EFI/Ignition/Charging

هر بخش شامل موارد زیر است:

ساختار سیستم

خرابی‌های رایج

تست‌های مهندسی

علائم بالینی خرابی

قطعات تعمیراتی

Keywords

رفرنس‌های استاندارد معتبر

🚀 Deployment on Render (Recommended)
Build Command
pip install -r requirements.txt

Start Command
gunicorn bot:app --bind 0.0.0.0:$PORT

Environment Variables
TELEGRAM_TOKEN=xxxx
OPENAI_API_KEY=xxxx
SINAX_PROMPT= (اختیاری – پرامپت شخصی)

🔗 Set Telegram Webhook

توکن و دامنه را جایگزین کنید:

https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<your-render-app>.onrender.com/telegram-webhook

Check Status
https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo

🧪 Local Development
Install
pip install -r requirements.txt

Run
python -m flask --app bot run --port 8080

Expose via ngrok
ngrok http 8080

Set webhook
https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<ngrok>.ngrok.io/telegram-webhook

🛡️ Security Notes

هرگز Token یا API Key را در کد نگذارید.

فقط در Render → Environment variables

در صورت لو رفتن → فوراً rotate کنید

از لاگ‌برداری پیام‌های حساس کاربر خودداری کنید.

🧠 Model Notes
Default Model

GPT-4.1-mini
بهترین تعادل هزینه/کیفیت برای پاسخ‌های فنی، سریع، دقیق.

Dynamic Model Switching (Optional)

برای درخواست‌های بسیار پیچیده:

model = "gpt-4.1-mini"
if any(k in user_text.lower() for k in ["root cause","asme","timing chain","inverter","thermal runaway"]):
    model = "gpt-5.1"

❓ FAQ
Bot جواب نمی‌دهد؟

webhook → باید دقیقاً /telegram-webhook باشد

Render Logs را چک کنید

کلیدهای OpenAI معتبر باشند

Billing فعال باشد

آیا می‌توان Custom GPT را به بات وصل کرد؟

خیر.
Custom GPT API ندارد.
فقط با SINAX_PROMPT می‌توان رفتار آن را شبیه‌سازی کرد.

📝 License

استفادهٔ آزاد برای پروژه‌های شخصی و تجاری.
(در صورت نیاز می‌توان MIT یا Apache 2.0 اضافه کرد.)
