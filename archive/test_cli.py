import subprocess
import sys
import shutil

def test_agy_cli():
    print("Initializing Phase 0: Verifying Antigravity CLI (agy) integration...")
    
    # Check if agy is on the system PATH
    agy_path = shutil.which("agy")
    
    if agy_path:
        print(f"[SUCCESS] Found 'agy' CLI installed at: {agy_path}")
        print("Testing a live query to the CLI...")
        try:
            # We are calling the CLI via shell just like a user would type it in
            result = subprocess.run(
                ["agy", "Say exactly the words: 'Inception complete'"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            print("\n--- CLI Output ---")
            print(result.stdout.strip())
            print("------------------")
            print("\n[SUCCESS] AI successfully summoned AI!")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] The CLI command failed with error code: {e.returncode}")
            print(f"Error output:\n{e.stderr}")
    else:
        print("\n[WARNING] The 'agy' CLI was not found on your system PATH.")
        print("To fix this and proceed with Phase 1, you need to ensure the Antigravity CLI is installed globally.")
        print("Since you are using the Antigravity IDE, the CLI might not be exposed globally to Python yet.")

if __name__ == "__main__":
    test_agy_cli()
