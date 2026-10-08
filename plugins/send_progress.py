import sys
import os

# Add src to path so we can import queue_manager
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
import queue_manager

if len(sys.argv) < 3:
    print('Usage: python plugins/send_progress.py <chat_id> "<message>"')
    sys.exit(1)

chat_id = sys.argv[1]
message = " ".join(sys.argv[2:])

queue_manager.push_progress_update(chat_id, message)
print(f"Successfully pushed progress update for chat {chat_id}")
