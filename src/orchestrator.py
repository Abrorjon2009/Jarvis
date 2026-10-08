import asyncio
import logging
import os
import subprocess
import datetime
import json
import tempfile
from aiogram import Bot
from pydantic import BaseModel, Field

import queue_manager
import agents

class TriageDecision(BaseModel):
    category: str = Field(description="One of: 'reminder', 'general_qa', 'research', 'memory_query', 'build_tool', 'use_tool'")
    extracted_prompt: str = Field(description="The cleaned up request to pass to the worker.")
    missing_tool_name: str | None = Field(description="If build_tool, the name of the external integration needed. Else None.")
    reminder_time_iso: str | None = Field(description="If reminder, the ISO time to remind. Else None.")

logging.basicConfig(level=logging.INFO)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', '.env'))

# Initialize bot to edit messages
# IMPORTANT: Set the TELEGRAM_BOT_TOKEN environment variable.
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = Bot(token=BOT_TOKEN)

async def process_incoming_message(chat_id, reply_message_id, user_text):
    logging.info(f"Incoming message: {user_text}")
    
    try:
        await bot.edit_message_text(
            text=f"⏳ <i>Analyzing your request, Sir...</i>",
            chat_id=chat_id,
            message_id=reply_message_id,
            parse_mode='HTML'
        )
        
        now = datetime.datetime.now().isoformat()
        schema_desc = '{ "category": "one of: reminder, general_qa, research, memory_query, build_tool, use_tool", "extracted_prompt": "string", "missing_tool_name": "string or null", "reminder_time_iso": "string or null" }'
        triage_prompt = f"The current time is {now}. Analyze the following request: '{user_text}'. Categorize it. Respond ONLY with valid JSON matching this schema: {schema_desc}"
        
        triage_stdout, _ = await agents.run_fast_agent(
            "You are a triage agent. Output only raw JSON, no markdown.", 
            triage_prompt
        )
        
        triage = None
        try:
            raw_json = triage_stdout.strip().strip('`').removeprefix('json').strip()
            parsed_json = json.loads(raw_json)
            triage = TriageDecision(**parsed_json)
        except Exception as e:
            logging.warning(f"Failed to parse triage JSON: {e}")
            
        category = triage.category if triage else "general_qa"
        
        # Instant acknowledgment based on category
        if category == 'build_tool':
            ack_msg = "👨‍💻 I have dispatched the Coder Agent to build this integration, Sir. I will notify you when it is complete."
        elif category == 'use_tool':
            ack_msg = "🔌 The Integration Hub is connecting to external services, Sir. Please stand by."
        elif category == 'research':
            ack_msg = "🔍 The Researcher Agent is gathering information from the web, Sir. I will report back shortly."
        elif category == 'memory_query':
            ack_msg = "📖 The Librarian Agent is searching the memory archives, Sir. I will notify you when it's done."
        elif category == 'reminder':
            ack_msg = "⏳ Processing reminder, Sir."
        else:
            ack_msg = "👨‍💼 Processing your request directly, Sir."
            
        await bot.edit_message_text(text=ack_msg, chat_id=chat_id, message_id=reply_message_id)
        
        # Push to queue for the daemon
        payload = {
            "chat_id": chat_id,
            "text": user_text,
            "reply_message_id": reply_message_id
        }
        task_id = queue_manager.push_task(payload)
        logging.info(f"Pushed task {task_id} to queue.")
        
    except Exception as e:
        logging.error(f"Failed to process incoming message: {e}")
        try:
            await bot.edit_message_text(text="I encountered a critical error while routing your request.", chat_id=chat_id, message_id=reply_message_id)
        except:
            pass

async def response_poller_loop():
    logging.info("Starting Response Poller Daemon...")
    while True:
        try:
            completed = queue_manager.pop_completed_task()
            if completed:
                payload = completed["payload"]
                chat_id = payload["chat_id"]
                reply_message_id = payload.get("reply_message_id")
                response_text = completed.get("response", "Task completed but no response was provided.")
                
                if reply_message_id:
                    try:
                        await bot.edit_message_text(
                            text=response_text,
                            chat_id=chat_id,
                            message_id=reply_message_id
                        )
                    except Exception as e:
                        logging.warning(f"Failed to edit message, sending as new: {e}")
                        await bot.send_message(chat_id=chat_id, text=response_text)
                else:
                    await bot.send_message(chat_id=chat_id, text=response_text)
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in response poller loop: {e}")
            await asyncio.sleep(5)

# We still need a way to receive telegram messages and trigger `process_incoming_message`.
# Wait, currently `relay.py` runs the aiogram bot polling and `orchestrator.py` only handles the processing loop?
# Let's check relay.py.
