"""
Reminder Plugin for Jarvis
Handles task and reminder creation, querying, state tracking, and Telegram notification delivery.
"""

import sys
import os
import sqlite3
import datetime
import argparse
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "state" / "jarvis_state.db"
ENV_PATH = BASE_DIR / "config" / ".env"

load_dotenv(ENV_PATH)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_USER_ID")


def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            due_time DATETIME,
            status TEXT DEFAULT 'pending',
            last_reminded_at DATETIME
        )
    ''')
    conn.commit()
    return conn


def send_telegram_alert(text: str, chat_id: str = None) -> bool:
    chat_id = chat_id or DEFAULT_CHAT_ID
    if not BOT_TOKEN or not chat_id:
        print("[ReminderPlugin] Error: Missing TELEGRAM_BOT_TOKEN or chat_id.")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("ok", False)
    except urllib.error.URLError as e:
        print(f"[ReminderPlugin] Telegram send error: {e}")
        return False


def create_reminder(description: str, due_time: datetime.datetime) -> int:
    conn = get_db_connection()
    due_str = due_time.isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (description, due_time, status) VALUES (?, ?, 'pending')",
        (description, due_str)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def list_pending_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, description, due_time, status, last_reminded_at FROM tasks WHERE status = 'pending' ORDER BY due_time ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_due_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().isoformat()
    cursor.execute(
        "SELECT id, description, due_time FROM tasks WHERE status = 'pending' AND (due_time IS NULL OR due_time <= ?)",
        (now_str,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_reminded(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().isoformat()
    cursor.execute(
        "UPDATE tasks SET last_reminded_at = ? WHERE id = ?",
        (now_str, task_id)
    )
    conn.commit()
    conn.close()


def mark_completed(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET status = 'completed' WHERE id = ?",
        (task_id,)
    )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Jarvis Reminder Plugin CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Add command
    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--text", required=True, help="Reminder description")
    add_parser.add_argument("--minutes", type=float, help="Minutes from now")
    add_parser.add_argument("--due", help="Explicit ISO datetime string")
    add_parser.add_argument("--notify-now", action="store_true", help="Send Telegram alert immediately")

    # List command
    subparsers.add_parser("list")

    # Check and trigger due reminders
    subparsers.add_parser("check")

    # Complete command
    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--id", type=int, required=True, help="Task ID")

    args = parser.parse_args()

    if args.command == "add":
        now = datetime.datetime.now()
        if args.due:
            due_dt = datetime.datetime.fromisoformat(args.due)
        elif args.minutes is not None:
            due_dt = now + datetime.timedelta(minutes=args.minutes)
        else:
            due_dt = now

        task_id = create_reminder(args.text, due_dt)
        print(f"Created reminder ID {task_id}: '{args.text}' due at {due_dt.isoformat()}")

        if args.notify_now:
            alert_text = f"🚨 <b>REMINDER</b> 🚨\n\n<b>Task:</b> {args.text}\n<b>Scheduled Time:</b> {due_dt.strftime('%H:%M:%S')}"
            success = send_telegram_alert(alert_text)
            if success:
                mark_reminded(task_id)
                print(f"Telegram alert sent for task ID {task_id}.")
            else:
                print(f"Failed to send Telegram alert for task ID {task_id}.")

    elif args.command == "list":
        pending = list_pending_reminders()
        print(f"Found {len(pending)} pending reminders:")
        for r in pending:
            print(f"- ID {r[0]}: {r[1]} (Due: {r[2]}, Last reminded: {r[4]})")

    elif args.command == "check":
        due = get_due_reminders()
        print(f"Found {len(due)} due reminders.")
        for r in due:
            task_id, desc, due_time = r
            alert_text = f"🚨 <b>REMINDER</b> 🚨\n\n<b>Task ID {task_id}:</b> {desc}\n<b>Due:</b> {due_time}"
            if send_telegram_alert(alert_text):
                mark_reminded(task_id)
                print(f"Alert sent for Task {task_id}: {desc}")

    elif args.command == "complete":
        mark_completed(args.id)
        print(f"Marked task {args.id} as completed.")


if __name__ == "__main__":
    main()
