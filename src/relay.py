import asyncio
import logging
import os
import datetime
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
import google.genai as genai
from google.genai import types as genai_types

import sys
sys.path.insert(0, os.path.dirname(__file__))

import queue_manager
import agents
import memory_manager
import database_manager

# Configure robust file and console logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'relay.log')

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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Manage GenAI client and chat sessions
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

chat_histories = {}

def strip_html_tags(text: str) -> str:
    """Strips all HTML/XML tags from text."""
    return re.sub(r'<[^>]+>', '', text)

async def safe_send_message(bot_instance: Bot, chat_id: str | int, text: str, reply_to_message_id: int | None = None, parse_mode: str | None = 'HTML', **kwargs) -> Message:
    """Sends a Telegram message, falling back to plain text if HTML parsing fails."""
    try:
        if reply_to_message_id:
            return await bot_instance.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id, parse_mode=parse_mode, **kwargs)
        else:
            return await bot_instance.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kwargs)
    except Exception as e:
        if parse_mode:
            logging.warning(f"Telegram failed to send with parse_mode={parse_mode}: {e}. Falling back to plain text...")
            plain_text = strip_html_tags(text)
            if reply_to_message_id:
                return await bot_instance.send_message(chat_id=chat_id, text=plain_text, reply_to_message_id=reply_to_message_id, parse_mode=None, **kwargs)
            else:
                return await bot_instance.send_message(chat_id=chat_id, text=plain_text, parse_mode=None, **kwargs)
        raise e

async def safe_answer(message: Message, text: str, parse_mode: str | None = 'HTML', **kwargs) -> Message:
    """Answers a Telegram message, falling back to plain text if HTML parsing fails."""
    try:
        return await message.answer(text, parse_mode=parse_mode, **kwargs)
    except Exception as e:
        if parse_mode:
            logging.warning(f"Telegram failed to answer with parse_mode={parse_mode}: {e}. Falling back to plain text...")
            plain_text = strip_html_tags(text)
            return await message.answer(plain_text, parse_mode=None, **kwargs)
        raise e

async def generate_response_with_context(chat_id, user_text, history_user_text=None) -> str:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
        
    history = chat_histories[chat_id]
    
    # Create a temporary history for this generation
    temp_history = history.copy()
    
    # Keep history manageable and ensure first message always has role 'user'
    if len(temp_history) > 20:
        temp_history = temp_history[-20:]
        while temp_history and temp_history[0].get("role") != "user":
            temp_history.pop(0)
        
    hot_context = memory_manager.get_hot_context()
    context_str = "\n".join([f"{k}: {v}" for k, v in hot_context.items()])
    current_time_iso = datetime.datetime.now().isoformat()
    dynamic_instruction = agents.JARVIS_RESPONDER_PERSONA + f"\n\nCURRENT TIME: {current_time_iso}\n\nCURRENT USER HOT CONTEXT:\n{context_str}"
    
    response_text = None
    max_retries = 3
    def add_task_tool(description: str, deadline_iso: str = None) -> str:
        """Adds a task to the user's To-Do list.
        
        Args:
            description: Description of the task.
            deadline_iso: Optional ISO 8601 deadline (e.g. 2026-10-09T17:00:00).
        """
        import database_manager
        task_id = database_manager.add_task(chat_id, description, deadline_iso)
        return f"Task added with ID {task_id}"
        
    def add_reminder_tool(message: str, remind_at_iso: str) -> str:
        """Schedules a Telegram notification/reminder for the user at a specific time.
        
        Args:
            message: The message to send to the user when the reminder triggers.
            remind_at_iso: The precise ISO 8601 time to send the reminder (e.g. 2026-10-09T17:00:00). Must be in the future.
        """
        import database_manager
        reminder_id = database_manager.add_reminder(chat_id, message, remind_at_iso)
        return f"Reminder scheduled with ID {reminder_id}"

    for attempt in range(max_retries):
        try:
            # We initialize a chat with the history, then send the new message
            chat = client.aio.chats.create(
                model='gemini-3.5-flash-lite',
                history=temp_history,
                config=genai_types.GenerateContentConfig(
                    system_instruction=dynamic_instruction,
                    temperature=0.7,
                    tools=[add_task_tool, add_reminder_tool]
                )
            )
            response = await chat.send_message(user_text)
            if response and response.text:
                response_text = response.text
                break
            elif response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                response_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text])
                if response_text:
                    break
            logging.warning(f"Empty Gemini response on attempt {attempt + 1}")
        except Exception as e:
            logging.warning(f"Gemini API attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                logging.error(f"All {max_retries} Gemini API attempts failed: {e}", exc_info=True)
                raise e
    
    if not response_text:
        logging.error("Received empty response from Gemini after all retry attempts.")
        response_text = "I apologize, Sir, I am momentarily speechless."
        
    database_manager.increment_api_requests()
    
    # Append the clean version to the actual persistent history
    text_to_save = history_user_text if history_user_text is not None else user_text
    history.append({"role": "user", "parts": [{"text": text_to_save}]})
    history.append({"role": "model", "parts": [{"text": response_text}]})
    
    # Ensure persistent history doesn't grow unbounded and starts with user role
    if len(history) > 20:
        history = history[-20:]
        while history and history[0].get("role") != "user":
            history.pop(0)
        chat_histories[chat_id] = history
        
    return response_text


@dp.message()
async def handle_all_messages(message: types.Message) -> None:
    chat_id = message.chat.id
    user_text = message.text or ""
    
    # Send a quick "typing" action while the model thinks
    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception as e:
        logging.warning(f"Failed to send typing action: {e}")
    
    try:
        response_text = await generate_response_with_context(chat_id, user_text)
        await safe_answer(message, response_text)
            
    except Exception as e:
        logging.error(f"Error handling message: {e}", exc_info=True)
        await safe_answer(message, "I apologize, Sir, but I encountered an error processing your request.")

async def response_poller_loop():
    logging.info("Starting Response Poller Daemon...")
    while True:
        try:
            completed = queue_manager.pop_completed_task()
            if completed:
                payload = completed["payload"]
                chat_id = payload["chat_id"]
                reply_message_id = payload.get("reply_message_id")
                response_text = completed.get("response") or "Task completed but no response was provided."
                
                prompt = f"SYSTEM MESSAGE: The background worker has completed the task and provided this raw report:\n\n{response_text}\n\nTranslate this report into your Jarvis persona to inform the user. Keep it very concise and natural. DO NOT ask if they need anything else. DO NOT mention system logs or database technicalities unless explicitly asked."
                clean_history = f"[Background Worker Task Completed: {response_text}]"
                
                logging.info(f"Routing worker report through Responder for chat {chat_id}...")
                final_text = await generate_response_with_context(chat_id, prompt, history_user_text=clean_history)
                
                if reply_message_id:
                    try:
                        await safe_send_message(
                            bot_instance=bot,
                            chat_id=chat_id, 
                            text=final_text,
                            reply_to_message_id=reply_message_id,
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logging.warning(f"Failed to reply to message, sending as new: {e}")
                        await safe_send_message(bot_instance=bot, chat_id=chat_id, text=final_text, parse_mode='HTML')
                else:
                    await safe_send_message(bot_instance=bot, chat_id=chat_id, text=final_text, parse_mode='HTML')
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in response poller loop: {e}", exc_info=True)
            await asyncio.sleep(5)

async def persistent_scheduler_loop():
    logging.info("Starting Persistent Scheduler Daemon...")
    while True:
        try:
            due_reminders = database_manager.get_due_reminders()
            for r in due_reminders:
                chat_id = r["chat_id"]
                message = r["message"]
                try:
                    await safe_send_message(bot_instance=bot, chat_id=chat_id, text=f"🔔 <b>Reminder, Sir:</b>\n{message}", parse_mode='HTML')
                    logging.info(f"Sent due reminder to {chat_id}: {message}")
                except Exception as e:
                    logging.error(f"Failed to send reminder to {chat_id}: {e}", exc_info=True)
            await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"Error in scheduler loop: {e}", exc_info=True)
            await asyncio.sleep(10)

async def progress_poller_loop():
    logging.info("Starting Progress Poller Daemon...")
    while True:
        try:
            update = queue_manager.pop_progress_update()
            if update:
                chat_id = update["chat_id"]
                message_text = update["message"]
                
                prompt = f"SYSTEM MESSAGE: The background worker is currently working on the task and sent this progress update:\n\n{message_text}\n\nTranslate this into a brief, polite progress update in your Jarvis persona to keep the user informed. DO NOT ask if they need anything else."
                clean_history = f"[Background Worker Progress Update: {message_text}]"
                
                logging.info(f"Routing progress update through Responder for chat {chat_id}...")
                final_text = await generate_response_with_context(chat_id, prompt, history_user_text=clean_history)
                
                await safe_send_message(bot_instance=bot, chat_id=chat_id, text=final_text, parse_mode='HTML')
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in progress poller loop: {e}", exc_info=True)
            await asyncio.sleep(5)

async def main() -> None:
    queue_manager.init_db()
    database_manager.init_db()
    logging.info("Starting Jarvis Responder Relay...")
    
    commands = [
        BotCommand(command="dashboard", description="Open the main dashboard"),
        BotCommand(command="tasks", description="View and manage pending tasks"),
        BotCommand(command="reminders", description="View and manage active reminders"),
        BotCommand(command="schedule", description="View today's schedule"),
        BotCommand(command="start", description="Start Jarvis"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logging.warning(f"Failed to set bot commands: {e}")
    
    # Start poller loops in background
    asyncio.create_task(response_poller_loop())
    asyncio.create_task(persistent_scheduler_loop())
    asyncio.create_task(progress_poller_loop())
    
    # Start telegram bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
