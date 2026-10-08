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
import scheduler

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
poll_task_map = {}
poll_reminder_map = {}

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
    temp_history.append({"role": "user", "parts": [{"text": user_text}]})
    
    # Keep history manageable and ensure first message always has role 'user'
    if len(temp_history) > 20:
        temp_history = temp_history[-20:]
        while temp_history and temp_history[0].get("role") != "user":
            temp_history.pop(0)
        
    hot_context = memory_manager.get_hot_context()
    context_str = "\n".join([f"{k}: {v}" for k, v in hot_context.items()])
    dynamic_instruction = agents.JARVIS_RESPONDER_PERSONA + f"\n\nCURRENT USER HOT CONTEXT:\n{context_str}"
    
    response_text = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=temp_history,
                config=genai_types.GenerateContentConfig(
                    system_instruction=dynamic_instruction,
                    temperature=0.7
                )
            )
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

# --- Dashboard UI Handlers ---

@dp.message(Command("start", "dashboard"))
async def cmd_dashboard(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 My Tasks", callback_data="ui_tasks")],
        [InlineKeyboardButton(text="⏰ My Reminders", callback_data="ui_reminders")],
        [InlineKeyboardButton(text="📅 My Schedule", callback_data="ui_schedule")]
    ])
    await safe_answer(message, "<b>Jarvis Dashboard</b>\nWhat would you like to view, Sir?", parse_mode='HTML', reply_markup=kb)

@dp.message(Command("tasks", "todo"))
async def cmd_tasks(message: types.Message):
    await show_tasks(message.chat.id)

@dp.message(Command("reminders"))
async def cmd_reminders(message: types.Message):
    await show_reminders(message.chat.id)

@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    await show_schedule(message.chat.id)

async def show_tasks(chat_id: int):
    tasks = database_manager.get_tasks(str(chat_id), status='pending')
    if not tasks:
        await safe_send_message(bot, chat_id, "You have no pending tasks, Sir.")
        return
        
    options = []
    for t in tasks:
        deadline_str = f" (Due: {t['deadline_iso'][:10]})" if t.get('deadline_iso') else ""
        opt_text = f"{t['description']}{deadline_str}"
        if len(opt_text) > 100:
            opt_text = opt_text[:97] + "..."
        options.append(opt_text)
        
    if len(options) == 1:
        options.append("(End of list)")
        tasks.append({"id": -1})
        
    try:
        msg = await bot.send_poll(
            chat_id=chat_id,
            question="📋 Pending Tasks (Check to complete)",
            options=options,
            is_anonymous=False,
            type='regular',
            allows_multiple_answers=True
        )
        poll_task_map[msg.poll.id] = {
            'chat_id': chat_id,
            'message_id': msg.message_id,
            'task_ids': [t['id'] for t in tasks]
        }
    except Exception as e:
        logging.error(f"Failed to send poll: {e}")
        await safe_send_message(bot, chat_id, "Failed to display tasks as a poll.")

async def show_reminders(chat_id: int):
    reminders = scheduler.get_pending_reminders(str(chat_id))
    if not reminders:
        await safe_send_message(bot, chat_id, "You have no pending reminders, Sir.")
        return
        
    options = []
    for r in reminders:
        opt_text = f"{r['message']} (At: {r['trigger_time_iso']})"
        if len(opt_text) > 100:
            opt_text = opt_text[:97] + "..."
        options.append(opt_text)
        
    if len(options) == 1:
        options.append("(End of list)")
        reminders.append({"id": -1})
        
    try:
        msg = await bot.send_poll(
            chat_id=chat_id,
            question="⏰ Pending Reminders (Check to cancel)",
            options=options,
            is_anonymous=False,
            type='regular',
            allows_multiple_answers=True
        )
        poll_reminder_map[msg.poll.id] = {
            'chat_id': chat_id,
            'message_id': msg.message_id,
            'reminder_ids': [r['id'] for r in reminders]
        }
    except Exception as e:
        logging.error(f"Failed to send poll: {e}")
        await safe_send_message(bot, chat_id, "Failed to display reminders as a poll.")

async def show_schedule(chat_id: int):
    events = database_manager.get_schedule(str(chat_id))
    if not events:
        await safe_send_message(bot, chat_id, "Your schedule is clear, Sir.")
        return
    
    text = "📅 <b>Your Schedule:</b>\n\n"
    for e in events:
        text += f"• <b>{e['event_name']}</b>\n  <i>{e['start_time_iso']} - {e['end_time_iso']}</i>\n\n"
    await safe_send_message(bot, chat_id, text)

@dp.callback_query(F.data.startswith("ui_"))
async def process_ui_callback(callback_query: types.CallbackQuery):
    action = callback_query.data.split("_")[1]
    chat_id = callback_query.message.chat.id
    await bot.answer_callback_query(callback_query.id)
    if action == "tasks":
        await show_tasks(chat_id)
    elif action == "reminders":
        await show_reminders(chat_id)
    elif action == "schedule":
        await show_schedule(chat_id)

@dp.callback_query(F.data.startswith("complete_task_"))
async def process_task_complete(callback_query: types.CallbackQuery):
    task_id = int(callback_query.data.split("_")[2])
    database_manager.complete_task(task_id)
    await bot.answer_callback_query(callback_query.id, text="Task completed.")
    
    tasks = database_manager.get_tasks(str(callback_query.message.chat.id), status='pending')
    if not tasks:
        await bot.edit_message_text(text="All tasks completed, Sir.", chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        return
        
    text = "📋 <b>Your Pending Tasks:</b>\n\n"
    keyboard = []
    row = []
    for i, t in enumerate(tasks, start=1):
        deadline_str = f" (Deadline: {t['deadline_iso']})" if t.get('deadline_iso') else ""
        text += f"<b>{i}.</b> {t['description']}{deadline_str}\n"
        row.append(InlineKeyboardButton(text=f"✅ {i}", callback_data=f"complete_task_{t['id']}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await bot.edit_message_text(text=text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("cancel_reminder_"))
async def process_reminder_cancel(callback_query: types.CallbackQuery):
    reminder_id = int(callback_query.data.split("_")[2])
    scheduler.cancel_reminder(reminder_id)
    await bot.answer_callback_query(callback_query.id, text="Reminder cancelled.")
    
    reminders = scheduler.get_pending_reminders(str(callback_query.message.chat.id))
    if not reminders:
        await bot.edit_message_text(text="You have no pending reminders, Sir.", chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        return
        
    text = "⏰ <b>Your Pending Reminders:</b>\n\n"
    keyboard = []
    row = []
    for i, r in enumerate(reminders, start=1):
        text += f"<b>{i}.</b> {r['message']}\n<i>At: {r['trigger_time_iso']}</i>\n\n"
        row.append(InlineKeyboardButton(text=f"❌ Cancel {i}", callback_data=f"cancel_reminder_{r['id']}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await bot.edit_message_text(text=text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, reply_markup=kb, parse_mode="HTML")
@dp.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    poll_id = poll_answer.poll_id
    selected_options = poll_answer.option_ids
    
    if poll_id in poll_task_map:
        info = poll_task_map[poll_id]
        task_ids = info['task_ids']
        chat_id = info['chat_id']
        message_id = info['message_id']
        
        for i, task_id in enumerate(task_ids):
            if task_id == -1:
                continue
            if i in selected_options:
                database_manager.set_task_status(task_id, "completed")
            else:
                database_manager.set_task_status(task_id, "pending")
        
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
            
        await show_tasks(chat_id)
                
    elif poll_id in poll_reminder_map:
        info = poll_reminder_map[poll_id]
        reminder_ids = info['reminder_ids']
        chat_id = info['chat_id']
        message_id = info['message_id']
        
        for i, reminder_id in enumerate(reminder_ids):
            if reminder_id == -1:
                continue
            if i in selected_options:
                scheduler.cancel_reminder(reminder_id)
        
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
            
        await show_reminders(chat_id)
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
        
        # Check if the Responder wants to delegate a task (case-insensitive, tolerates unclosed tags)
        delegate_match = re.search(r'(?i)<DELEGATE>(.*?)(?:</DELEGATE>|$)', response_text, re.DOTALL)
        
        if delegate_match and delegate_match.group(1).strip():
            task_description = delegate_match.group(1).strip()
            # Remove the tag from what we show the user
            display_text = re.sub(r'(?i)<DELEGATE>.*?(?:</DELEGATE>|$)', '', response_text, flags=re.DOTALL).strip()
            
            if display_text:
                reply = await safe_answer(message, display_text)
                reply_message_id = reply.message_id
            else:
                reply = await safe_answer(message, "⏳ <i>Working on it, Sir...</i>")
                reply_message_id = reply.message_id
                
            # Push the task to the Universal Worker queue
            payload = {
                "user_id": message.from_user.id if message.from_user else chat_id,
                "chat_id": chat_id,
                "message_id": message.message_id,
                "reply_message_id": message.message_id, # FIX: Always reply to the user's original message, not Jarvis's "Working on it" reply
                "text": task_description,
                "date": message.date.isoformat() if message.date else datetime.datetime.utcnow().isoformat(),
            }
            task_id = queue_manager.push_task(payload)
            logging.info(f"Delegated task {task_id} to Worker: {task_description}")
            
        else:
            # Just a normal conversation
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
    import scheduler
    logging.info("Starting Persistent Scheduler Daemon...")
    while True:
        try:
            due_reminders = scheduler.get_due_reminders()
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
    import scheduler
    scheduler.init_db()
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
