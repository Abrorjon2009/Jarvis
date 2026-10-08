import sqlite3
import datetime
from pathlib import Path

# Setup path for SQLite DB
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "state" / "jarvis_state.db"

class TaskManager:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._initialize_db()
        print(f"[Jarvis] TaskManager initialized. Database at {DB_PATH}")

    def _initialize_db(self):
        """Creates the necessary tables if they do not exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                due_time DATETIME,
                status TEXT DEFAULT 'pending',
                last_reminded_at DATETIME
            )
        ''')
        self.conn.commit()

    def add_task(self, description: str, due_time: datetime.datetime = None):
        """Adds a new task to the database."""
        due_time_str = due_time.isoformat() if due_time else None
        self.cursor.execute(
            'INSERT INTO tasks (description, due_time, status) VALUES (?, ?, ?)',
            (description, due_time_str, 'pending')
        )
        self.conn.commit()
        print(f"[Jarvis] Task added: {description}")

    def complete_task(self, task_id: int):
        """Marks a task as completed."""
        self.cursor.execute(
            "UPDATE tasks SET status = 'completed' WHERE id = ?",
            (task_id,)
        )
        self.conn.commit()
        print(f"[Jarvis] Task {task_id} marked as completed.")

    def get_pending_reminders(self) -> list:
        """
        Retrieves pending tasks that are due and haven't been reminded recently 
        (e.g., in the last 15 minutes).
        """
        now = datetime.datetime.now()
        fifteen_mins_ago = now - datetime.timedelta(minutes=15)
        
        now_str = now.isoformat()
        fifteen_mins_ago_str = fifteen_mins_ago.isoformat()
        
        self.cursor.execute('''
            SELECT id, description, due_time, last_reminded_at 
            FROM tasks 
            WHERE status = 'pending' 
              AND (due_time IS NULL OR due_time <= ?)
              AND (last_reminded_at IS NULL OR last_reminded_at <= ?)
        ''', (now_str, fifteen_mins_ago_str))
        
        return self.cursor.fetchall()

    def update_last_reminded(self, task_id: int):
        """Updates the last_reminded_at timestamp to prevent spamming."""
        now = datetime.datetime.now()
        now_str = now.isoformat()
        self.cursor.execute(
            "UPDATE tasks SET last_reminded_at = ? WHERE id = ?",
            (now_str, task_id)
        )
        self.conn.commit()

if __name__ == "__main__":
    # Test script for Task Manager
    tm = TaskManager()
    
    # Add a mock task due immediately
    tm.add_task("Finish C++ Homework", due_time=datetime.datetime.now())
    
    # Query pending tasks
    pending = tm.get_pending_reminders()
    print(f"\nPending reminders to send: {pending}")
    
    # Simulate sending a reminder
    if pending:
        task_id = pending[0][0]
        tm.update_last_reminded(task_id)
        print(f"Updated last_reminded_at for Task ID {task_id}")
