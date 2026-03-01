import pytest
import os
import json
import re

def test_character_global_rename(client):
    # 1. Setup a dummy game
    game_id = "rename_test_game"
    client.post("/games/create", json={
        "name": game_id,
        "manual_data": {
            "title": "Renaming Sara",
            "summary": "This is a story about Sara.",
            "genre": "Test",
            "characters": ["Sara"],
            "plot_outline": "Sara went to the market."
        }
    })
    
    # 2. Add a custom script
    script_path = os.path.join("test_games_tmp", game_id, "phase1.narrat")
    content = """main:
    talk sara "Hi, I am Sara."
    sara "Sara is my name."
    talk narrator "You see Sara standing there."
"""
    with open(script_path, "w") as f:
        f.write(content)

    # 3. Perform Global Rename
    response = client.post(f"/games/{game_id}/assets/rename", json={
        "category": "characters",
        "old_id": "sara",
        "new_id": "sarah"
    })
    assert response.status_code == 200

    # 4. Verify Metadata
    res_meta = client.get(f"/games/{game_id}/metadata")
    meta = res_meta.json()
    assert "Sarah" in meta["characters"]
    assert "sarah" not in [c.lower() for c in meta["characters"] if c.lower() == "sara"]
    assert "Sarah" in meta["title"]
    assert "Sarah" in meta["summary"]
    assert "Sarah" in meta["plot_outline"]

    # 5. Verify Script
    with open(script_path, "r") as f:
        new_content = f.read()
    
    assert 'talk sarah "Hi, I am Sarah."' in new_content
    assert 'sarah "Sarah is my name."' in new_content
    assert 'talk narrator "You see Sarah standing there."' in new_content
    
    # Check that 'sara' as a whole word is gone
    assert not re.search(r'\bsara\b', new_content, re.IGNORECASE)

if __name__ == "__main__":
    # If run directly, we need a mock client or just run via pytest
    pass
