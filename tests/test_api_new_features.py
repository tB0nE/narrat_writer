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
