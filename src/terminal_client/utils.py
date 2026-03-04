import os
import sys
import time
import subprocess
import requests
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys

console = Console()
BASE_URL = "http://localhost:8045"

def ensure_server_running():
    """Checks if server is up, starts it if not."""
    try:
        requests.get(f"{BASE_URL}/games", timeout=0.5)
        return None
    except:
        log_file = open("narrat_server.log", "a")
        proc = subprocess.Popen(
            [sys.executable, "server.py"],
            stdout=subprocess.DEVNULL,
            stderr=log_file,
            preexec_fn=os.setsid
        )
        for _ in range(15):
            try:
                requests.get(f"{BASE_URL}/games", timeout=0.5)
                return proc
            except:
                time.sleep(0.5)
        return proc

def make_intro_layout() -> Layout:
    """Creates the primary 70/30 split layout."""
    layout = Layout()
    layout.split_row(
        Layout(name="left", ratio=7),
        Layout(name="right", ratio=3)
    )
    return layout

def get_menu_choice(options, make_layout_func):
    """Interactive menu loop using rich.Live and prompt_toolkit."""
    if os.getenv("NARRAT_TEST_MODE") == "1":
        from rich.console import Console
        Console().print(make_layout_func(options, 0))
        import questionary
        return questionary.select("Menu", choices=options).ask()

    idx = 0
    input_obj = create_input()
    with Live(make_layout_func(options, idx), auto_refresh=False, screen=True) as live:
        with input_obj.raw_mode():
            while True:
                live.update(make_layout_func(options, idx))
                live.refresh()
                keys = input_obj.read_keys()
                if not keys:
                    if os.getenv("NARRAT_TEST_MODE") != "1":
                        time.sleep(0.05)
                    continue
                for key in keys:
                    if key.key == Keys.Up: idx = (idx - 1) % len(options)
                    elif key.key == Keys.Down: idx = (idx + 1) % len(options)
                    elif key.key == Keys.Enter or key.key == Keys.ControlM: return options[idx]
                    elif key.key == Keys.ControlC: sys.exit()

import tempfile

def open_in_external_editor(filepath: str, line_number: int = 1):
    """Opens the specified file in the system's default editor at the given line."""
    editor = os.getenv("EDITOR", "vim")
    
    cmd = [editor]
    # Standard 'jump to line' flags for common editors
    if "vim" in editor or "vi" in editor or "nano" in editor or "emacs" in editor:
        cmd.append(f"+{line_number}")
    elif "code" in editor: # VS Code
        cmd.extend(["--goto", f"{filepath}:{line_number}"])
    elif "subl" in editor: # Sublime Text
        cmd.append(f"{filepath}:{line_number}")
    
    if "code" not in editor and "subl" not in editor:
        cmd.append(filepath)
        
    try:
        subprocess.call(cmd)
    except Exception as e:
        console.print(f"[red]Failed to open editor: {e}[/red]")
        time.sleep(2)

def edit_text_in_external_editor(initial_text: str) -> str:
    """Opens an external editor with the initial_text and returns the edited version."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w+t") as tf:
        tf.write(initial_text)
        temp_path = tf.name
    
    open_in_external_editor(temp_path)
    
    with open(temp_path, "r") as tf:
        edited_text = tf.read().strip()
    
    try:
        os.remove(temp_path)
    except:
        pass
    
    return edited_text
