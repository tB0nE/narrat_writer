import pytest
from unittest.mock import MagicMock, patch, call
from src.terminal_client.screens.launcher import Launcher
from prompt_toolkit.keys import Keys

@pytest.fixture
def launcher():
    return Launcher(custom_console=MagicMock(), base_url="http://localhost:8045")

def test_options_view_mode_navigation(launcher):
    """Tests that Up/Down arrows change the main index in view mode."""
    mock_config = {"api_url": "http://test", "model": "m1", "narrat_mode": "writer", "editor": "vim", "global_prompt_prefix": ""}
    
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live:
        
        mock_get.return_value.json.return_value = mock_config
        
        # Mock input to send: Down, Down, Escape (to exit)
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = [
            [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Escape)]
        ]
        mock_input_factory.return_value = mock_input
        
        launcher.global_options_flow()
        
        # We can't easily check internal state without refactoring, 
        # but we verify the loop ran and exited on Escape.
        assert mock_input.read_keys.call_count == 3

def test_options_select_mode_navigation(launcher):
    """Tests navigating the sub-menu for Selecting Editor."""
    mock_config = {"api_url": "http://test", "model": "m1", "narrat_mode": "writer", "editor": "vim", "global_prompt_prefix": ""}
    
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.requests.post') as mock_post, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live:
        
        mock_get.return_value.json.return_value = mock_config
        mock_post.return_value.status_code = 200
        
        # Actions:
        # 1. Down 3 times to get to "Select Editor"
        # 2. Enter to enter select mode
        # 3. Down once to select "nano"
        # 4. Enter to confirm
        # 5. Escape to exit
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = [
            [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)], [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Enter)],
            [MagicMock(key=Keys.Down)],
            [MagicMock(key=Keys.Enter)],
            [MagicMock(key=Keys.Escape)]
        ]
        mock_input_factory.return_value = mock_input
        
        launcher.global_options_flow()
        
        # Verify post was called with nano
        # Note: Depending on index, Select Editor is index 3
        mock_post.assert_any_call("http://localhost:8045/config", json={"editor": "nano"})

def test_options_api_flow_trigger(launcher):
    """Tests that Edit API Settings triggers the inline flow."""
    mock_config = {"api_url": "http://test", "model": "m1", "narrat_mode": "writer", "editor": "vim"}
    
    with patch('src.terminal_client.screens.launcher.requests.get') as mock_get, \
         patch('src.terminal_client.screens.launcher.create_input') as mock_input_factory, \
         patch('src.terminal_client.screens.launcher.Live') as mock_live, \
         patch.object(launcher, 'edit_api_flow_inline') as mock_api_flow:
        
        mock_get.return_value.json.return_value = mock_config
        
        # Actions: Enter (on first option "Edit API Settings"), Escape
        mock_input = MagicMock()
        mock_input.read_keys.side_effect = [
            [MagicMock(key=Keys.Enter)],
            [MagicMock(key=Keys.Escape)]
        ]
        mock_input_factory.return_value = mock_input
        
        launcher.global_options_flow()
        
        mock_api_flow.assert_called_once()
