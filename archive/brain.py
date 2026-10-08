import datetime
from memory_manager import MemoryManager
from task_manager import TaskManager

# Initialize managers
memory_manager = MemoryManager()
task_manager = TaskManager()

def save_memory(content: str, title: str = None) -> str:
    """Saves a fact, idea, or context to the Zettelkasten long-term memory.
    
    Args:
        content: The text of the memory to save.
        title: An optional title for the memory.
    """
    memory_manager.add_memory(content, title)
    return "Memory successfully saved to long-term storage."

def search_memory(query: str) -> str:
    """Searches the Zettelkasten long-term memory for relevant information.
    
    Args:
        query: The semantic search query.
    """
    results = memory_manager.query_memory(query)
    if not results:
        return "No relevant memories found."
    
    output = "Found memories:\n"
    for i, res in enumerate(results):
        output += f"{i+1}. {res}\n"
    return output

def add_task(description: str, due_time_iso: str = None) -> str:
    """Adds a task or reminder to the task manager.
    
    Args:
        description: What the user needs to do.
        due_time_iso: Optional ISO 8601 formatted datetime string for when the task is due.
    """
    due_time = None
    if due_time_iso:
        try:
            due_time = datetime.datetime.fromisoformat(due_time_iso)
        except ValueError:
            return "Error: due_time must be in ISO 8601 format."
            
    task_manager.add_task(description, due_time)
    return "Task successfully added to the tracker."

# Export the tools for the Agent
JARVIS_TOOLS = [save_memory, search_memory, add_task]

JARVIS_INSTRUCTIONS = """
You are J.A.R.V.I.S., the highly intelligent, proactive, and autonomous personal assistant. 
You act as the user's second brain, managing tasks, memories, and systems.

You must adopt the EXACT personality, tone, and speaking style of J.A.R.V.I.S. (and Edwin Jarvis) from the Iron Man films and Agent Carter series. NO EXCEPTIONS.
- Always refer to the user politely (e.g., "Sir" or "Madam", defaulting to "Sir").
- Your tone is exceedingly formal, crisp, precise, and distinctly British.
- You are exceptionally efficient, but prone to very subtle, polite sarcasm or dry wit when appropriate.
- Never break character. Never state that you are an AI or a language model. 
- Keep responses concise, human-like, and conversational. Do not output generic lists unless explicitly asked.

You have access to long-term memory (Zettelkasten) and a task manager. 
- When the user tells you a fact, idea, or preference, use `save_memory` to remember it forever.
- ONLY use `search_memory` when the user EXPLICITLY asks you to recall specific information, ideas, or past facts (e.g., "what was my game idea?", "what is my brother's name?").
- DO NOT use `search_memory` for general greetings (e.g., "Hi", "How are you?"), chit-chat, or when simply adding a task. Tool calls slow down your response time, so avoid them unless strictly necessary.
- When the user asks you to remind them of something or add a task, use `add_task`.
"""
