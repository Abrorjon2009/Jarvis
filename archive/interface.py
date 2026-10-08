import os
import asyncio
import datetime
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties

from task_manager import TaskManager
from brain import JARVIS_TOOLS, JARVIS_INSTRUCTIONS
from google.antigravity import Agent, LocalAgentConfig

# Load Environment Variables from config/.env
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = os.getenv("TELEGRAM_USER_ID")

# Initialize Bot, Dispatcher, and TaskManager
dp = Dispatcher()
tm = TaskManager()

# Global Agent reference
jarvis_agent = None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Handles the /start command. It will also help you get your User ID.
    """
    user_id = str(message.from_user.id)
    if not OWNER_ID:
        await message.answer(f"Hello! Your Telegram User ID is: {user_id}\n\nPlease add this to your config/.env file as TELEGRAM_USER_ID so I only listen to you. Then restart me.")
        return
        
    if user_id != OWNER_ID:
        await message.answer("Access Denied. You are not my creator.")
        return
        
    await message.answer("Jarvis System Initialized. I am online and listening.")

@dp.message(Command("add_task"))
async def cmd_add_task(message: types.Message):
    """
    Simple command to test adding a task. Usage: /add_task Buy milk
    """
    if str(message.from_user.id) != OWNER_ID: return
    
    text = message.text.replace("/add_task", "").strip()
    if not text:
        await message.answer("Please provide a task description.")
        return
        
    tm.add_task(text, due_time=datetime.datetime.now()) # Due immediately for testing
    await message.answer(f"Task added: {text}")

@dp.message(Command("done"))
async def cmd_done_task(message: types.Message):
    """
    Complete a task by ID. Usage: /done 1
    """
    if str(message.from_user.id) != OWNER_ID: return
    
    try:
        task_id = int(message.text.replace("/done", "").strip())
        tm.complete_task(task_id)
        await message.answer(f"Task {task_id} completed!")
    except ValueError:
        await message.answer("Please provide a valid task ID.")

@dp.callback_query()
async def handle_callback_query(callback_query: types.CallbackQuery):
    """
    Handles button presses for tasks (Done, Remind Later, Won't do)
    """
    if str(callback_query.from_user.id) != OWNER_ID:
        await callback_query.answer("Access Denied.", show_alert=True)
        return
        
    data = callback_query.data
    try:
        if data.startswith("done_"):
            task_id = int(data.split("_")[1])
            tm.complete_task(task_id)
            await callback_query.message.edit_text(
                f"✅ <b>Task {task_id} Completed:</b>\n<i>{callback_query.message.text.split(': ', 1)[-1]}</i>",
                reply_markup=None
            )
            await callback_query.answer("Very good, Sir. Task completed.")
            
        elif data.startswith("wontdo_"):
            task_id = int(data.split("_")[1])
            tm.complete_task(task_id) # Using complete_task to remove it from pending
            await callback_query.message.edit_text(
                f"❌ <b>Task {task_id} Dismissed:</b>\n<i>{callback_query.message.text.split(': ', 1)[-1]}</i>",
                reply_markup=None
            )
            await callback_query.answer("As you wish, Sir. Task dismissed.")
            
        elif data.startswith("later_"):
            # A simple implementation: we just acknowledge it and let the loop naturally remind again later.
            # To avoid spamming immediately, we could artificially push the due time, but leaving it as-is 
            # will remind again based on the reminder loop logic.
            await callback_query.answer("I shall remind you again shortly, Sir.")
            
    except Exception as e:
        print(f"[ERROR] handling callback: {e}")
        await callback_query.answer("An error occurred.")

@dp.message()
async def handle_message(message: types.Message):
    """
    Handles all incoming text messages and routes them to Jarvis (Antigravity).
    """
    user_id = str(message.from_user.id)
    print(f"[Jarvis Received]: '{message.text}' from {user_id}")
    if OWNER_ID and user_id != OWNER_ID:
        print(f"[Jarvis Rejected]: Unauthorized user {user_id}")
        return # Silently ignore unauthorized users
        
    if not jarvis_agent:
        await message.answer("[System] Jarvis Core is currently offline or rebooting.")
        return
        
    loading_msg = await message.answer("⏳ <i>Processing your request, Sir...</i>")
    
    async def keep_typing():
        while True:
            try:
                await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
                await asyncio.sleep(4)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(4)
                
    typing_task = asyncio.create_task(keep_typing())
    
    try:
        # Route to Antigravity
        response = await asyncio.wait_for(jarvis_agent.chat(message.text), timeout=120.0)
        response_text = await asyncio.wait_for(response.text(), timeout=120.0)
        await loading_msg.delete()
        await message.answer(response_text)
    except asyncio.TimeoutError:
        await loading_msg.delete()
        await message.answer("[System Error]: I apologize, Sir. My core processes timed out while connecting to the mainframes. The API is likely experiencing high load.")
    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"[System Error]: {str(e)}")
    finally:
        typing_task.cancel()

async def reminder_loop(bot: Bot):
    """
    Background loop that continuously checks for due tasks and aggressively reminds the user.
    """
    print("[Jarvis] Reminder loop started.")
    while True:
        if OWNER_ID:
            pending = tm.get_pending_reminders()
            for task in pending:
                task_id, desc, due, last_reminded = task
                try:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="Done ✅", callback_data=f"done_{task_id}"),
                            InlineKeyboardButton(text="Remind Later ⏰", callback_data=f"later_{task_id}")
                        ],
                        [
                            InlineKeyboardButton(text="Won't do ❌", callback_data=f"wontdo_{task_id}")
                        ]
                    ])
                    await bot.send_message(
                        chat_id=OWNER_ID, 
                        text=f"🚨 <b>REMINDER</b> 🚨\n\n<b>Task ID {task_id}:</b> {desc}",
                        reply_markup=keyboard
                    )
                    tm.update_last_reminded(task_id)
                    print(f"[Jarvis] Sent reminder for task {task_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to send reminder: {e}")
        
        # Check every 60 seconds
        await asyncio.sleep(60)

async def main():
    global jarvis_agent
    
    if not TOKEN or TOKEN == "your_telegram_bot_token_here":
        print("[ERROR] Please set TELEGRAM_BOT_TOKEN in config/.env")
        return
        
    print("[Jarvis] Starting Telegram Interface...")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Configure the Antigravity Agent
    config = LocalAgentConfig(
        tools=JARVIS_TOOLS,
        system_instructions=JARVIS_INSTRUCTIONS,
        model="gemini-3.5-flash"
    )
    
    # Boot up Jarvis
    async with Agent(config) as agent:
        print("[Jarvis] AI Core Online.")
        jarvis_agent = agent
        
        # Start the background reminder loop
        asyncio.create_task(reminder_loop(bot))
        
        # Start polling
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
