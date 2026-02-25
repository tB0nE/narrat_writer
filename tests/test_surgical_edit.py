import pytest
import os

@pytest.fixture
def edit_game(client):
    game_id = "edit_test_game"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Edit Test", "summary": "...", "genre": "Test"}})
    return game_id

def test_script_surgical_update(client, edit_game):
    # Find the first talk line
    path = os.path.join("test_games_tmp", edit_game, "phase1.narrat")
    with open(path, "r") as f: lines = f.readlines()
    target_idx = next(i for i, l in enumerate(lines) if "talk" in l)
    
    payload = {"category": "script", "action": "update", "target": str(target_idx), "content": 'talk anya "Changed line."'}
    client.post(f"/games/{edit_game}/sessions/any/edit", json=payload)
    
    res = client.post(f"/games/{edit_game}/sessions/s1/step", json={"command": "R"})
    assert "Changed line" in res.json()["text"]

def test_script_surgical_insert(client, edit_game):
    path = os.path.join("test_games_tmp", edit_game, "phase1.narrat")
    with open(path, "r") as f: lines = f.readlines()
    target_idx = next(i for i, l in enumerate(lines) if "talk" in l)

    payload = {"category": "script", "action": "insert", "target": str(target_idx), "content": 'talk anya "Inserted line."'}
    client.post(f"/games/{edit_game}/sessions/any/edit", json=payload)
    
    # Reload and step
    client.post(f"/games/{edit_game}/sessions/fresh_s/step", json={"command": "R"})
    res = client.post(f"/games/{edit_game}/sessions/fresh_s/step", json={"command": " "})
    
    log = res.json()["dialogue_log"]
    assert any("Inserted line" in entry["text"] for entry in log)

def test_reference_asset_update(client, edit_game):
    payload = {"category": "reference", "action": "update", "sub_category": "background", "target": "new_bg", "content": "Sunrise."}
    client.post(f"/games/{edit_game}/sessions/any/edit", json=payload)
    path = os.path.join("test_games_tmp", edit_game, "reference", "backgrounds", "new_bg.txt")
    with open(path, "r") as f: assert f.read() == "Sunrise."

def test_character_metadata_update(client, edit_game):
    payload = {"category": "reference", "action": "update", "sub_category": "character", "target": "anya", "content": "Hacker.", "meta": {"type": "profile"}}
    client.post(f"/games/{edit_game}/sessions/any/edit", json=payload)
    path = os.path.join("test_games_tmp", edit_game, "reference", "characters", "anya", "anya_profile.txt")
    with open(path, "r") as f: assert f.read() == "Hacker."
