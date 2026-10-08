import os
import datetime
import chromadb
from pathlib import Path

# Setup paths based on the JarvisBrain directory structure
BASE_DIR = Path(__file__).resolve().parent.parent
ZETTELKASTEN_DIR = BASE_DIR / "memory" / "zettelkasten"
VECTORDB_DIR = BASE_DIR / "memory" / "vectordb"

# Ensure directories exist
ZETTELKASTEN_DIR.mkdir(parents=True, exist_ok=True)
VECTORDB_DIR.mkdir(parents=True, exist_ok=True)

class MemoryManager:
    def __init__(self):
        # Initialize ChromaDB local persistent client
        self.chroma_client = chromadb.PersistentClient(path=str(VECTORDB_DIR))
        # Create or get the collection for our memories
        self.collection = self.chroma_client.get_or_create_collection(name="jarvis_memories")
        print(f"[Jarvis] MemoryManager initialized. Vector DB loaded from {VECTORDB_DIR}")

    def add_memory(self, content: str, title: str = None) -> str:
        """
        Saves a memory to both a physical Markdown file and the Vector DB.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.replace(" ", "_").lower() if title else "memory"
        filename = f"{timestamp}_{safe_title}.md"
        filepath = ZETTELKASTEN_DIR / filename
        
        # 1. Save to physical Markdown file (Zettelkasten)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        # 2. Add to ChromaDB
        # We use the filename as the unique ID
        self.collection.add(
            documents=[content],
            metadatas=[{"title": title, "timestamp": timestamp}],
            ids=[filename]
        )
        
        print(f"[Jarvis] Memory saved successfully: {filename}")
        return filename

    def query_memory(self, query_text: str, n_results: int = 3) -> list:
        """
        Queries ChromaDB for the most semantically relevant memories.
        """
        print(f"[Jarvis] Searching memory for: '{query_text}'...")
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        if not results['documents'] or not results['documents'][0]:
            print("[Jarvis] No relevant memories found.")
            return []
            
        return results['documents'][0]

if __name__ == "__main__":
    # Quick test of the Memory Manager
    memory = MemoryManager()
    
    print("\n--- Testing Memory Addition ---")
    memory.add_memory("I want to build an indie horror game in Unreal Engine 5 where the monster only moves when you blink.", "Game Dev Idea")
    memory.add_memory("My university admission deadline for Stanford is December 15th.", "College Deadline")
    
    print("\n--- Testing Semantic Search ---")
    results = memory.query_memory("What did I want to do in Unreal Engine?")
    print("Search Results:")
    for i, res in enumerate(results):
        print(f"Result {i+1}: {res}")
