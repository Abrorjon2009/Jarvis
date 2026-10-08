import sqlite3
import json
import os
import logging

DB_PATH = os.path.join(os.path.dirname(__file__), 'jarvis_memory.db')
logger = logging.getLogger(__name__)

def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def init_db():
    """Initializes the multi-tier SQLite memory databases."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    # --- HOT TIER: Key-Value Store ---
    # Stores core, immutable facts (e.g. user_name, active_project)
    # Cost: ~50 tokens. Speed: Instant.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hot_context (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # --- WARM TIER: Relational Graph ---
    # Structured relational tables. Not loaded into prompt by default.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            context TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Initialized Hot and Warm memory tiers in SQLite.")

# --- HOT TIER METHODS ---
def get_hot_context() -> dict:
    """Retrieves the full Hot context to be injected into the system prompt."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM hot_context")
    rows = cursor.fetchall()
    conn.close()
    
    context = {}
    for k, v in rows:
        try:
            context[k] = json.loads(v)
        except json.JSONDecodeError:
            context[k] = v
    return context

def set_hot_context(key: str, value: any):
    """Updates or inserts a fact into the Hot context."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
    
    cursor.execute(
        "INSERT INTO hot_context (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, val_str)
    )
    conn.commit()
    conn.close()

# --- WARM TIER METHODS ---
def query_warm_graph(query: str, params: tuple = ()) -> list:
    """
    Exposed as a tool to agents for querying the warm relational graph.
    e.g., query_warm_graph("SELECT * FROM projects WHERE status = ?", ('active',))
    """
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        # Get column names
        columns = [description[0] for description in cursor.description]
        
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    except Exception as e:
        logging.error(f"Error querying warm graph: {e}")
        return []
    finally:
        conn.close()

# --- COLD TIER METHODS ---
class ColdArchive:
    """
    ChromaDB Vector Semantic Store.
    This is strictly gated behind a `search_archives` tool.
    """
    def __init__(self):
        try:
            import chromadb
            chroma_path = os.path.join(os.path.dirname(__file__), 'chroma_db')
            self.client = chromadb.PersistentClient(path=chroma_path)
            self.collection = self.client.get_or_create_collection(name="jarvis_cold_storage")
            self.initialized = True
        except ImportError:
            logging.warning("ChromaDB not installed. Cold storage disabled.")
            self.initialized = False
        
    def search(self, query: str, limit: int = 5):
        if not self.initialized:
            return "[System] ChromaDB not initialized. Cannot perform search."
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        return results
    
    def add_document(self, text: str, metadata: dict = None, doc_id: str = None):
        if not self.initialized:
            return None
        import uuid
        if not doc_id:
            doc_id = str(uuid.uuid4())
        self.collection.add(
            documents=[text],
            metadatas=[metadata] if metadata else [{"source": "unknown"}],
            ids=[doc_id]
        )
        logging.info(f"Added document {doc_id} to Cold Archive.")
        return doc_id

# Initialize DB when module is imported
init_db()
