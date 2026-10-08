import asyncio
import time
import os
import tempfile
import sys

# Simulate the exact logic from orchestrator and agents
agy_path = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin")

async def run_agent(persona, prompt):
    full_prompt = f"{persona}\n\nTask:\n{prompt}"
    fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(full_prompt)
        
    try:
        process = await asyncio.create_subprocess_exec(
            os.path.join(agy_path, "agy.exe"),
            "--model", "Gemini 3.8 Flash (High)",
            "--dangerously-skip-permissions",
            "-p", temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return stdout.decode('utf-8').strip(), stderr.decode('utf-8').strip()
    finally:
        try: os.remove(temp_path)
        except: pass

async def main():
    test_prompt = "Tell me a 1 sentence joke about AI."
    print(f"\n--- Testing Latency for: '{test_prompt}' ---")
    
    start_time = time.time()
    
    # 1. Triage (using a simple triage persona for the test)
    triage_start = time.time()
    print("1. Running Triage...")
    triage_persona = "You are a router. Just return {" + f'"category": "general_qa", "extracted_prompt": "{test_prompt}"' + "}"
    await run_agent(triage_persona, test_prompt)
    triage_end = time.time()
    print(f"   Triage took: {triage_end - triage_start:.2f} seconds")
    
    # 2. Worker Agent
    worker_start = time.time()
    print("2. Running Worker Agent...")
    worker_persona = "You are Jarvis, a helpful and concise personal assistant. Provide raw answers."
    raw_result, _ = await run_agent(worker_persona, test_prompt)
    worker_end = time.time()
    print(f"   Worker took: {worker_end - worker_start:.2f} seconds")
    
    # 3. Formatter Agent
    formatter_start = time.time()
    print("3. Running Jarvis Voice Formatter...")
    voice_persona = "You are J.A.R.V.I.S., the highly advanced, polite AI assistant. Address the user as 'Sir'."
    voice_prompt = f"Rewrite this in your voice:\n\n{raw_result}"
    final_result, _ = await run_agent(voice_persona, voice_prompt)
    formatter_end = time.time()
    print(f"   Formatter took: {formatter_end - formatter_start:.2f} seconds")
    
    end_time = time.time()
    print(f"\nFinal Result:\n{final_result}")
    print(f"\nTotal time elapsed: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
