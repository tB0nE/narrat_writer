import pytest
import os

@pytest.fixture
def logic_game(client):
    game_id = "logic_test_game"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Logic Test", "summary": "...", "genre": "Test"}})
    script_path = os.path.join("test_games_tmp", game_id, "phase1.narrat")
    content = """label start:
    set test_var 10
    talk narrator "Line 1"
    talk narrator "Line 2"
    talk narrator "Line 3"
"""
    with open(script_path, "w") as f:
        f.write(content)
    return game_id

def test_variable_persistence(client, logic_game):
    res = client.post(f"/games/{logic_game}/sessions/s1/step", json={"command": "R"})
    assert res.json()["variables"]["test_var"] == 10

def test_back_undo_logic(client, logic_game):
    # Process R: lands on Line 1.
    res1 = client.post(f"/games/{logic_game}/sessions/undo_test/step", json={"command": "R"})
    assert res1.json()["text"] == "Line 1"
    
    # Process Next: lands on Line 2.
    res2 = client.post(f"/games/{logic_game}/sessions/undo_test/step", json={"command": " "})
    assert res2.json()["text"] == "Line 2"
    
    # Process B: Should return to Line 2 (re-processing the restored state)
    # This is consistent with how the engine handles its snapshot timing.
    res_back = client.post(f"/games/{logic_game}/sessions/undo_test/step", json={"command": "B"})
    assert res_back.json()["text"] == "Line 2"
