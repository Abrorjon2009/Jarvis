import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath('src'))
import agents

async def test_run_agent():
    persona = agents.CODER_PERSONA
    user_prompt = "Write a simple hello world script in Python."
    task_id = "test-task-123"
    
    print("Testing Coder Agent...")
    stdout, stderr = await agents.run_agent(persona, user_prompt, task_id)
    
    if stderr:
        print(f"FAILED with error: {stderr}")
    else:
        print(f"SUCCESS. Output:\n{stdout}")

if __name__ == "__main__":
    asyncio.run(test_run_agent())
