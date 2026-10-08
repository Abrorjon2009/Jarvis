import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_data.db')

def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    
    # Tasks / To-Do List
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            description TEXT NOT NULL,
            deadline_iso TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Schedule / Calendar Events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            start_time_iso TEXT NOT NULL,
            end_time_iso TEXT NOT NULL
        )
    ''')
    
    # Statistics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            date TEXT PRIMARY KEY,
            api_requests INTEGER DEFAULT 0
        )
    ''')
    
    # Reminders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            message TEXT NOT NULL,
            remind_at_iso TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# ---- Task Methods ----

def add_task(chat_id: str, description: str, deadline_iso: str = None) -> int:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (chat_id, description, deadline_iso) VALUES (?, ?, ?)",
        (str(chat_id), description, deadline_iso)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def complete_task(task_id: int):
    set_task_status(task_id, 'completed')

def set_task_status(task_id: int, status: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()

def get_tasks(chat_id: str, status: str = 'pending'):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, description, deadline_iso, status FROM tasks WHERE chat_id = ? AND status = ? ORDER BY id ASC",
        (str(chat_id), status)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "description": r[1], "deadline_iso": r[2], "status": r[3]} for r in rows]

# ---- Schedule Methods ----

def add_schedule_event(chat_id: str, event_name: str, start_time_iso: str, end_time_iso: str) -> int:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO schedule (chat_id, event_name, start_time_iso, end_time_iso) VALUES (?, ?, ?, ?)",
        (str(chat_id), event_name, start_time_iso, end_time_iso)
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_schedule(chat_id: str, from_time_iso: str = None):
    conn = _get_connection()
    cursor = conn.cursor()
    if from_time_iso:
        cursor.execute(
            "SELECT id, event_name, start_time_iso, end_time_iso FROM schedule WHERE chat_id = ? AND end_time_iso >= ? ORDER BY start_time_iso ASC",
            (str(chat_id), from_time_iso)
        )
    else:
        cursor.execute(
            "SELECT id, event_name, start_time_iso, end_time_iso FROM schedule WHERE chat_id = ? ORDER BY start_time_iso ASC",
            (str(chat_id),)
        )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "event_name": r[1], "start_time_iso": r[2], "end_time_iso": r[3]} for r in rows]

# ---- Statistics Methods ----

def increment_api_requests(date_str: str = None):
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO statistics (date, api_requests) VALUES (?, 0)", (date_str,))
    cursor.execute("UPDATE statistics SET api_requests = api_requests + 1 WHERE date = ?", (date_str,))
    conn.commit()
    conn.close()

def get_api_requests(date_str: str = None) -> int:
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT api_requests FROM statistics WHERE date = ?", (date_str,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

# ---- Reminders Methods ----

def add_reminder(chat_id: str, message: str, remind_at_iso: str) -> int:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reminders (chat_id, message, remind_at_iso) VALUES (?, ?, ?)",
        (str(chat_id), message, remind_at_iso)
    )
    reminder_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reminder_id

def get_reminders(chat_id: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, message, remind_at_iso FROM reminders WHERE chat_id = ? ORDER BY remind_at_iso ASC",
        (str(chat_id),)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "message": r[1], "remind_at_iso": r[2]} for r in rows]

def delete_reminder(reminder_id: int):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()
