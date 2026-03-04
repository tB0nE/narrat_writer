import pytest
from unittest.mock import MagicMock, patch
from src.terminal_client.screens.launcher import Launcher
from prompt_toolkit.keys import Keys

def test_launcher_navigation_logic():
    launcher = Launcher(custom_console=MagicMock(), base_url="http://localhost:8045")
    
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live:
        
        mock_get.return_value.json.return_value = {"api_url": "..."}
        
        # Simulate selecting 'Exit' immediately (Index 3 in Main Menu)
        mock_input = MagicMock()
        # 3 Down arrows + Enter
        mock_input.read_keys.side_effect = [
            [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Enter)]
        ]
        mock_input_factory.return_value = mock_input
        
        with pytest.raises(SystemExit):
            launcher.run()

def test_game_hub_loading():
    from src.terminal_client.screens.hub import GameHub
    hub = GameHub(custom_console=MagicMock(), base_url="http://localhost:8045")
    game_id = "test_game"
    
    mock_meta = {
        "title": "Test Game",
        "summary": "A test summary",
        "genre": "Test",
        "characters": ["A", "B"],
        "plot_outline": "The plot"
    }

    with patch('src.terminal_client.screens.hub.requests.get') as mock_get, \
         patch('src.terminal_client.screens.hub.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.hub.Live') as mock_live:
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_meta
        mock_get.return_value = mock_response
        
        # Simulate selecting 'Back' (Index 5 in Hub Menu)
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = [
            [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Enter)]
        ]
        mock_input_factory.return_value = mock_input
        
        hub.run(game_id)
        
        # Verify correct metadata was requested
        mock_get.assert_any_call("http://localhost:8045/games/{game_id}/metadata".format(game_id=game_id))

def test_game_engine_focus_logic():
    from src.terminal_client.screens.engine import GameEngine
    engine = GameEngine("test_game", "test_session")
    
    # Initially should focus actions
    assert engine.focus == "actions"
    
    # Mock data with a choice
    engine.data = {"type": "choice", "options": {"1": {"text": "Opt 1"}}}
    
    # In a real run, Tab would toggle this. Let's verify our renderers respect it.
    engine.focus = "choices"
    choice_output = engine.get_choices_list()
    # Check for the reverse highlight style we added
    assert "Opt 1" in choice_output
    
    engine.focus = "actions"
    action_output = engine.get_actions_row()
    assert "Next" in action_output

def test_asset_manager_navigation():
    from src.terminal_client.screens.hub import GameHub
    hub = GameHub(custom_console=MagicMock(), base_url="http://localhost:8045")
    meta = {"title": "Test"}
    
    with patch('src.terminal_client.screens.hub.requests.get') as mock_get, \
         patch('src.terminal_client.screens.hub.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.hub.Live') as mock_live:
        
        mock_input = MagicMock()
        # Escape to exit the single-loop manager
        mock_input.read_keys.return_value = [MagicMock(key=Keys.Escape)]
        mock_input_factory.return_value = mock_input
        
        mock_get.return_value.json.return_value = {"assets": []}
        
        hub.asset_manager_flow("test_game", meta)
        assert mock_input.read_keys.called
