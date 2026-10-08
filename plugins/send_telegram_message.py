import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', '.env'))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if len(sys.argv) < 3:
    print("Usage: python send_telegram_message.py <chat_id> <message>")
    sys.exit(1)

chat_id = sys.argv[1]
message = " ".join(sys.argv[2:])

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": message,
    "parse_mode": "HTML"
}
response = requests.post(url, json=payload)

if response.status_code == 200:
    print("Message sent successfully.")
else:
    print(f"Failed to send message: {response.text}")
