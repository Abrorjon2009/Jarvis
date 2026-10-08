import sys
import os

# Add src to path so we can import scheduler
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
import scheduler

if len(sys.argv) < 4:
    print('Usage: python plugins/add_reminder.py <chat_id> <YYYY-MM-DDTHH:MM:SS> "<message>"')
    sys.exit(1)

chat_id = sys.argv[1]
trigger_time = sys.argv[2]
message = " ".join(sys.argv[3:])

scheduler.init_db()
scheduler.add_reminder(chat_id, trigger_time, message)
print(f"Successfully scheduled reminder for {trigger_time}")
