import pytest
from unittest.mock import MagicMock, patch
from src.terminal_client.screens.launcher import Launcher

@pytest.fixture
def launcher():
    return Launcher(custom_console=MagicMock(), base_url="http://localhost:8045")

def test_launcher_navigates_to_create_game(launcher):
    with patch('src.terminal_client.utils.get_menu_choice') as mock_menu, \
         patch.object(launcher, 'create_game_flow') as mock_create_flow:
        
        # 1. Select 'Create Game'
        # 2. Select 'Exit' (to break the while True loop)
        mock_menu.side_effect = ["Create Game", "Exit"]
        
        with pytest.raises(SystemExit):
            launcher.run()
        
        mock_create_flow.assert_called_once()

def test_launcher_navigates_to_select_game(launcher):
    with patch('src.terminal_client.utils.get_menu_choice') as mock_menu, \
         patch.object(launcher, 'select_game_flow') as mock_select_flow:
        
        # 1. Select 'Select Game'
        # 2. Select 'Exit'
        mock_menu.side_effect = ["Select Game", "Exit"]
        
        with pytest.raises(SystemExit):
            launcher.run()
        
        mock_select_flow.assert_called_once()

def test_launcher_navigates_to_options(launcher):
    with patch('src.terminal_client.utils.get_menu_choice') as mock_menu, \
         patch.object(launcher, 'global_options_flow') as mock_options_flow:
        
        # 1. Select 'Options'
        # 2. Select 'Exit'
        mock_menu.side_effect = ["Options", "Exit"]
        
        with pytest.raises(SystemExit):
            launcher.run()
        
        mock_options_flow.assert_called_once()

def test_select_game_flow_triggers_hub(launcher):
    mock_games = {"games": [{"id": "game1", "title": "Game 1", "summary": "..."}]}
    
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.utils.get_menu_choice') as mock_menu, \
         patch('src.terminal_client.screens.hub.GameHub.run') as mock_hub_run:

        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_games
        mock_get.return_value = mock_response
        
        # Simulate selecting "game1"
        mock_menu.return_value = "game1"
        
        launcher.select_game_flow()
        
        mock_hub_run.assert_called_once_with("game1")

def test_global_options_flow_triggers_config(launcher):
    mock_config = {
        "api_url": "http://api",
        "model": "m",
        "narrat_mode": "writer",
        "global_prompt_prefix": "p",
        "editor": "vim"
    }
    
    from prompt_toolkit.keys import Keys
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live:
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_config
        mock_get.return_value = mock_response
        
        # Simulate pressing 'Escape' to exit the loop immediately
        mock_input = MagicMock()
        mock_input.read_keys.return_value = [MagicMock(key=Keys.Escape)]
        mock_input_factory.return_value = mock_input
        
        launcher.global_options_flow()
        
        # Verify it fetched config
        mock_get.assert_called()
