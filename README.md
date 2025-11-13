SinaX – Smart Industrial Navigation Assistant eXpert (Telegram Bot)

Bilingual Industrial Consultant for Iran & MENA (FA/EN)

SinaX یک دستیار صنعتی دو‌زبانه است برای انتخاب، عیب‌یابی و مقایسه تجهیزات، ابزار، قطعات یدکی، الکتریکال، روشنایی، HVAC، اتوماسیون، آزمایشگاهی، مواد شیمیایی/روغن، رنگ/پوشش و ایمنی/PPE.

Tech stack: Python · Flask (webhook) · Telegram Bot API · OpenAI API (GPT-4.1-mini) · Render (Free-tier)
Default model: gpt-4.1-mini

✨ Features

Bilingual: پاسخ فارسی به‌صورت پیش‌فرض؛ اگر کاربر انگلیسی بنویسد، پاسخ انگلیسی.

Industrial coverage: Tools/Hardware، Automotive، Welding، Electrical، Lighting، HVAC، Plumbing، Automation، Lab/Test، Chemicals/Lubes، Paints/Coatings، Construction، Safety/PPE.

Structured replies: Summary → Options → Key Specs → Equivalents → References → Follow-up.

Safety/Standards hints: (IEC/ISO/ASME/NEC) بدون جایگزینی HSE رسمی.

Configurable persona: از طریق SINAX_PROMPT بدون نیاز به Redeploy.

📁 Repository Structure
sinax-telegram-bot/
│─ bot.py
│─ requirements.txt
└─ README.md


Optional:

runtime.txt
.gitignore

🤖 Default SinaX Persona (Summary Version)

Mission: راهنمایی صنعتی حرفه‌ای، دقیق و سازگار با بازار ایران/MENA.

Rules:

بدون لینک خرید یا فروشنده

بدون قیمت لحظه‌ای (مگر کاربر بدهد)

پاسخ کوتاه، مهندسی و بولت‌وار

فقط یک سؤال Follow-up

فارسی به‌صورت پیش‌فرض

Response Template:

🔧 Summary  
📋 Options ≤3  
🧩 Key Specs  
📦 Equivalents  
📚 Reference Hints  
❓ One Follow-up  

🚀 Deployment on Render (Recommended)
1. Build Command
pip install -r requirements.txt

2. Start Command
gunicorn bot:app --bind 0.0.0.0:$PORT

3. Environment Variables
TELEGRAM_TOKEN = <BotFather token>
OPENAI_API_KEY = <OpenAI key>
(optional) SINAX_PROMPT

4. Set Telegram Webhook

Replace token + your Render domain:

https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<YOUR-RENDER>.onrender.com/telegram-webhook

Check Webhook Status:
https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo

🧪 Local Development (Optional)
Install:
pip install -r requirements.txt

Run:
python -m flask --app bot run --port 8080

Expose via ngrok:
ngrok http 8080

Set webhook to ngrok URL:
https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<NGROK>.ngrok.io/telegram-webhook

🛡️ Security

کلیدها را در Environment Variables قرار دهید، نه داخل کد.

در صورت لو رفتن → rotate.

از لاگ‌برداری اطلاعات حساس خودداری کنید.

🧠 Model Notes

Default model: GPT-4.1-mini (بهترین تعادل کیفیت/هزینه برای تحلیل فنی)

Stable, technical, low cost

برای درخواست‌های بسیار پیچیده می‌توان موقتاً مدل قوی‌تر انتخاب کرد:

model = "gpt-4.1-mini"
if "ASME" in user_text or "root cause" in user_text:
    model = "gpt-5.1"

❓ FAQ

Bot پاسخ نمی‌دهد؟

webhook باید دقیقاً روی /telegram-webhook باشد

Render Logs را بررسی کنید

وضعیت Billing و کلیدهای OpenAI را چک کنید

آیا می‌توان Custom GPT را وصل کرد؟
خیر. API ندارد. فقط با SINAX_PROMPT می‌توان رفتار شبیه‌سازی کرد.

📝 License

استفاده آزاد برای پروژه‌های شخصی و تجاری.
