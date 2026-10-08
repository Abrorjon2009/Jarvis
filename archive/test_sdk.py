import sys
try:
    import google.antigravity
    print("[SUCCESS] The Google Antigravity SDK is successfully installed!")
    print(f"Antigravity version path: {google.antigravity.__file__}")
    print("\nPhase 0 Complete: We can now natively build Jarvis in Python without hacky shell commands.")
except ImportError as e:
    print(f"[ERROR] Failed to load Antigravity: {e}")
