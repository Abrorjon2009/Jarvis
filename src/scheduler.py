import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schedule.db')

def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            trigger_time_iso TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

def add_reminder(chat_id: str, trigger_time_iso: str, message: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reminders (chat_id, trigger_time_iso, message) VALUES (?, ?, ?)",
        (str(chat_id), trigger_time_iso, message)
    )
    conn.commit()
    conn.close()

def get_due_reminders():
    now = datetime.datetime.now().isoformat()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, chat_id, message FROM reminders WHERE status = 'pending' AND trigger_time_iso <= ?",
        (now,)
    )
    due = cursor.fetchall()
    
    # Mark them as processed
    for row in due:
        cursor.execute("UPDATE reminders SET status = 'sent' WHERE id = ?", (row[0],))
    
    conn.commit()
    conn.close()
    return [{"id": r[0], "chat_id": r[1], "message": r[2]} for r in due]

def get_pending_reminders(chat_id: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, trigger_time_iso, message FROM reminders WHERE chat_id = ? AND status = 'pending' ORDER BY trigger_time_iso ASC",
        (str(chat_id),)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "trigger_time_iso": r[1], "message": r[2]} for r in rows]

def cancel_reminder(reminder_id: int):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET status = 'cancelled' WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()
