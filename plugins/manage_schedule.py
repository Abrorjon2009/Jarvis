import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src import database_manager

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description="Schedule Management Tool for Jarvis")
    parser.add_argument("action", choices=["add", "list"], help="Action to perform")
    parser.add_argument("chat_id", type=str, help="Telegram Chat ID")
    parser.add_argument("--event", type=str, help="Name of the event")
    parser.add_argument("--start", type=str, help="Start time in ISO format")
    parser.add_argument("--end", type=str, help="End time in ISO format")
    
    args = parser.parse_args()
    
    database_manager.init_db()
    
    if args.action == "add":
        if not args.event or not args.start or not args.end:
            print("Error: --event, --start, and --end are required for add")
            return
        eid = database_manager.add_schedule_event(args.chat_id, args.event, args.start, args.end)
        print(f"Schedule event added with ID {eid}.")
        
    elif args.action == "list":
        events = database_manager.get_schedule(args.chat_id)
        if not events:
            print("No scheduled events.")
        else:
            for e in events:
                print(f"ID {e['id']}: {e['event_name']} ({e['start_time_iso']} to {e['end_time_iso']})")

if __name__ == "__main__":
    main()
