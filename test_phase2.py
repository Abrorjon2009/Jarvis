import asyncio
import os
import sys
import logging
import tempfile

sys.path.insert(0, os.path.abspath('src'))
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

from memory_manager import ColdArchive
from orchestrator import TriageDecision

logging.basicConfig(level=logging.INFO)

async def test_phase2():
    print("1. --- Testing ChromaDB (Cold Archive) ---")
    archive = ColdArchive()
    if archive.initialized:
        doc_id = archive.add_document("The user likes to drink coffee in the morning.", metadata={"type": "preference"})
        print(f"Added doc: {doc_id}")
        results = archive.search("What does the user drink?")
        print(f"Search Results: {results}")
        print("ChromaDB: PASS\n")
    else:
        print("ChromaDB: FAILED TO INITIALIZE\n")

    print("2. --- Testing LLM Triage (via agy CLI) ---")
    try:
        import datetime, json
        prompt = "Remind me to buy groceries at 5 PM tomorrow"
        print(f"Testing Triage with prompt: {prompt}")
        
        now = datetime.datetime.now().isoformat()
        schema_desc = '{ "category": "one of: reminder, general_qa, research, memory_query, build_tool, use_tool", "extracted_prompt": "string", "missing_tool_name": "string or null", "reminder_time_iso": "string or null" }'
        triage_prompt = f"The current time is {now}. Analyze the following request: '{prompt}'. Categorize it. Respond ONLY with valid JSON matching this schema: {schema_desc}"
        
        agy_path = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin")
        if agy_path not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + agy_path

        fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(triage_prompt)
            
        try:
            triage_process = await asyncio.create_subprocess_exec(
                os.path.join(agy_path, "agy.exe"),
                "--model", "Gemini 3.8 Flash (High)",
                "--dangerously-skip-permissions",
                "-p", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            t_stdout, t_stderr = await triage_process.communicate()
            
            if triage_process.returncode == 0:
                raw_output = t_stdout.decode('utf-8').strip()
                print(f"Raw Output: {raw_output}")
                raw_json = raw_output.strip('`').removeprefix('json').strip()
                parsed_json = json.loads(raw_json)
                triage = TriageDecision(**parsed_json)
                print(f"Triage Result: {triage}")
                print("LLM Triage: PASS\n")
            else:
                print(f"LLM Triage: FAIL (return code {triage_process.returncode})")
                print(f"Stderr: {t_stderr.decode('utf-8')}")
        finally:
            try:
                os.remove(temp_path)
            except:
                pass
            
    except Exception as e:
        print(f"LLM Triage: ERROR - {e}\n")

if __name__ == "__main__":
    asyncio.run(test_phase2())
