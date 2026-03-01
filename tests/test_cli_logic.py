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
