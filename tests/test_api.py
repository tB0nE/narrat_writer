import pytest

def test_list_games_empty(client):
    response = client.get("/games")
    assert response.status_code == 200
    assert response.json() == {"games": []}

def test_create_game_manual(client):
    payload = {
        "name": "test_manual_game",
        "manual_data": {
            "title": "Test Manual Title",
            "summary": "This is a test summary",
            "genre": "Test Genre"
        }
    }
    response = client.post("/games/create", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["game_id"] == "test_manual_game"

def test_get_metadata(client):
    # Relies on test_create_game_manual having run or similar
    response = client.get("/games/test_manual_game/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Manual Title"
    assert data["genre"] == "Test Genre"

def test_step_game_start(client):
    # Test starting a session
    payload = {"command": "R"} # Reset/Start
    response = client.post("/games/test_manual_game/sessions/test_session/step", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "talk"
    assert "Welcome" in data["text"]
    assert data["current_label"] == "start"

def test_edit_metadata(client):
    payload = {
        "category": "metadata",
        "action": "update",
        "target": "title",
        "content": "Updated Title"
    }
    response = client.post("/games/test_manual_game/sessions/any/edit", json=payload)
    assert response.status_code == 200
    
    # Verify change
    response = client.get("/games/test_manual_game/metadata")
    assert response.json()["title"] == "Updated Title"

def test_invalid_game_step(client):
    response = client.post("/games/non_existent/sessions/s/step", json={"command": " "})
    # Our current logic might fail differently depending on file ops, 
    # but let's see if it handles missing games gracefully.
    # Currently it might return DialogueResponse type='end' or similar if parser fails.
    assert response.status_code == 200 # Type 'end' is returned currently
    assert response.json()["type"] == "end"
