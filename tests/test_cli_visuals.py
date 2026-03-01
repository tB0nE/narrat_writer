import pytest
from terminal_client import Launcher
from rich.console import Console
from unittest.mock import MagicMock
import os

def test_intro_screen_visual_snapshot():
    launcher = Launcher()
    # Create a console that records its output
    recording_console = Console(width=100, height=30, record=True, color_system="truecolor")
    
    # We need to temporarily patch the global 'console' in terminal_client.py
    import terminal_client
    original_console = terminal_client.console
    terminal_client.console = recording_console
    
    try:
        # Mock options and selection
        options = ["Create Game", "Select Game", "Options", "Exit"]
        selected_idx = 0
        
        # Render the intro layout
        layout = launcher.display_intro(options, selected_idx)
        recording_console.print(layout)
        
        # Get the exported text
        rendered_text = recording_console.export_text()
        
        # Define snapshot path
        snapshot_dir = "tests/snapshots"
        os.makedirs(snapshot_dir, exist_ok=True)
        snapshot_path = os.path.join(snapshot_dir, "intro_screen.txt")
        
        if not os.path.exists(snapshot_path):
            # Create the initial "golden" snapshot
            with open(snapshot_path, "w") as f:
                f.write(rendered_text)
            pytest.skip(f"Snapshot created at {snapshot_path}. Run again to verify.")
        
        # Compare current rendering with snapshot
        with open(snapshot_path, "r") as f:
            golden_text = f.read()
        
        assert rendered_text == golden_text, "Intro screen visual regression detected!"
        print("Intro screen visual snapshot matches.")
        
    finally:
        # Restore original console
        terminal_client.console = original_console

if __name__ == "__main__":
    test_intro_screen_visual_snapshot()
