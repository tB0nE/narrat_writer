import pytest
import re
from unittest.mock import MagicMock, patch
from src.terminal_client.screens.launcher import Launcher

@pytest.fixture
def launcher():
    return Launcher(custom_console=MagicMock(), base_url="http://localhost:8045")

def test_auto_id_generation(launcher):
    """Verifies that IDs are generated correctly from titles."""
    # Mock games list to test collision
    mock_games = {"games": [{"id": "test_game", "title": "Test Game"}]}
    
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.questionary.select') as mock_select, \
         patch('src.terminal_client.screens.launcher.questionary.text') as mock_text, \
         patch('src.terminal_client.screens.launcher.requests.post') as mock_post, \
         patch('src.terminal_client.screens.hub.GameHub.run') as mock_hub:
        
        # 1. Choose Manual
        mock_select.return_value.ask.return_value = "Manual"
        # 2. Set Title to "Test Game" (should collide with existing and become test_game_2)
        mock_text.return_value.ask.side_effect = ["Test Game", "A summary"]
        
        mock_get.side_effect = [
            MagicMock(json=lambda: mock_games), # list_games
            MagicMock(json=lambda: {"editor": "None"}) # get_config
        ]
        mock_post.return_value.status_code = 200
        
        launcher.create_game_flow()
        
        # Verify post used the auto-incremented ID
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]['json']
        assert payload["name"] == "test_game_2"
        assert payload["manual_data"]["title"] == "Test Game"

def test_manual_creation_skips_ai(launcher):
    """Verifies that manual creation sends manual_data and no prompt."""
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.questionary.select') as mock_select, \
         patch('src.terminal_client.screens.launcher.questionary.text') as mock_text, \
         patch('src.terminal_client.screens.launcher.requests.post') as mock_post, \
         patch('src.terminal_client.screens.hub.GameHub.run') as mock_hub:
        
        mock_select.return_value.ask.return_value = "Manual"
        mock_text.return_value.ask.side_effect = ["My New Game", "Summary here"]
        
        mock_get.side_effect = [
            MagicMock(json=lambda: {"games": []}),
            MagicMock(json=lambda: {"editor": "None"})
        ]
        mock_post.return_value.status_code = 200
        
        launcher.create_game_flow()
        
        payload = mock_post.call_args[1]['json']
        assert "manual_data" in payload
        assert "prompt" not in payload
        assert payload["name"] == "my_new"

def test_ai_assisted_creation_uses_external_editor(launcher):
    """Verifies that AI Assisted flow uses external editor if configured."""
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.questionary.select') as mock_select, \
         patch('src.terminal_client.screens.launcher.questionary.text') as mock_text, \
         patch('src.terminal_client.utils.edit_text_in_external_editor') as mock_edit, \
         patch('src.terminal_client.screens.launcher.requests.post') as mock_post, \
         patch('src.terminal_client.screens.hub.GameHub.run') as mock_hub:
        
        mock_select.return_value.ask.return_value = "AI Assisted"
        mock_text.return_value.ask.return_value = "AI Game" # Title
        mock_edit.return_value = "Extensive AI Prompt"
        
        mock_get.side_effect = [
            MagicMock(json=lambda: {"games": []}),
            MagicMock(json=lambda: {"editor": "vim"})
        ]
        mock_post.return_value.status_code = 200
        
        launcher.create_game_flow()
        
        mock_edit.assert_called_once_with("")
        payload = mock_post.call_args[1]['json']
        assert payload["prompt"] == "Extensive AI Prompt"
        assert payload["name"] == "ai_game"
