import sys
import os

# Add src to path so we can import memory_manager
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
import memory_manager

if len(sys.argv) < 2:
    print('Usage: python plugins/manage_memory.py <action> [arguments]')
    print('Actions: add, search, set_hot, get_hot')
    sys.exit(1)

action = sys.argv[1]

if action == "set_hot":
    if len(sys.argv) < 4:
        print('Usage: python plugins/manage_memory.py set_hot <key> "<value>"')
        sys.exit(1)
    key = sys.argv[2]
    val = " ".join(sys.argv[3:])
    memory_manager.set_hot_context(key, val)
    print(f"Hot context updated: {key} = {val}")
elif action == "get_hot":
    context = memory_manager.get_hot_context()
    print("Hot context:")
    for k, v in context.items():
        print(f"- {k}: {v}")
elif action in ("add", "search"):
    if len(sys.argv) < 3:
        print(f'Usage: python plugins/manage_memory.py {action} "<text>"')
        sys.exit(1)
    text = " ".join(sys.argv[2:])
    archive = memory_manager.ColdArchive()
    if action == "add":
        doc_id = archive.add_document(text)
        print(f"Memory saved with ID {doc_id}.")
    elif action == "search":
        results = archive.search(text)
        if not results or not results.get('documents') or len(results['documents'][0]) == 0:
            print("No memories found matching that query.")
        else:
            print("Found memories:")
            for doc in results['documents'][0]:
                print(f"- {doc}")
else:
    print("Unknown action. Use 'add', 'search', 'set_hot', or 'get_hot'.")
