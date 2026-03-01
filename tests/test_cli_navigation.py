import pexpect
import sys
import os
import time

def test_full_navigation_flow():
    env = os.environ.copy()
    env["GARRAT_GAMES_DIR"] = "games"
    env["NARRAT_TEST_MODE"] = "1" # Enable the clean output mode
    
    # Spawn the process
    child = pexpect.spawn(f"{sys.executable} client.py", env=env, encoding='utf-8', timeout=10)
    
    try:
        # 1. Main Menu
        child.expect("Main Menu")
        print("Detected Main Menu")
        
        # 2. Select 'Select Game' (Standard questionary selection)
        child.sendline("Select Game")
        
        # 3. Wait for Select Game screen
        child.expect("Select Game")
        print("Detected Select Game")
        
        # 4. Pick first game (e.g. cyberpunk_adventure)
        # We assume games exist. We can just send Enter or the name.
        child.sendline("") # Selects first
        
        # 5. Game Hub
        child.expect("Game Hub")
        print("Detected Game Hub")
        
        # 6. Manage Assets
        child.sendline("Manage Assets")
        
        # 7. Asset Manager
        child.expect("Asset Manager")
        print("Detected Asset Manager")
        
        # 8. Back to Hub
        child.sendline("Back")
        
        # 9. Verify Hub
        child.expect("Game Hub")
        print("Returned to Game Hub")
        
        # 10. Back to Main Menu
        child.sendline("Back")
        
        # 11. Exit
        child.expect("Main Menu")
        child.sendline("Exit")
        
        child.expect(pexpect.EOF)
        print("E2E Navigation Test Passed cleanly in Test Mode!")

    except Exception as e:
        print(f"Test Failed! Last output from child:\n{child.before}")
        raise e

if __name__ == "__main__":
    test_full_navigation_flow()
