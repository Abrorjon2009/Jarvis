import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'jarvis_queue.db')

def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def init_db():
    """Initializes the SQLite database and tasks table."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            response TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    # Try to add response column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN response TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
    conn.commit()
    conn.close()

def push_task(payload: dict) -> int:
    """Pushes a new task to the queue."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    payload_str = json.dumps(payload)
    created_at = datetime.utcnow().isoformat()
    
    cursor.execute(
        "INSERT INTO tasks (status, payload, created_at) VALUES (?, ?, ?)",
        ("pending", payload_str, created_at)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return task_id

def pop_task() -> dict | None:
    """Pops the oldest pending task, marking it as processing."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    cursor.execute(
        "SELECT id, payload FROM tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
    )
    row = cursor.fetchone()
    
    if row:
        task_id, payload_str = row
        cursor.execute("UPDATE tasks SET status = 'processing' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
        return {"id": task_id, "payload": json.loads(payload_str)}
    
    conn.commit()
    conn.close()
    return None

def mark_completed(task_id: int, response_text: str = None):
    """Marks a task as completed."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'completed', response = ? WHERE id = ?", (response_text, task_id))
    conn.commit()
    conn.close()

def mark_failed(task_id: int, response_text: str = None):
    """Marks a task as failed."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'failed', response = ? WHERE id = ?", (response_text, task_id))
    conn.commit()
    conn.close()

def pop_completed_task() -> dict | None:
    """Pops the oldest completed or failed task, marking it as delivered."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    cursor.execute(
        "SELECT id, status, payload, response FROM tasks WHERE status IN ('completed', 'failed') ORDER BY created_at ASC LIMIT 1"
    )
    row = cursor.fetchone()
    
    if row:
        task_id, status, payload_str, response_text = row
        cursor.execute("UPDATE tasks SET status = 'delivered' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
        return {"id": task_id, "status": status, "payload": json.loads(payload_str), "response": response_text}
    
    conn.commit()
    conn.close()
    return None

def push_progress_update(chat_id: str, message: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO progress_updates (chat_id, message) VALUES (?, ?)",
        (str(chat_id), message)
    )
    conn.commit()
    conn.close()

def pop_progress_update() -> dict | None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
    cursor.execute(
        "SELECT id, chat_id, message FROM progress_updates WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        update_id, chat_id, message = row
        cursor.execute("UPDATE progress_updates SET status = 'delivered' WHERE id = ?", (update_id,))
        conn.commit()
        conn.close()
        return {"id": update_id, "chat_id": chat_id, "message": message}
    
    conn.commit()
    conn.close()
    return None

# Initialize DB when module is imported
init_db()
