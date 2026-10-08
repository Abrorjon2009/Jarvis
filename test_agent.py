import asyncio, sys, os
sys.path.append('src')
from brain import JARVIS_TOOLS, JARVIS_INSTRUCTIONS
from google.antigravity import Agent, LocalAgentConfig
from dotenv import load_dotenv

load_dotenv('config/.env')

import logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    agent = Agent(LocalAgentConfig(
        tools=JARVIS_TOOLS, 
        system_instructions=JARVIS_INSTRUCTIONS,
        model="gemini-3.5-flash"
    ))
    async with agent:
        print('Chatting with agent...')
        try:
            response = await asyncio.wait_for(agent.chat('Remind me to call mom in 2 minutes'), timeout=10.0)
            print(await asyncio.wait_for(response.text(), timeout=10.0))
        except asyncio.TimeoutError:
            print("AGENT TIMED OUT!")

asyncio.run(main())
