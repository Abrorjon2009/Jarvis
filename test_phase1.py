import asyncio
import os
import sys

# Add src to path so we can import modules
sys.path.insert(0, os.path.abspath('src'))

import queue_manager
import memory_manager

async def test_all():
    print("1. --- Testing Memory Manager (SQLite Multi-Tier) ---")
    memory_manager.set_hot_context("test_key", {"status": "operational", "version": 2.0})
    ctx = memory_manager.get_hot_context()
    print("Retrieved Hot Context:", ctx)
    assert ctx["test_key"]["status"] == "operational", "Memory Manager Test Failed"
    print("Memory Manager: PASS\n")
    
    print("2. --- Testing Queue Manager (SQLite Task Queue) ---")
    payload = {
        "user_id": 123,
        "chat_id": 456,
        "text": "Say hello world"
    }
    task_id = queue_manager.push_task(payload)
    print(f"Pushed task ID: {task_id}")
    
    task = queue_manager.pop_task()
    print(f"Popped task: {task}")
    assert task["id"] == task_id, "Queue Manager ID mismatch"
    assert task["payload"]["text"] == "Say hello world", "Queue Manager Payload mismatch"
    
    queue_manager.mark_completed(task_id)
    print("Queue Manager: PASS\n")
    
    print("3. --- Testing agy Orchestrator Subprocess ---")
    cmd_str = r"%LOCALAPPDATA%\agy\bin\agy.exe --model " + '"Gemini 3.8 Flash (High)"' + r" -p " + '"Respond with exactly one word: Success"'
    print(f"Executing: {cmd_str}")
    
    process = await asyncio.create_subprocess_shell(
        cmd_str,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    print(f"Process Return Code: {process.returncode}")
    
    if process.returncode == 0:
        print(f"Orchestrator agy Output: {stdout.decode('utf-8').strip()}")
        print("Orchestrator agy Call: PASS\n")
    else:
        print(f"Orchestrator agy Error: {stderr.decode('utf-8').strip()}")
        print("Orchestrator agy Call: FAIL\n")
        
    print("ALL PHASE 1 FOUNDATION TESTS COMPLETE.")

if __name__ == "__main__":
    asyncio.run(test_all())
