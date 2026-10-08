import asyncio
import logging
import os
import datetime

import sys
sys.path.insert(0, os.path.dirname(__file__))

import queue_manager
import agents

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'daemon.log')

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
stream_handler = logging.StreamHandler()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[file_handler, stream_handler],
    force=True
)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', '.env'))

async def process_task(task: dict):
    task_id = task["id"]
    payload = task["payload"]
    task_description = payload["text"]
    chat_id = payload.get("chat_id", "UNKNOWN")
    
    logging.info(f"Worker processing task {task_id}: {task_description}")
    
    try:
        now = datetime.datetime.now().isoformat()
        
        # Use agents.run_agent which automatically invokes the CLI worker (has tools!)
        prompt = f"The current time is {now}.\nTask ID: {task_id}\nUser Chat ID: {chat_id}\n\nPlease execute the following task:\n{task_description}"
        
        logging.info("Dispatching Universal Worker...")
        result_text, err = await agents.run_agent(agents.UNIVERSAL_WORKER_PERSONA, prompt, str(task_id))
        
        if err:
            logging.error(f"Worker error: {err}")
            result_text = f"I encountered an error while processing the task, Sir: {err}"
        
        # --- Memory Logging ---
        try:
            import memory_manager
            cold_archive = memory_manager.ColdArchive()
            interaction = f"Task: {task_description}\nResult: {result_text}"
            cold_archive.add_document(
                text=interaction,
                metadata={"task_id": str(task_id), "timestamp": now, "type": "background_task"}
            )
        except Exception as mem_err:
            logging.warning(f"Failed to save to memory archive: {mem_err}")
            
        queue_manager.mark_completed(task_id, result_text)
        logging.info(f"Task {task_id} completed successfully.")
        
    except Exception as e:
        logging.error(f"Failed to process task {task_id}: {e}")
        queue_manager.mark_failed(task_id, "I encountered a critical error while processing your request.")

async def daemon_loop():
    logging.info("Initializing Universal Worker Daemon...")
    logging.info("Polling for tasks...")
    
    while True:
        try:
            task = queue_manager.pop_task()
            if task:
                await process_task(task)
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in daemon loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    queue_manager.init_db()
    asyncio.run(daemon_loop())
