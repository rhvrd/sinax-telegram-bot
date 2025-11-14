🤖 SinaX Persona (Updated Summary)

SinaX یک دستیار صنعتی فوق‌فنی است که:

فارسی → پیش‌فرض

پاسخ‌ها کوتاه، دقیق، بولت‌وار

حداکثر ۱۰ خط یا ۶ بولت

فقط یک Follow-up

بدون قیمت و لینک فروش

تمرکز اصلی روی:

Failure modes

Diagnostics

Repair paths

Safety

Compatibility

بخش‌های پیشرفته پرامپت (در ENV)
1) Power Tools – Ultra Engineering

تعمیرات آرمیچر، استاتور، بلبرینگ، گریس‌کاری، SDS wobble، MOSFET burn، Runout، O-ring, piston.

2) Automotive – ICE / Hybrid / EV

Compression, trims, injectors, GDI, cooling, ATF, CVT slip, hybrid inverter, HV insulation.

3) Motorcycle – Carb/EFI/Ignition/Charging

Float height, carb sync, injector clog, stator burnt, rectifier fault, clutch slip, chain alignment.

🚀 Deployment on Render
Build Command
pip install -r requirements.txt

Start Command
gunicorn bot:app --bind 0.0.0.0:$PORT

Environment Variables
TELEGRAM_TOKEN=xxxx
OPENAI_API_KEY=xxxx
SINAX_PROMPT=   (optional)
SETUP_SECRET=   (optional)

🔗 Set Telegram Webhook
https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://<your-app>.onrender.com/telegram-webhook

Check webhook status:
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

Token و API Key هرگز داخل کد نباشد.

فقط در Render → Environment Variables

اگر لو رفت → فوراً rotate

لاگ پیام‌های حساس را ذخیره نکن.

🧠 Model Notes
Default Model

GPT-4.1-mini
بهترین تعادل سرعت/هزینه/دقت برای کاربردهای مهندسی.

Dynamic Switching (Optional)

برای درخواست‌های بسیار تخصصی:

model = "gpt-4.1-mini"
if any(k in user_text.lower() for k in ["root cause", "asme", "timing chain", "inverter", "thermal runaway"]):
    model = "gpt-5.1"

❓ FAQ
Bot پاسخ نمی‌دهد؟

webhook باید دقیقاً روی /telegram-webhook باشد

Render Logs را چک کنید

OpenAI API Key معتبر باشد

Billing فعال باشد

آیا می‌توان Custom GPT را وصل کرد؟

خیر.
Custom GPT API ندارد.
فقط با SINAX_PROMPT می‌توان رفتار آن را شبیه‌سازی کرد.

📝 License

استفادهٔ آزاد برای پروژه‌های شخصی و تجاری.
(در صورت نیاز می‌توانید MIT/Apache 2.0 اضافه کنید.)
