import pexpect
import sys
import os

def test_cli_starts_and_exits():
    # Set environment to use test games dir
    env = os.environ.copy()
    env["GARRAT_GAMES_DIR"] = "test_games_tmp"
    
    # Spawn the process
    child = pexpect.spawn(f"{sys.executable} terminal_client.py", env=env, encoding='utf-8', timeout=10)
    
    # 1. Wait for the Main Menu to appear
    child.expect("Main Menu")
    
    # 2. Navigate to 'Exit' 
    # (Main Menu: Create, Select, Options, Exit) -> Need 3 Down arrows
    child.sendline("\x1b[B") # Down
    child.sendline("\x1b[B") # Down
    child.sendline("\x1b[B") # Down
    child.sendline("\r")     # Enter
    
    # 3. Wait for process to exit
    child.expect(pexpect.EOF)
    assert child.isalive() is False
    print("Smoke test passed: CLI started and exited cleanly.")

if __name__ == "__main__":
    test_cli_starts_and_exits()
