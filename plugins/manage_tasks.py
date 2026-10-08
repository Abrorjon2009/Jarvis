import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src import database_manager

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description="Task Management Tool for Jarvis")
    parser.add_argument("action", choices=["add", "complete", "list"], help="Action to perform")
    parser.add_argument("chat_id", type=str, help="Telegram Chat ID")
    parser.add_argument("--desc", type=str, help="Description of the task")
    parser.add_argument("--deadline", type=str, help="Deadline in ISO format (optional)")
    parser.add_argument("--task_id", type=int, help="Task ID (for complete action)")
    
    args = parser.parse_args()
    
    database_manager.init_db()
    
    if args.action == "add":
        if not args.desc:
            print("Error: --desc is required for add")
            return
        tid = database_manager.add_task(args.chat_id, args.desc, args.deadline)
        print(f"Task added with ID {tid}.")
        
    elif args.action == "complete":
        if not args.task_id:
            print("Error: --task_id is required for complete")
            return
        database_manager.complete_task(args.task_id)
        print(f"Task {args.task_id} completed.")
        
    elif args.action == "list":
        tasks = database_manager.get_tasks(args.chat_id, status='pending')
        if not tasks:
            print("No pending tasks.")
        else:
            for t in tasks:
                d_str = f" [Deadline: {t['deadline_iso']}]" if t['deadline_iso'] else ""
                print(f"ID {t['id']}: {t['description']}{d_str}")

if __name__ == "__main__":
    main()
