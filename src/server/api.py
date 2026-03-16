import os
import json
import re
import shutil
import logging
import requests as sync_requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any

import prompts
from src.server.models import (
    GameMetadata, SessionState, GameUpdate, 
    CreateGameRequest, GenerateRequest, DialogueResponse
)
from src.server.utils import (
    get_game_path, get_script_path, load_metadata, save_metadata, 
    load_session, save_session, get_reference
)
from src.server.parser import NarratParser, evaluate_expression
from src.server.ai import call_llm
from src.server.api_logic import process_current_step

logger = logging.getLogger("narrat_api")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("narrat_server.log"),
        logging.StreamHandler()
    ]
)
NARRAT_MODE = os.getenv("NARRAT_MODE", "developer")

app = FastAPI(title="Headless Narrat API", version="0.2.0")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error during {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": "server_error"}
    )

# --- API ENDPOINTS ---

@app.get("/config")
async def get_api_config():
    return {
        "api_url": os.getenv("API_URL", ""),
        "model": os.getenv("API_MODEL", ""),
        "api_key": os.getenv("API_KEY", ""),
        "narrat_mode": os.getenv("NARRAT_MODE", "writer"),
        "global_prompt_prefix": os.getenv("GLOBAL_PROMPT_PREFIX", ""),
        "editor": os.getenv("EDITOR", "vim")
    }

@app.post("/config/test")
async def test_api_config(req: Dict[str, str]):
    url, key = req.get("api_url"), req.get("api_key")
    if not url or not key:
        raise HTTPException(status_code=400, detail="Missing URL or Key")
    
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    models_url = url.replace("/chat/completions", "/models")
    try:
        res = sync_requests.get(models_url, headers=headers, timeout=10)
        if res.status_code == 200:
            models = [m["id"] for m in res.json().get("data", [])]
            return {"status": "success", "models": models}
        test_payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
        res = sync_requests.post(url, json=test_payload, headers=headers, timeout=10)
        res.raise_for_status()
        return {"status": "success", "models": []}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/config/models")
async def get_available_models():
    url = os.getenv("API_URL")
    key = os.getenv("API_KEY")
    if not url or not key: return {"models": []}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    models_url = url.replace("/chat/completions", "/models")
    try:
        res = sync_requests.get(models_url, headers=headers, timeout=10)
        if res.status_code == 200:
            return {"models": [m["id"] for m in res.json().get("data", [])]}
    except: pass
    return {"models": []}

@app.post("/config")
async def update_api_config(new_config: Dict[str, Any]):
    env_path = ".env"
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f: env_lines = f.readlines()
    def update_env_line(key, value):
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith(f"{key}="):
                env_lines[i] = f"{key}={value}\n"; found = True; break
        if not found: env_lines.append(f"{key}={value}\n")
        os.environ[key] = str(value)
    mappable = {"global_prompt_prefix": "GLOBAL_PROMPT_PREFIX", "editor": "EDITOR", "api_url": "API_URL", "api_key": "API_KEY", "model": "API_MODEL", "narrat_mode": "NARRAT_MODE"}
    for k, env_k in mappable.items():
        if k in new_config: update_env_line(env_k, new_config[k])
    with open(env_path, "w") as f: f.writelines(env_lines)
    return {"status": "success", "config": await get_api_config()}

@app.get("/games")
async def list_games():
    """Lists all games currently available, sorted by last played/updated."""
    games_dir = os.getenv("GARRAT_GAMES_DIR", "games")
    if not os.path.exists(games_dir): return {"games": []}
    
    games = []
    for d in os.listdir(games_dir):
        game_path = os.path.join(games_dir, d)
        if os.path.isdir(game_path):
            # Determine last updated time (newest save or metadata)
            last_time = 0
            meta_path = os.path.join(game_path, "metadata.json")
            if os.path.exists(meta_path):
                last_time = os.path.getmtime(meta_path)
            
            saves_dir = os.path.join(game_path, "saves")
            if os.path.exists(saves_dir):
                for f in os.listdir(saves_dir):
                    if f.endswith(".json"):
                        last_time = max(last_time, os.path.getmtime(os.path.join(saves_dir, f)))
            
            meta = load_metadata(d, sync=True)
            if meta: 
                games.append({
                    "id": d, "title": meta.title, "summary": meta.summary, 
                    "genre": meta.genre, "characters": meta.characters, 
                    "plot_outline": meta.plot_outline, "last_updated": last_time
                })
    
    # Sort by last_updated descending
    games.sort(key=lambda x: x["last_updated"], reverse=True)
    return {"games": games}

@app.get("/games/{game_id}/validate")
async def validate_game_script(game_id: str):
    parser = NarratParser(game_id)
    is_valid, errors = parser.validate()
    return {"valid": is_valid, "errors": errors}

@app.get("/games/{game_id}/labels")
async def get_game_labels(game_id: str):
    try:
        parser = NarratParser(game_id)
        return {"labels": list(parser.labels.keys())}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/{game_id}/label_map")
async def get_game_label_map(game_id: str):
    try:
        parser = NarratParser(game_id)
        return {"label_map": parser.label_to_file}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/games/{game_id}/metadata")
async def get_game_metadata(game_id: str):
    meta = load_metadata(game_id, sync=True)
    if meta: return meta
    raise HTTPException(status_code=404, detail="Game not found")

@app.post("/games/create")
async def create_game(req: CreateGameRequest):
    games_dir = os.getenv("GARRAT_GAMES_DIR", "games")
    game_dir = os.path.join(games_dir, req.name)
    if os.path.exists(game_dir): raise HTTPException(status_code=400, detail="Game ID already exists")
    os.makedirs(game_dir, exist_ok=True)
    if req.prompt:
        ai_prompt = prompts.GENERATE_METADATA_PROMPT.format(user_prompt=req.prompt)
        try:
            raw = call_llm(ai_prompt, game_id=req.name)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match: meta = GameMetadata(**json.loads(match.group(0)))
            else: raise HTTPException(status_code=500, detail="AI returned invalid format")
        except Exception as e:
            logger.exception("AI creation error")
            raise HTTPException(status_code=500, detail=str(e))
    else: meta = req.manual_data or GameMetadata(title=req.name, summary="Custom", genre="Blank")
    
    for sub in ["backgrounds", "characters", "scenes", "animations", "variables"]:
        os.makedirs(os.path.join(game_dir, "reference", sub), exist_ok=True)
    
    # Create individual character folders
    if meta.characters:
        for char in meta.characters:
            os.makedirs(os.path.join(game_dir, "reference", "characters", char), exist_ok=True)
    
    os.makedirs(os.path.join(game_dir, "saves"), exist_ok=True)
    
    # Scaffold scripts directory
    scripts_dir = os.path.join(game_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    for sub in ["chapters", "quests", "interactions"]:
        os.makedirs(os.path.join(scripts_dir, sub), exist_ok=True)

    save_metadata(req.name, meta)
    
    if req.prompt:
        script_p = prompts.INITIAL_SCRIPT_PROMPT.format(metadata=meta.model_dump_json(indent=2), starting_point=meta.starting_point)
        try:
            initial_script = call_llm(script_p, game_id=req.name)
            initial_script = re.sub(r'^```[\w]*\s*\n?', '', initial_script, flags=re.MULTILINE)
            initial_script = re.sub(r'\n?```$', '', initial_script, flags=re.MULTILINE)
        except: initial_script = f"{meta.starting_point}:\n    talk narrator \"Welcome to {meta.title}.\"\n"
    else: initial_script = f"{meta.starting_point}:\n    talk narrator \"Welcome to {meta.title}!\"\n"

    with open(os.path.join(scripts_dir, "main.narrat"), "w") as f: f.write(initial_script)
    return {"status": "success", "game_id": req.name}

def get_full_character_context(game_id: str, meta: GameMetadata) -> str:
    """Aggregates all character reference data into a context string for AI."""
    context = "CHARACTER PROFILES AND DESCRIPTIONS:\n"
    for char in meta.characters:
        profile = get_reference(game_id, "characters", char, "profile")
        description = get_reference(game_id, "characters", char, "description")
        context += f"--- {char.capitalize()} ---\n"
        context += f"Profile: {profile}\n"
        context += f"Description: {description}\n\n"
    return context

@app.post("/games/{game_id}/sessions/{session_id}/generate")
async def generate_more_story(game_id: str, session_id: str, req: Dict[str, Any]):
    target = req.get("target")
    parser = NarratParser(game_id)
    # Resolve which file to append to. Default to main.narrat if target is new or unknown
    rel_path = req.get("path") or parser.label_to_file.get(target) or "main.narrat"
    state = load_session(game_id, session_id)
    meta = load_metadata(game_id, sync=True)
    
    char_context = get_full_character_context(game_id, meta) if meta else ""
    context = ""
    for entry in state.dialogue_log[-10:]:
        context += f"{entry['character']}: {entry['text']}\n"
    
    prompt = prompts.GENERATE_STORY_PROMPT.format(
        target_label=target,
        context=context,
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata",
        char_context=char_context
    )
    
    try:
        new_script = call_llm(prompt, game_id=game_id)
        new_script = re.sub(r'^```[\w]*\s*\n?', '', new_script, flags=re.MULTILINE)
        new_script = re.sub(r'\n?```$', '', new_script, flags=re.MULTILINE)
        p = get_script_path(game_id, rel_path)
        with open(p, "a") as f: f.write("\n\n" + new_script + "\n")
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/sessions/{session_id}/continue")
async def continue_story(game_id: str, session_id: str, req: Dict[str, Any] = None):
    state = load_session(game_id, session_id)
    parser = NarratParser(game_id)
    rel_path = (req or {}).get("path") or parser.label_to_file.get(state.current_label) or "main.narrat"
    meta = load_metadata(game_id, sync=True)
    
    char_context = get_full_character_context(game_id, meta) if meta else ""
    next_label = f"cont_{state.current_label}_{int(time.time())}"
    context = ""
    for entry in state.dialogue_log[-10:]:
        context += f"{entry['character']}: {entry['text']}\n"
    
    prompt = prompts.CONTINUE_STORY_PROMPT.format(
        current_label=state.current_label,
        next_label=next_label,
        context=context,
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata",
        char_context=char_context
    )
    
    try:
        new_script = call_llm(prompt, game_id=game_id)
        new_script = re.sub(r'^```[\w]*\s*\n?', '', new_script, flags=re.MULTILINE)
        new_script = re.sub(r'\n?```$', '', new_script, flags=re.MULTILINE)
        p = get_script_path(game_id, rel_path)
        with open(p, "a") as f: f.write("\n\n" + new_script + "\n")
        
        # Point the state to the new label
        state.current_label = next_label
        state.line_index = 0
        save_session(game_id, state)
        return {"status": "success", "next_label": next_label}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/sessions/{session_id}/step")
async def step_game(game_id: str, session_id: str, update: GameUpdate):
    logger.info(f"API Step: {game_id}/{session_id} cmd='{update.command}'")
    state = load_session(game_id, session_id)
    # Ensure it's saved immediately if it's new
    save_session(game_id, state)
    
    parser = NarratParser(game_id)
    if update.command == "R":
        state.line_index = 0
        return await process_current_step(game_id, state, parser, "B_REPROCESS")
    if update.command == "B":
        if len(state.history) > 1:
            # Current state is always at the top, we want to discard it and 
            # go back to the state that was saved BEFORE the previous blocking line.
            state.history.pop() # Remove current
            prev_state_dict = state.history.pop()
            state = SessionState(**prev_state_dict)
            save_session(game_id, state)
            return await process_current_step(game_id, state, parser, "B_REPROCESS")
    
    logger.info(f"Dispatching to logic: {state.current_label} @ {state.line_index}")
    return await process_current_step(game_id, state, parser, update.command)

@app.get("/games/{game_id}/scripts/content")
async def get_script_content(game_id: str, path: str):
    p = get_script_path(game_id, path)
    if not os.path.exists(p): raise HTTPException(status_code=404, detail="Script not found")
    with open(p, "r") as f: return {"content": f.read()}

@app.put("/games/{game_id}/scripts/content")
async def update_script_content(game_id: str, req: Dict[str, str]):
    path, content = req.get("path"), req.get("content")
    if not path: raise HTTPException(status_code=400, detail="Missing path")
    p = get_script_path(game_id, path)
    if not os.path.exists(p): raise HTTPException(status_code=404, detail="Script not found")
    with open(p, "w") as f: f.write(content)
    NarratParser(game_id).refresh()
    return {"status": "success"}

@app.delete("/games/{game_id}/scripts/content")
async def delete_script(game_id: str, path: str):
    if path == "main.narrat": raise HTTPException(status_code=400, detail="Cannot delete main.narrat")
    p = get_script_path(game_id, path)
    if not os.path.exists(p): raise HTTPException(status_code=404, detail="Script not found")
    os.remove(p)
    NarratParser(game_id).refresh()
    return {"status": "success"}

@app.get("/games/{game_id}/assets/{category}")
async def list_assets(game_id: str, category: str):
    p = get_game_path(game_id, "reference", category)
    if not os.path.exists(p): return {"assets": []}
    if category == "characters":
        return {"assets": [d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))]}
    return {"assets": [f.replace(".txt", "") for f in os.listdir(p) if f.endswith(".txt")]}

@app.get("/games/{game_id}/assets/{category}/{asset_id}")
async def get_asset(game_id: str, category: str, asset_id: str, type: str = "description"):
    if category == "backgrounds": p = get_game_path(game_id, "reference", "backgrounds", f"{asset_id}.txt")
    elif category == "characters": p = get_game_path(game_id, "reference", "characters", asset_id, f"{asset_id}_{type}.txt")
    elif category == "scenes": p = get_game_path(game_id, "reference", "scenes", f"{asset_id}.txt")
    elif category == "variables": p = get_game_path(game_id, "reference", "variables", f"{asset_id}.txt")
    else: p = get_game_path(game_id, "reference", category, f"{asset_id}.txt")
    if not os.path.exists(p): return {"content": ""}
    with open(p, "r") as f: return {"content": f.read()}

@app.post("/games/{game_id}/assets/generate")
async def generate_asset(game_id: str, req: GenerateRequest):
    target, cat, sub = req.target, req.category, req.sub_type
    meta = load_metadata(game_id, sync=True)
    prompt = prompts.ASSET_DESCRIPTION_PROMPT.format(asset_id=target, asset_type=f"{cat} {sub}", metadata=meta.model_dump_json(indent=2) if meta else "No metadata")
    try:
        content = call_llm(prompt, game_id=game_id)
        ref_p = get_game_path(game_id, "reference", cat, target, f"{target}_{sub}.txt") if cat == "characters" else get_game_path(game_id, "reference", cat, f"{target}.txt")
        os.makedirs(os.path.dirname(ref_p), exist_ok=True)
        with open(ref_p, "w") as f: f.write(content)
        return {"status": "success", "content": content}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/assets/scan")
async def scan_assets(game_id: str):
    """
    Automated asset discovery and scaffolding.
    Scans the script for characters, backgrounds, and variables.
    Creates missing reference files/folders and updates metadata.
    """
    meta = load_metadata(game_id, sync=True)
    if not meta: raise HTTPException(status_code=404, detail="Not found")
    
    from src.server.parser import NarratParser
    parser = NarratParser(game_id)
    detected = parser.detect_assets()
    
    newly_added = {"characters": [], "backgrounds": [], "scenes": [], "variables": []}
    
    # 1. Characters
    for char in detected["characters"]:
        p = get_game_path(game_id, "reference", "characters", char)
        if not os.path.exists(p):
            os.makedirs(p, exist_ok=True)
            # Create default empty profile/desc if they don't exist
            open(os.path.join(p, f"{char}_profile.txt"), "a").close()
            open(os.path.join(p, f"{char}_description.txt"), "a").close()
            newly_added["characters"].append(char)
            if char not in meta.characters: meta.characters.append(char)
            
    # 2. Backgrounds
    for bg in detected["backgrounds"]:
        p = get_game_path(game_id, "reference", "backgrounds", f"{bg}.txt")
        if not os.path.exists(p):
            open(p, "a").close()
            newly_added["backgrounds"].append(bg)
            if bg not in meta.backgrounds: meta.backgrounds.append(bg)

    # 3. Variables
    for var in detected["variables"]:
        p = get_game_path(game_id, "reference", "variables", f"{var}.txt")
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "a").close()
            newly_added["variables"].append(var)
            if var not in meta.variables: meta.variables.append(var)

    # 4. Scenes (Labels)
    for scene in parser.labels.keys():
        if scene not in meta.scenes:
            meta.scenes.append(scene)
            newly_added["scenes"].append(scene)

    save_metadata(game_id, meta)
    return {"status": "success", "added": newly_added}

@app.delete("/games/{game_id}/assets/{category}/{asset_id}")
async def delete_asset(game_id: str, category: str, asset_id: str):
    meta = load_metadata(game_id, sync=True)
    if not meta: raise HTTPException(status_code=404, detail="Not found")
    
    from src.server.parser import NarratParser
    parser = NarratParser(game_id)
    detected = parser.detect_assets()
    
    # Check if in script
    if category == "characters" and asset_id.lower() in detected["characters"]:
        raise HTTPException(status_code=400, detail="Cannot delete character used in script")
    elif category == "backgrounds" and asset_id.lower() in detected["backgrounds"]:
        raise HTTPException(status_code=400, detail="Cannot delete background used in script")
    elif category == "variables" and asset_id.lower() in detected["variables"]:
        raise HTTPException(status_code=400, detail="Cannot delete variable used in script")
    
    # Delete from disk
    if category == "characters":
        p = get_game_path(game_id, "reference", "characters", asset_id)
        if os.path.exists(p):
            import shutil
            shutil.rmtree(p)
    else:
        p = get_game_path(game_id, "reference", category, f"{asset_id}.txt")
        if os.path.exists(p):
            os.remove(p)
            
    # Update Metadata
    if category == "characters":
        meta.characters = [c for c in meta.characters if c.lower() != asset_id.lower()]
    elif category == "backgrounds":
        meta.backgrounds = [b for b in meta.backgrounds if b.lower() != asset_id.lower()]
    elif category == "variables":
        meta.variables = [v for v in meta.variables if v.lower() != asset_id.lower()]
    elif category == "scenes":
        meta.scenes = [s for s in meta.scenes if s != asset_id] # Scenes are labels, usually case-sensitive in metadata but lowercase in list
        
    save_metadata(game_id, meta)
    return {"status": "success"}

@app.post("/games/{game_id}/assets/rename")
async def rename_asset(game_id: str, req: Dict[str, str]):
    cat, old_id, new_id = req.get("category"), req.get("old_id"), req.get("new_id")
    if not all([cat, old_id, new_id]): raise HTTPException(status_code=400, detail="Missing data")
    
    if cat == "characters":
        new_id = new_id.lower().replace(" ", "_")
        
    meta = load_metadata(game_id, sync=True)
    if not meta: raise HTTPException(status_code=404, detail="Not found")

    def apply_smart_rename(text, old, new):
        def replace_keep_case(match):
            word = match.group(0)
            if word.isupper(): return new.upper()
            if word[0].isupper(): return new.capitalize()
            return new.lower()
        return re.sub(rf'\b{old}\b', replace_keep_case, text, flags=re.IGNORECASE)

    # 1. Update Metadata
    meta.title = apply_smart_rename(meta.title, old_id, new_id)
    meta.summary = apply_smart_rename(meta.summary, old_id, new_id)
    if meta.plot_outline:
        meta.plot_outline = apply_smart_rename(meta.plot_outline, old_id, new_id)
    
    if cat == "characters":
        meta.characters = [new_id if c.lower() == old_id.lower() or c == old_id else c for c in meta.characters]
        # Ensure consistent naming if they used a proper name in characters list
        if any(c.lower() == new_id.lower() for c in meta.characters):
             meta.characters = [new_id.capitalize() if c.lower() == new_id.lower() else c for c in meta.characters]
    
    save_metadata(game_id, meta)

    # 2. Rename Files
    old_p = None
    if cat == "characters":
        char_dir = get_game_path(game_id, "reference", "characters")
        if os.path.exists(char_dir):
            for d in os.listdir(char_dir):
                if d.lower() == old_id.lower():
                    old_p = os.path.join(char_dir, d); break
        new_p = get_game_path(game_id, "reference", "characters", new_id)
    else:
        ref_dir = get_game_path(game_id, "reference", cat)
        if os.path.exists(ref_dir):
            for f in os.listdir(ref_dir):
                if f.lower() == f"{old_id.lower()}.txt":
                    old_p = os.path.join(ref_dir, f); break
        new_p = get_game_path(game_id, "reference", cat, f"{new_id}.txt")
    
    if old_p and os.path.exists(old_p):
        os.rename(old_p, new_p)
        if cat == "characters":
            # Also rename files inside the character folder
            for f in os.listdir(new_p):
                if old_id.lower() in f.lower():
                    new_f = f.lower().replace(old_id.lower(), new_id.lower())
                    os.rename(os.path.join(new_p, f), os.path.join(new_p, new_f))

    # 3. Update Scripts
    scripts_dir = get_game_path(game_id, "scripts")
    if os.path.exists(scripts_dir):
        for root, _, files in os.walk(scripts_dir):
            for f in files:
                if f.endswith(".narrat"):
                    sp = os.path.join(root, f)
                    with open(sp, "r") as file: content = file.read()
                    with open(sp, "w") as file: file.write(apply_smart_rename(content, old_id, new_id))

    return {"status": "success"}

@app.get("/games/{game_id}/scripts")
async def list_scripts(game_id: str):
    scripts_dir = get_game_path(game_id, "scripts")
    if not os.path.exists(scripts_dir): return {"scripts": []}
    
    scripts = []
    for root, _, files in os.walk(scripts_dir):
        for f in files:
            if f.endswith(".narrat"):
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, scripts_dir)
                scripts.append({
                    "path": rel_p,
                    "name": f.replace(".narrat", ""),
                    "size": os.path.getsize(full_p)
                })
    return {"scripts": sorted(scripts, key=lambda x: x["path"])}

@app.post("/games/{game_id}/scripts")
async def create_script(game_id: str, req: Dict[str, str]):
    path = req.get("path") # e.g. "chapters/chapter1.narrat"
    if not path: raise HTTPException(status_code=400, detail="Missing path")
    if not path.endswith(".narrat"): path += ".narrat"
    
    full_p = get_game_path(game_id, "scripts", path)
    os.makedirs(os.path.dirname(full_p), exist_ok=True)
    
    if os.path.exists(full_p): raise HTTPException(status_code=400, detail="File already exists")
    
    # Scaffold with a basic label if it's empty
    label_name = os.path.basename(path).replace(".narrat", "")
    content = f"// New script: {path}\n\n{label_name}:\n    \"This is a new script.\"\n"
    with open(full_p, "w") as f: f.write(content)
    return {"status": "success"}

@app.post("/games/{game_id}/sessions/{session_id}/edit")
async def edit_game(game_id: str, session_id: str, update: Dict[str, Any]):
    cat, action, target, content = update.get("category"), update.get("action"), update.get("target"), update.get("content")
    if cat == "reference":
        sub = update.get("sub_category", "background")
        if sub == "character":
            p = get_game_path(game_id, "reference", "characters", target, f"{target}_{update.get('meta', {}).get('type', 'profile')}.txt")
            # Ensure folder exists
            os.makedirs(os.path.dirname(p), exist_ok=True)
            # Initialize both files if they don't exist
            prof_p = get_game_path(game_id, "reference", "characters", target, f"{target}_profile.txt")
            desc_p = get_game_path(game_id, "reference", "characters", target, f"{target}_description.txt")
            if not os.path.exists(prof_p): open(prof_p, "a").close()
            if not os.path.exists(desc_p): open(desc_p, "a").close()
        else:
            p = get_game_path(game_id, "reference", f"{sub}s", f"{target}.txt")
            os.makedirs(os.path.dirname(p), exist_ok=True)
        
        with open(p, "w") as f: f.write(content)
    elif cat == "script":
        rel_path = update.get("meta", {}).get("path")
        if not rel_path:
            parser = NarratParser(game_id)
            state = load_session(game_id, session_id)
            rel_path = parser.label_to_file.get(state.current_label) or "main.narrat"

        p = get_script_path(game_id, rel_path)
        with open(p, "r") as f: lines = f.readlines()
        lines[int(target)] = f"{re.match(r'^\s*', lines[int(target)]).group(0)}{content}\n"
        with open(p, "w") as f: f.writelines(lines)
    elif cat == "metadata":
        meta = load_metadata(game_id, sync=True)
        if meta: setattr(meta, target, content); save_metadata(game_id, meta)
    
    # Sync metadata characters if we just edited/created a character reference
    if cat == "reference" and update.get("sub_category") == "character":
        meta = load_metadata(game_id, sync=True)
        if meta and target not in meta.characters:
            meta.characters.append(target)
            save_metadata(game_id, meta)

    return {"status": "success"}

@app.post("/games/{game_id}/sessions/{session_id}/edit/ai")
async def edit_game_ai(game_id: str, session_id: str, update: Dict[str, Any]):
    target_idx = int(update.get("target"))
    instruction = update.get("content")
    rel_path = update.get("meta", {}).get("path")
    if not rel_path:
        parser = NarratParser(game_id)
        state = load_session(game_id, session_id)
        rel_path = parser.label_to_file.get(state.current_label) or "main.narrat"
    
    p = get_script_path(game_id, rel_path)
    with open(p, "r") as f: lines = f.readlines()
    
    old_line = lines[target_idx].strip()
    meta = load_metadata(game_id, sync=True)
    
    prompt = f"Original line: {old_line}\nInstruction: {instruction}\nContext: {meta.model_dump_json() if meta else ''}\nRewrite the line using valid narrat syntax. Return ONLY the line."
    new_content = call_llm(prompt, game_id=game_id).strip()
    # Clean possible markdown
    new_content = new_content.replace("```narrat", "").replace("```", "").strip()
    
    lines[target_idx] = f"{re.match(r'^\s*', lines[target_idx]).group(0)}{new_content}\n"
    with open(p, "w") as f: f.writelines(lines)
    
    return {"status": "success", "new_content": new_content}

@app.post("/games/{game_id}/refine/options")
async def refine_metadata_options(game_id: str, req: Dict[str, str]):
    field, instruction = req.get("field"), req.get("instruction", "Better")
    current_meta = load_metadata(game_id, sync=True)
    prompt = prompts.METADATA_REFINE_PROMPT.format(field=field, instruction=instruction, metadata=current_meta.model_dump_json(indent=2))
    try:
        raw = call_llm(prompt, game_id=game_id)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match: return {"options": json.loads(match.group(0)).get("options", [])[:3]}
        raise Exception("AI Error")
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/regenerate")
async def regenerate_metadata(game_id: str, req: CreateGameRequest):
    current_meta = load_metadata(game_id, sync=True)
    prompt = prompts.REGENERATE_METADATA_PROMPT.format(user_prompt=req.prompt or "Refine", current_metadata=current_meta.model_dump_json(indent=2))
    try:
        raw = call_llm(prompt, game_id=game_id)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            new_data = json.loads(match.group(0))
            if "prompt_prefix" not in new_data: new_data["prompt_prefix"] = current_meta.prompt_prefix
            new_meta = GameMetadata(**new_data); save_metadata(game_id, new_meta)
            return {"status": "success", "metadata": new_meta}
        raise Exception("AI Error")
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.get("/games/{game_id}/saves")
async def list_saves(game_id: str):
    path = get_game_path(game_id, "saves")
    if not os.path.exists(path): return {"saves": []}
    
    saves = []
    # Only process files changed in the last hour to speed up?
    # No, let's just make it more robust.
    for f in os.listdir(path):
        if f.endswith(".json"):
            sid = f.replace(".json", "")
            try:
                full_p = os.path.join(path, f)
                mtime = os.path.getmtime(full_p)
                
                # Fast check: Read only first few lines if possible or just rely on file
                # For now, we still load but maybe we can optimize load_session
                st = load_session(game_id, sid)
                saves.append({
                    "id": sid, 
                    "label": st.current_label, 
                    "last_text": st.dialogue_log[-1]["text"] if st.dialogue_log else "Start", 
                    "timestamp": mtime
                })
            except Exception as e:
                logger.error(f"Error loading save {sid}: {e}")
                continue
    saves.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"saves": saves}

@app.delete("/games/{game_id}/saves/{session_id}")
async def delete_save(game_id: str, session_id: str):
    path = get_game_path(game_id, "saves", f"{session_id}.json")
    if os.path.exists(path): os.remove(path)
    return {"status": "success"}
