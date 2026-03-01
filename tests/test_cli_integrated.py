import pytest
from unittest.mock import MagicMock, patch
from rich.console import Console
from src.terminal_client.screens.launcher import Launcher
from src.terminal_client.screens.engine import GameEngine

@pytest.fixture
def test_console():
    return Console(width=100, height=40, record=True, color_system=None)

def test_launcher_rendering(test_console):
    launcher = Launcher(custom_console=test_console)
    
    # 1. Capture Intro Screen
    layout = launcher.display_intro(options=["Opt 1", "Opt 2"], selected_idx=0)
    test_console.print(layout)
    text = test_console.export_text()
    
    # Verify key visual markers
    assert "Narrat Writer" in text
    assert "███" in text # Part of the logo
    assert "> Opt 1" in text
    assert "  Opt 2" in text
    assert "Main Menu" in text
    print("Launcher intro rendering verified.")

def test_game_hub_rendering(test_console):
    from src.terminal_client.screens.hub import GameHub
    hub = GameHub(custom_console=test_console, base_url="http://localhost:8045")
    meta = {
        "title": "Cyberpunk Adventure",
        "summary": "A neon story.",
        "genre": "Sci-Fi",
        "characters": ["Anya"]
    }
    
    # Render hub
    layout = hub.render_game_hub(["Start", "Back"], 0, meta)
    test_console.print(layout)
    text = test_console.export_text()
    
    assert "Cyberpunk Adventure" in text
    assert "A neon story." in text
    assert "> Start" in text
    assert "Game Hub" in text
    print("Game Hub rendering verified.")

def test_game_engine_choice_rendering(test_console):
    from src.terminal_client.screens.engine import GameEngine
    engine = GameEngine("test", "sess", custom_console=test_console)
    engine.data = {
        "type": "choice",
        "options": {"1": {"text": "Fight"}, "2": {"text": "Flee"}},
        "dialogue_log": [{"character": "narrator", "text": "A foe appears!"}]
    }
    engine.focus = "choices"
    engine.choice_idx = 0
    
    layout = engine.display_game()
    test_console.print(layout)
    text = test_console.export_text()
    
    assert "A foe appears!" in text
    assert "> Fight" in text
    assert "  Flee" in text
    assert "System / Choices" in text
    print("Game Engine choice rendering verified.")

def test_save_manager_rendering(test_console):
    from src.terminal_client.screens.hub import GameHub
    hub = GameHub(custom_console=test_console, base_url="http://localhost:8045")
    saves = [{
        "id": "autosave",
        "timestamp": 1700000000,
        "label": "main",
        "last_text": "The end?"
    }]
    
    layout = hub.render_save_manager(["autosave", "Back"], 0, saves)
    test_console.print(layout)
    text = test_console.export_text()
    
    assert "Save Preview" in text
    assert "autosave" in text
    assert "The end?" in text
    assert "Location: main" in text
    print("Save Manager rendering verified.")
