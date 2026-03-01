import pytest
from unittest.mock import MagicMock, patch
from client import Launcher

def test_launcher_navigation_logic():
    launcher = Launcher()
    
    # Mock dependencies
    with patch('client.requests.get') as mock_get, \
         patch('client.questionary.select') as mock_select, \
         patch('client.Launcher.get_menu_choice') as mock_menu:
        
        # 1. Simulate selecting 'Exit' immediately
        mock_menu.return_value = "Exit"
        
        with pytest.raises(SystemExit):
            launcher.run()
        
        print("Launcher correctly exits on 'Exit' choice.")

def test_game_hub_loading():
    launcher = Launcher()
    game_id = "test_game"
    
    # Mock the metadata response
    mock_meta = {
        "title": "Test Game",
        "summary": "A test summary",
        "genre": "Test",
        "characters": ["A", "B"],
        "plot_outline": "The plot"
    }
    
    with patch('client.requests.get') as mock_get, \
         patch('client.Launcher.get_menu_choice') as mock_menu:
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_meta
        mock_get.return_value = mock_response
        
        # Simulate selecting 'Back' from the Hub
        mock_menu.return_value = "Back"
        
        launcher.game_hub(game_id)
        
        # Verify correct metadata was requested
        mock_get.assert_called_with(f"http://localhost:8045/games/{game_id}/metadata")
        print("Game Hub correctly loads metadata and handles 'Back'.")

def test_game_engine_focus_logic():
    from client import GameEngine
    engine = GameEngine("test_game", "test_session")
    
    # Initially should focus actions
    assert engine.focus == "actions"
    
    # Mock data with a choice
    engine.data = {"type": "choice", "options": {"1": {"text": "Opt 1"}}}
    
    # In a real run, Tab would toggle this. Let's verify our renderers respect it.
    engine.focus = "choices"
    choice_output = engine.get_choices_list()
    assert "> [bold yellow]Opt 1[/bold yellow]" in choice_output
    
    engine.focus = "actions"
    action_output = engine.get_actions_row()
    assert "[bold yellow reverse]Next[/bold yellow reverse]" in action_output
    print("GameEngine focus and rendering logic verified.")

def test_asset_manager_navigation():
    launcher = Launcher()
    meta = {"title": "Test"}
    
    with patch('client.requests.get') as mock_get, \
         patch('client.questionary.select') as mock_select:
        
        # We need to handle the nested while True loops.
        # Outer loop: Category selection
        # Inner loop: Asset selection
        mock_select.side_effect = [
            MagicMock(ask=MagicMock(return_value="Characters")), # Select category
            MagicMock(ask=MagicMock(return_value="Back")),       # Exit inner loop
            MagicMock(ask=MagicMock(return_value="Back"))        # Exit outer loop
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"assets": ["char1", "char2"]}
        mock_get.return_value = mock_response
        
        launcher.asset_manager_flow("test_game", meta)
        
        # Verify it fetched characters
        mock_get.assert_called_with("http://localhost:8045/games/test_game/assets/characters")
        print("Asset Manager correctly handles nested navigation.")
