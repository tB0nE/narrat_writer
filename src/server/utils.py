import os
import json
import logging
from typing import Optional, List, Tuple
from src.server.models import GameMetadata, SessionState

logger = logging.getLogger("narrat_api")

def get_game_path(game_id: str, *subpaths):
    """Utility to get full path for game files."""
    games_dir = os.getenv("GARRAT_GAMES_DIR", "games")
    return os.path.join(games_dir, game_id, *subpaths)

def get_script_path(game_id: str, relative_path: str):
    """Helper to get path to a script file within the scripts directory."""
    return get_game_path(game_id, "scripts", relative_path)

def load_metadata(game_id: str, sync: bool = False) -> Optional[GameMetadata]:
    """Loads metadata for a specific game, optionally syncing with folders and script assets."""
    # Migration Check: Move phase1.narrat to scripts/main.narrat
    legacy_p = get_game_path(game_id, "phase1.narrat")
    scripts_dir = get_game_path(game_id, "scripts")
    if os.path.exists(legacy_p):
        os.makedirs(scripts_dir, exist_ok=True)
        # Create subfolders
        for sub in ["chapters", "quests", "interactions"]:
            os.makedirs(os.path.join(scripts_dir, sub), exist_ok=True)
        # Move file
        os.rename(legacy_p, os.path.join(scripts_dir, "main.narrat"))
        logger.info(f"Migrated legacy script for game '{game_id}'")
    elif not os.path.exists(scripts_dir):
        # Ensure scripts dir exists for new games
        os.makedirs(scripts_dir, exist_ok=True)
        for sub in ["chapters", "quests", "interactions"]:
            os.makedirs(os.path.join(scripts_dir, sub), exist_ok=True)

    path = get_game_path(game_id, "metadata.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            meta = GameMetadata(**json.load(f))
        
        if not sync:
            return meta

        from src.server.parser import NarratParser
        parser = NarratParser(game_id)
        detected = parser.detect_assets()

        # 1. Sync Characters with folders
        char_dir = get_game_path(game_id, "reference", "characters")
        if os.path.exists(char_dir):
            existing_folders = [d for d in os.listdir(char_dir) if os.path.isdir(os.path.join(char_dir, d))]
            # Preserve order from meta but filter out missing folders (case-insensitive)
            synced_chars = [c for c in meta.characters if any(f.lower() == c.lower() for f in existing_folders)]
            # Add new folders that aren't already represented in metadata
            for folder in existing_folders:
                if not any(c.lower() == folder.lower() for c in synced_chars):
                    synced_chars.append(folder)
            
            # Add new detected characters from script
            for char in detected["characters"]:
                if not any(c.lower() == char.lower() for c in synced_chars):
                    synced_chars.append(char)
            meta.characters = synced_chars

        # 2. Sync Backgrounds with folders and script
        bg_dir = get_game_path(game_id, "reference", "backgrounds")
        if os.path.exists(bg_dir):
            existing_bgs = [f.replace(".txt", "") for f in os.listdir(bg_dir) if f.endswith(".txt")]
            meta.backgrounds = sorted(list(set(meta.backgrounds) | set(detected["backgrounds"]) | set(existing_bgs)))
        else:
            meta.backgrounds = sorted(list(set(meta.backgrounds) | set(detected["backgrounds"])))

        # 3. Sync Variables from script
        meta.variables = sorted(list(set(meta.variables) | set(detected["variables"])))

        # 4. Sync Scenes from folders
        scene_dir = get_game_path(game_id, "reference", "scenes")
        if os.path.exists(scene_dir):
            existing_scenes = [f.replace(".txt", "") for f in os.listdir(scene_dir) if f.endswith(".txt")]
            meta.scenes = sorted(list(set(meta.scenes) | set(existing_scenes)))
        
        return meta
    return None

def save_metadata(game_id: str, meta: GameMetadata):
    """Saves metadata for a specific game."""
    path = get_game_path(game_id, "metadata.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(meta.model_dump(), f, indent=4)

def load_session(game_id: str, session_id: str) -> SessionState:
    """Loads a specific save session or creates a new one."""
    path = get_game_path(game_id, "saves", f"{session_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            return SessionState(**data)
    meta = load_metadata(game_id)
    return SessionState(session_id=session_id, current_label=meta.starting_point if meta else "main")

def save_session(game_id: str, state: SessionState):
    """Saves the current session state to disk."""
    path = get_game_path(game_id, "saves", f"{state.session_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(state.model_dump_json(indent=2))

def sanitize_env_value(value: str) -> str:
    """Sanitizes environment variable value to prevent newline injection."""
    return str(value).replace("\n", "").replace("\r", "")

def update_env_lines(env_lines: List[str], key: str, value: str) -> Tuple[List[str], str]:
    """Updates or appends an environment variable line in a list of lines."""
    value = sanitize_env_value(value)
    found = False
    for i, line in enumerate(env_lines):
        if line.startswith(f"{key}="):
            env_lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        env_lines.append(f"{key}={value}\n")
    return env_lines, value

def get_reference(game_id: str, category: str, name: str, sub_type: str = None):
    """Fetches a reference text file (character desc, background info, etc.)."""
    if category == "backgrounds":
        path = get_game_path(game_id, "reference", "backgrounds", f"{name}.txt")
    elif category == "scenes":
        path = get_game_path(game_id, "reference", "scenes", f"{name}.txt")
    elif category == "characters":
        suffix = sub_type or "description"
        path = get_game_path(game_id, "reference", "characters", name, f"{name}_{suffix}.txt")
    else:
        return f"[{name} {sub_type or ''} placeholder]"
    
    if os.path.exists(path):
        with open(path, "r") as f: return f.read().strip()
    return f"[{name} {category} missing]"
