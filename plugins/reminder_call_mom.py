import sys
import os
import time
import subprocess
from datetime import datetime

TARGET_ISO = "2026-10-07T23:43:00"
CHAT_ID = "8516322890"
MESSAGE = "🚨 <b>Reminder:</b> Call mom!"

def main():
    target_dt = datetime.fromisoformat(TARGET_ISO)
    now = datetime.now()
    delay = (target_dt - now).total_seconds()
    if delay > 0:
        time.sleep(delay)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    send_script = os.path.join(base_dir, "plugins", "send_telegram_message.py")
    
    subprocess.run([sys.executable, send_script, CHAT_ID, MESSAGE], check=False)

if __name__ == "__main__":
    main()
