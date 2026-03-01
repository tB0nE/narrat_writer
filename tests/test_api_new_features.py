import pytest
import os

def test_save_management_api(client):
    game_id = "api_test_game"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Test", "summary": "...", "genre": "..."}})
    
    # 1. List saves (should have none yet, or just autosave from create if implemented)
    res = client.get(f"/games/{game_id}/saves")
    assert res.status_code == 200
    saves = res.json()["saves"]
    
    # 2. Delete a save (create a dummy file first)
    save_path = os.path.join("test_games_tmp", game_id, "saves", "dummy.json")
    with open(save_path, "w") as f:
        f.write('{"session_id": "dummy", "current_label": "main"}')
    
    res = client.delete(f"/games/{game_id}/saves/dummy")
    assert res.status_code == 200
    assert not os.path.exists(save_path)

def test_surgical_edit_api(client):
    game_id = "edit_test_game"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Test", "summary": "...", "genre": "..."}})
    
    script_path = os.path.join("test_games_tmp", game_id, "phase1.narrat")
    with open(script_path, "w") as f:
        f.write('main:\n    talk narrator "Old Line"\n')
    
    # Mock the LLM call inside the API
    with pytest.MonkeyPatch().context() as mp:
        import main
        mp.setattr(main, "call_llm", lambda prompt, **kwargs: 'talk narrator "New Line"')
        
        res = client.post(f"/games/{game_id}/sessions/any/edit/ai", json={
            "target": "1", # index of the 'talk' line (0 is 'main:')
            "content": "Make it new"
        })
        assert res.status_code == 200
        assert res.json()["new_content"] == 'talk narrator "New Line"'
        
        with open(script_path, "r") as f:
            content = f.read()
        assert 'talk narrator "New Line"' in content

def test_asset_rename_api(client):
    game_id = "rename_api_test"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Sara's Story", "summary": "About Sara", "genre": "Test", "characters": ["Sara"]}})
    
    # Verify Rename
    res = client.post(f"/games/{game_id}/assets/rename", json={
        "category": "characters",
        "old_id": "sara",
        "new_id": "sarah"
    })
    assert res.status_code == 200
    
    meta = client.get(f"/games/{game_id}/metadata").json()
    assert "Sarah" in meta["characters"]
    assert "Sarah" in meta["title"]

def test_asset_generation_api(client):
    game_id = "gen_api_test"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Test", "summary": "...", "genre": "..."}})
    
    with pytest.MonkeyPatch().context() as mp:
        import main
        mp.setattr(main, "call_llm", lambda prompt, **kwargs: "AI Generated Description")
        
        res = client.post(f"/games/{game_id}/assets/generate", json={
            "category": "backgrounds",
            "target": "forest"
        })
        assert res.status_code == 200
        
        path = os.path.join("test_games_tmp", game_id, "reference", "backgrounds", "forest.txt")
        assert os.path.exists(path)
        with open(path, "r") as f:
            assert f.read() == "AI Generated Description"

def test_metadata_regeneration_api(client):
    game_id = "regen_api_test"
    client.post("/games/create", json={"name": game_id, "manual_data": {"title": "Old Title", "summary": "Old Summary", "genre": "Test"}})
    
    with pytest.MonkeyPatch().context() as mp:
        import main
        # Return a JSON-like string as the AI content
        mp.setattr(main, "call_llm", lambda prompt, **kwargs: '{"title": "New Title", "summary": "New Summary", "genre": "Sci-Fi"}')
        
        res = client.post(f"/games/{game_id}/regenerate", json={"name": game_id, "prompt": "Make it better"})
        assert res.status_code == 200
        assert res.json()["metadata"]["title"] == "New Title"
        
        meta = client.get(f"/games/{game_id}/metadata").json()
        assert meta["title"] == "New Title"
