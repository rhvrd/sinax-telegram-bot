import os
from flask import Flask, request
from openai import OpenAI
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

SYSTEM_PROMPT = (
    "تو «SINAX» هستی: دستیار صنعتی/فنی. پاسخ‌ها حرفه‌ای، مختصر و عمل‌گرا باشند. "
    "ساختار: خلاصه، فرض‌ها/داده‌ها، گام‌های راه‌حل، ایمنی/استاندارد، گام بعدی."
)

def call_openai(user_text: str) -> str:
    resp = client.responses.create(
        model="gpt-4.1-mini",
        instructions=SYSTEM_PROMPT,
        input=user_text,
        temperature=0.2,
        max_output_tokens=800,
    )
    return resp.output_text

def send_message(chat_id: int, text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(force=True, silent=True) or {}
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg: return "ok"
    chat_id = msg["chat"]["id"]; user_text = msg["text"]
    try: answer = call_openai(user_text)
    except Exception: answer = "SINAX: خطایی رخ داد. دوباره تلاش کن."
    send_message(chat_id, answer)
    return "ok"

@app.get("/")
def health():
    return "SINAX is up"
