import pytest
from unittest.mock import MagicMock, patch
from src.terminal_client.screens.launcher import Launcher
from prompt_toolkit.keys import Keys

@pytest.fixture
def launcher():
    return Launcher(custom_console=MagicMock(), base_url="http://localhost:8045")

def mock_input_generator(sequence):
    for item in sequence:
        yield item
    # Provide enough empty results to avoid immediate failure but 
    # eventually raise StopIteration if the loop never ends.
    for _ in range(50):
        yield []

def test_launcher_navigates_to_select_game(launcher):
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live, \
         patch.object(launcher, 'select_game_flow_shared') as mock_select_flow:
        
        mock_get.return_value.json.return_value = {"api_url": "..."}
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = mock_input_generator([
            [MagicMock(key=Keys.Enter)],
            [MagicMock(key=Keys.Escape)]
        ])
        mock_input_factory.return_value = mock_input
        
        launcher.run()
        mock_select_flow.assert_called_once()

def test_launcher_navigates_to_create_game(launcher):
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live, \
         patch.object(launcher, 'create_game_flow') as mock_create_flow:
        
        mock_get.return_value.json.return_value = {"api_url": "..."}
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = mock_input_generator([
            [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Enter)],
            [MagicMock(key=Keys.Escape)]
        ])
        mock_input_factory.return_value = mock_input
        
        launcher.run()
        mock_create_flow.assert_called_once()

def test_launcher_navigates_to_options(launcher):
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live, \
         patch.object(launcher, 'global_options_flow_shared') as mock_options_flow:
        
        mock_get.return_value.json.return_value = {"api_url": "..."}
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = mock_input_generator([
            [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Enter)],
            [MagicMock(key=Keys.Escape)]
        ])
        mock_input_factory.return_value = mock_input
        
        launcher.run()
        mock_options_flow.assert_called_once()

def test_select_game_flow_triggers_hub(launcher):
    mock_games = {"games": [{"id": "game1", "title": "Game 1", "summary": "..."}]}
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live, \
         patch('src.terminal_client.screens.hub.GameHub.run') as mock_hub_run:
        
        mock_get.return_value.json.return_value = mock_games
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = mock_input_generator([[MagicMock(key=Keys.Enter)]])
        mock_input_factory.return_value = mock_input
        
        launcher.select_game_flow_shared(mock_live, mock_input)
        mock_hub_run.assert_called_once_with("game1")

def test_global_options_flow_triggers_config(launcher):
    mock_config = {"api_url": "http://api", "model": "m", "narrat_mode": "writer", "editor": "vim"}
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live:
        
        mock_get.return_value.json.return_value = mock_config
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = mock_input_generator([[MagicMock(key=Keys.Escape)]])
        mock_input_factory.return_value = mock_input
        
        launcher.global_options_flow_shared(mock_live, mock_input)
        mock_get.assert_called()
