import pytest

@pytest.fixture
def test_game(client):
    """Fixture to ensure a game exists for testing."""
    game_id = "test_fixture_game"
    payload = {
        "name": game_id,
        "manual_data": {
            "title": "Test Fixture Title",
            "summary": "Fixture summary",
            "genre": "Testing"
        }
    }
    client.post("/games/create", json=payload)
    return game_id

def test_list_games(client, test_game):
    response = client.get("/games")
    assert response.status_code == 200
    games = response.json()["games"]
    assert any(g["id"] == test_game for g in games)

def test_get_metadata(client, test_game):
    response = client.get(f"/games/{test_game}/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Fixture Title"

def test_step_game_start(client, test_game):
    payload = {"command": "R"} 
    response = client.post(f"/games/{test_game}/sessions/test_session/step", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "talk"
    assert "Welcome" in data["text"]
    assert data["current_label"] == "main"

def test_edit_metadata(client, test_game):
    payload = {
        "category": "metadata",
        "action": "update",
        "target": "title",
        "content": "Updated via Test"
    }
    response = client.post(f"/games/{test_game}/sessions/any/edit", json=payload)
    assert response.status_code == 200
    
    # Verify change
    response = client.get(f"/games/{test_game}/metadata")
    assert response.json()["title"] == "Updated via Test"

def test_invalid_game_step(client):
    response = client.post("/games/non_existent/sessions/s/step", json={"command": " "})
    # Parser returns end type for missing files
    assert response.json()["type"] == "end"
