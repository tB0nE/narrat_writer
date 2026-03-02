import os
import json
import re
import shutil
import logging
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional, Any

import prompts
from src.server.models import (
    GameMetadata, SessionState, GameUpdate, 
    CreateGameRequest, GenerateRequest, DialogueResponse
)
from src.server.utils import (
    get_game_path, load_metadata, save_metadata, 
    load_session, save_session, get_reference
)
from src.server.parser import NarratParser, evaluate_expression
from src.server.ai import call_llm

logger = logging.getLogger("narrat_api")
NARRAT_MODE = os.getenv("NARRAT_MODE", "developer")

app = FastAPI(title="Headless Narrat API", version="0.2.0")

# --- CORE GAMEPLAY LOGIC ---

async def process_current_step(game_id: str, state: SessionState, parser: NarratParser, command: str = None):
    """The main execution loop for the Narrat script parser."""
    skip_advance = (command == "B_REPROCESS")
    current_bg = state.variables.get("__current_bg", "None")
    
    while True:
        line_data = parser.get_line(state.current_label, state.line_index)
        if line_data is None:
            if state.current_label not in parser.labels:
                logger.warning(f"Label '{state.current_label}' is missing from script! Triggering AI request flow.")
                return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' is missing.", variables=state.variables, dialogue_log=state.dialogue_log)
            
            logger.info(f"End of label '{state.current_label}' reached at index {state.line_index}.")
            return DialogueResponse(type="end", text="End.", current_label=state.current_label, line_index=state.line_index, variables=state.variables, dialogue_log=state.dialogue_log)
        
        global_idx, line_text = line_data
        stripped = line_text.strip()
        
        if not skip_advance:
            state.line_index += 1
        skip_advance = False 
        
        # Try to match 'talk char "text"' or the shortcut 'char "text"'
        talk_match = re.match(r'talk\s+([\w_]+)\s+"(.*)"', stripped)
        if not talk_match:
            talk_match = re.match(r'^([\w_]+)\s+"(.*)"$', stripped)
            if talk_match and talk_match.group(1) in ["background", "scene", "jump", "set", "set_expression"]:
                talk_match = None

        if talk_match:
            char, text = talk_match.group(1), talk_match.group(2)
            state.dialogue_log.append({"character": char, "text": text})
            if len(state.dialogue_log) > 20: state.dialogue_log.pop(0)
            state.last_type = "talk"
            state.history.append(json.loads(state.model_dump_json()))
            save_session(game_id, state)
            
            latest_bg = state.variables.get("__current_bg", "None")
            meta = {"profile": get_reference(game_id, "characters", char, "profile"), "description": get_reference(game_id, "characters", char, "description"), "placeholder": get_reference(game_id, "characters", char, "idle"), "emotion": state.variables.get(f"__emo_{char}", "Neutral")}
            return DialogueResponse(type="talk", character=char, text=text, meta=meta, current_label=state.current_label, line_index=state.line_index, background=latest_bg, background_desc=get_reference(game_id, "backgrounds", latest_bg) if latest_bg != "None" else "", variables=state.variables, dialogue_log=state.dialogue_log)

        if re.match(r'background\s+([\w_]+)', stripped):
            state.variables["__current_bg"] = re.match(r'background\s+([\w_]+)', stripped).group(1)
            continue
        if re.match(r'scene\s+([\w_]+)', stripped):
            state.variables["__current_scene"] = re.match(r'scene\s+([\w_]+)', stripped).group(1)
            continue
        if re.match(r'set_expression\s+([\w_]+)\s+([\w_]+)', stripped):
            m = re.match(r'set_expression\s+([\w_]+)\s+([\w_]+)', stripped)
            char, emo = m.group(1), m.group(2)
            state.variables[f"__emo_{char}"] = emo
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            var_name = f"{char}_emotion"
            if var_name not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(var_name)
            state.variables[var_name] = emo
            continue
        if re.match(r'set\s+([\w_]+)\s+(.*)', stripped):
            m = re.match(r'set\s+([\w_]+)\s+(.*)', stripped)
            var, val = m.group(1), m.group(2).strip()
            state.variables[var] = int(val) if val.isdigit() else val
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            if var not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(var)
            if len(state.variables["__updated_vars"]) > 5: state.variables["__updated_vars"].pop(0)
            continue
        if re.match(r'jump\s+([\w_]+)', stripped) or re.match(r'->\s+([\w_]+)', stripped):
            target = re.match(r'^(?:jump|->)\s+([\w_]+)', stripped).group(1)
            state.current_label, state.line_index = target, 0
            continue
        if stripped == "choice:":
            options, opt_idx, temp_idx = {}, 1, state.line_index
            while True:
                next_data = parser.get_line(state.current_label, temp_idx)
                if not next_data: break
                line_content = next_data[1].strip()
                if not line_content: 
                    temp_idx += 1
                    continue
                opt_match = re.match(r'^\s*"(.*)":$', next_data[1])
                if opt_match:
                    text = opt_match.group(1)
                    found_jump = False
                    search_idx = temp_idx + 1
                    while True:
                        jump_data = parser.get_line(state.current_label, search_idx)
                        if not jump_data: break
                        jump_content = jump_data[1].strip()
                        if not jump_content: 
                            search_idx += 1
                            continue
                        if re.match(r'^\s*"(.*)":$', jump_data[1]): break
                        jump_match = re.search(r'(?:jump|->)\s+([\w_]+)', jump_content)
                        if jump_match:
                            options[opt_idx] = {"text": text, "target": jump_match.group(1)}
                            opt_idx += 1
                            found_jump = True
                            break
                        search_idx += 1
                    if found_jump:
                        temp_idx = search_idx + 1
                        continue
                break
            
            if command and command.strip().isdigit():
                idx = int(command.strip())
                if idx in options:
                    state.current_label, state.line_index = options[idx]["target"], 0
                    return await process_current_step(game_id, state, parser, None)
            state.line_index -= 1
            state.last_type = "choice"
            state.history.append(json.loads(state.model_dump_json()))
            save_session(game_id, state)
            return DialogueResponse(type="choice", options=options, current_label=state.current_label, line_index=state.line_index, background=current_bg, variables=state.variables, dialogue_log=state.dialogue_log)
        if re.match(r'if\s+(.*):', stripped):
            if not evaluate_expression(re.match(r'if\s+(.*):', stripped).group(1).strip(), state.variables): state.line_index += 1
            continue
    return DialogueResponse(type="end", text="End.")

# --- API ENDPOINTS ---

@app.get("/config")
async def get_api_config():
    from src.server.ai import API_URL, API_MODEL, API_KEY
    return {
        "api_url": API_URL,
        "model": API_MODEL,
        "narrat_mode": NARRAT_MODE,
        "global_prompt_prefix": os.getenv("GLOBAL_PROMPT_PREFIX", "")
    }

@app.post("/config")
async def update_api_config(new_config: Dict[str, Any]):
    if "global_prompt_prefix" in new_config:
        os.environ["GLOBAL_PROMPT_PREFIX"] = new_config["global_prompt_prefix"]
    return {"status": "success", "config": await get_api_config()}

@app.get("/games")
async def list_games():
    """Lists all games currently available in the games directory."""
    games_dir = os.getenv("GARRAT_GAMES_DIR", "games")
    if not os.path.exists(games_dir): return {"games": []}
    games = []
    for d in os.listdir(games_dir):
        if os.path.isdir(os.path.join(games_dir, d)):
            meta = load_metadata(d)
            if meta: games.append({"id": d, "title": meta.title, "summary": meta.summary})
    return {"games": games}

@app.get("/games/{game_id}/metadata")
async def get_game_metadata(game_id: str):
    meta = load_metadata(game_id)
    if meta: return meta
    raise HTTPException(status_code=404, detail="Game not found")

@app.post("/games/create")
async def create_game(req: CreateGameRequest):
    game_dir = get_game_path(req.name)
    if os.path.exists(game_dir): raise HTTPException(status_code=400, detail="Game already exists")
    
    meta = None
    if req.prompt:
        ai_prompt = prompts.CREATE_GAME_PROMPT.format(user_prompt=req.prompt)
        try:
            raw = call_llm(ai_prompt, game_id=req.name)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                json_str = match.group(0)
                meta = GameMetadata(**json.loads(json_str))
            else:
                raise HTTPException(status_code=500, detail="AI returned invalid format")
        except HTTPException: raise
        except Exception as e:
            logger.exception("Unexpected error during AI game creation")
            raise HTTPException(status_code=500, detail=str(e))
    else: meta = req.manual_data or GameMetadata(title=req.name, summary="Custom", genre="Blank")
    
    os.makedirs(os.path.join(game_dir, "reference", "backgrounds"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "characters"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "scenes"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "scenes"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "animations"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "saves"), exist_ok=True)

    save_metadata(req.name, meta)
    
    script_prompt = prompts.INITIAL_SCRIPT_PROMPT.format(metadata=meta.model_dump_json(indent=2), starting_point=meta.starting_point)
    try:
        initial_script = call_llm(script_prompt, game_id=req.name)
        initial_script = re.sub(r'^```[\w]*\s*\n?', '', initial_script, flags=re.MULTILINE)
        initial_script = re.sub(r'\n?```$', '', initial_script, flags=re.MULTILINE)
    except:
        initial_script = f"{meta.starting_point}:\n    talk narrator \"Welcome to {meta.title}.\"\n    choice:\n        \"Explore\":\n            jump explore_start\n\nexplore_start:\n    talk narrator \"Exploration.\"\n    jump {meta.starting_point}\n"

    with open(os.path.join(game_dir, "phase1.narrat"), "w") as f: f.write(initial_script)
    return {"status": "success", "game_id": req.name}

@app.post("/games/{game_id}/sessions/{session_id}/step")
async def step_game(game_id: str, session_id: str, update: GameUpdate):
    state = load_session(game_id, session_id)
    parser = NarratParser(game_id)
    if state.current_label not in parser.labels:
        return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' is missing.", variables=state.variables, dialogue_log=state.dialogue_log)

    if update.command == "R":
        meta = load_metadata(game_id)
        state.current_label = meta.starting_point if meta else "main"
        state.line_index, state.dialogue_log, state.history = 0, [], []
        save_session(game_id, state)
        return await process_current_step(game_id, state, parser)
    
    if update.command == "B":
        if len(state.history) >= 2:
            state.history.pop()
            state = SessionState(**state.history.pop())
            save_session(game_id, state)
        return await process_current_step(game_id, state, parser, "B_REPROCESS")
    
    if update.command == "REFRESH":
        if state.last_type == "talk":
            state.line_index = max(0, state.line_index - 1)
            if state.dialogue_log: state.dialogue_log.pop()
        return await process_current_step(game_id, state, parser)

    return await process_current_step(game_id, state, parser, update.command)

@app.post("/games/{game_id}/assets/rename")
async def rename_asset(game_id: str, req: Dict[str, str]):
    category = req.get("category")
    old_id, new_id = req.get("old_id"), req.get("new_id")
    if not all([category, old_id, new_id]): raise HTTPException(status_code=400, detail="Missing data")
    meta = load_metadata(game_id)
    if not meta: raise HTTPException(status_code=404, detail="Not found")

    def apply_smart_rename(text, old, new):
        if not text: return text
        def preserve_case(match):
            m = match.group(0)
            if m.isupper(): return new.upper()
            if m.istitle(): return new.capitalize()
            return new.lower()
        return re.sub(rf'\b{re.escape(old)}\b', preserve_case, text, flags=re.IGNORECASE)

    meta_changed = False
    if category == "characters":
        new_char_list = []
        for c in meta.characters:
            if c.lower() == old_id.lower():
                replacement = new_id.capitalize() if c[0].isupper() else new_id.lower()
                new_char_list.append(replacement); meta_changed = True
            else: new_char_list.append(c)
        meta.characters = new_char_list

    for field in ["title", "summary", "plot_outline"]:
        val = getattr(meta, field)
        if val:
            new_val = apply_smart_rename(val, old_id, new_id)
            if new_val != val: setattr(meta, field, new_val); meta_changed = True

    if meta_changed: save_metadata(game_id, meta)

    p = get_game_path(game_id, "phase1.narrat")
    if os.path.exists(p):
        with open(p, "r") as f: content = f.read()
        new_content = apply_smart_rename(content, old_id, new_id)
        if new_content != content:
            with open(p, "w") as f: f.write(new_content)

    return {"status": "success"}

@app.post("/games/{game_id}/sessions/{session_id}/generate")
async def generate_label(game_id: str, session_id: str, req: GenerateRequest):
    """Generates a new Narrat label using AI when a jump target is missing."""
    state, meta = load_session(game_id, session_id), load_metadata(game_id)
    prompt = prompts.GENERATE_STORY_PROMPT.format(
        context="\n".join([f"{d['character']}: {d['text']}" for d in state.dialogue_log[-20:]]), 
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata", 
        target_label=req.target
    )
    try:
        new_content = call_llm(prompt, game_id=game_id)
        new_content = re.sub(r'^```[\w]*\s*\n?', '', new_content, flags=re.MULTILINE)
        new_content = re.sub(r'\n?```$', '', new_content, flags=re.MULTILINE)
        with open(get_game_path(game_id, "phase1.narrat"), "a") as f:
            f.write(f"\n\n// AI Generated Label: {req.target}\n{req.target}:\n{new_content}\n")
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/sessions/{session_id}/continue")
async def continue_story(game_id: str, session_id: str):
    """Generates more content when the current script ends."""
    state, meta = load_session(game_id, session_id), load_metadata(game_id)
    import time
    next_label = f"cont_{hex(int(time.time()))[2:]}"
    prompt = prompts.CONTINUE_STORY_PROMPT.format(
        context="\n".join([f"{d['character']}: {d['text']}" for d in state.dialogue_log[-20:]]), 
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata", 
        current_label=state.current_label, 
        next_label=next_label
    )
    try:
        new_content = call_llm(prompt, game_id=game_id)
        new_content = re.sub(r'^```[\w]*\s*\n?', '', new_content, flags=re.MULTILINE)
        new_content = re.sub(r'\n?```$', '', new_content, flags=re.MULTILINE)
        with open(get_game_path(game_id, "phase1.narrat"), "a") as f:
            f.write(f"\n    jump {next_label}\n\n{next_label}:\n{new_content}\n")
        state.current_label, state.line_index = next_label, 0
        save_session(game_id, state)
        return {"status": "success", "new_label": next_label}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/sessions/{session_id}/edit")
async def edit_script(game_id: str, session_id: str, req: Dict[str, Any]):
    cat, target, content = req.get("category"), req.get("target"), req.get("content")
    if cat == "script":
        p = get_game_path(game_id, "phase1.narrat")
        with open(p, "r") as f: lines = f.readlines()
        idx = int(target)
        lines[idx] = f"{re.match(r'^\s*', lines[idx]).group(0)}{content}\n"
        with open(p, "w") as f: f.writelines(lines)
    elif cat == "reference":
        sub, t = req.get("sub_category"), req.get("target")
        if sub == "background": ref_p = get_game_path(game_id, "reference", "backgrounds", f"{t}.txt")
        else: ref_p = get_game_path(game_id, "reference", "characters", t, f"{t}_{req.get('meta', {}).get('type', 'description')}.txt")
        
        logger.info(f"Writing reference asset: {ref_p}")
        os.makedirs(os.path.dirname(ref_p), exist_ok=True)
        with open(ref_p, "w") as f: f.write(content)
    elif cat == "metadata":
        meta = load_metadata(game_id)
        if meta: setattr(meta, target, content); save_metadata(game_id, meta)
    return {"status": "success"}

@app.post("/games/{game_id}/sessions/{session_id}/edit/ai")
async def ai_edit_script(game_id: str, session_id: str, req: Dict[str, str]):
    """Surgically rewrites a script line using AI based on user instructions."""
    line_idx, instruction = int(req.get("target")), req.get("content")
    p = get_game_path(game_id, "phase1.narrat")
    with open(p, "r") as f: lines = f.readlines()
    old_line, meta = lines[line_idx].strip(), load_metadata(game_id)
    prompt = prompts.SCRIPT_ASSISTANT_PROMPT.format(
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata", 
        old_line=old_line, 
        instruction=instruction
    )
    try:
        new_content = call_llm(prompt, game_id=game_id)
        new_content = re.sub(r'^```[\w]*\s*\n?', '', new_content, flags=re.MULTILINE)
        new_content = re.sub(r'\n?```$', '', new_content, flags=re.MULTILINE).strip()
        lines[line_idx] = f"{re.match(r'^\s*', lines[line_idx]).group(0)}{new_content}\n"
        with open(p, "w") as f: f.writelines(lines)
        return {"status": "success", "new_content": new_content}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.post("/games/{game_id}/regenerate")
async def regenerate_metadata(game_id: str, req: CreateGameRequest):
    """Regenerates or refines game metadata using AI based on a new instruction."""
    current_meta = load_metadata(game_id)
    if not current_meta: raise HTTPException(status_code=404, detail="Not found")
    prompt = prompts.REGENERATE_METADATA_PROMPT.format(
        user_prompt=req.prompt or "Refine the existing metadata.", 
        current_metadata=current_meta.model_dump_json(indent=2)
    )
    try:
        raw = call_llm(prompt, game_id=game_id)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            new_meta_data = json.loads(match.group(0))
            if "prompt_prefix" not in new_meta_data: new_meta_data["prompt_prefix"] = current_meta.prompt_prefix
            new_meta = GameMetadata(**new_meta_data)
            save_metadata(game_id, new_meta)
            return {"status": "success", "metadata": new_meta}
        raise HTTPException(status_code=500, detail="AI error")
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))

@app.get("/games/{game_id}/saves")
async def list_saves(game_id: str):
    path = get_game_path(game_id, "saves")
    if not os.path.exists(path): return {"saves": []}
    saves = []
    for f in os.listdir(path):
        if f.endswith(".json"):
            sid = f.replace(".json", "")
            try:
                state = load_session(game_id, sid)
                saves.append({"id": sid, "label": state.current_label, "last_text": state.dialogue_log[-1]["text"] if state.dialogue_log else "Game Start", "timestamp": os.path.getmtime(os.path.join(path, f))})
            except: continue
    saves.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"saves": saves}

@app.delete("/games/{game_id}/saves/{session_id}")
async def delete_save(game_id: str, session_id: str):
    path = get_game_path(game_id, "saves", f"{session_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/games/{game_id}/assets/{category}")
async def list_assets(game_id: str, category: str):
    p = get_game_path(game_id, "reference", category)
    assets = [f.replace(".txt", "") for f in os.listdir(p) if f.endswith(".txt")] if os.path.exists(p) else []
    return {"assets": assets}

@app.post("/games/{game_id}/assets/generate")
async def generate_asset_description(game_id: str, req: Dict[str, str]):
    cat, target, sub = req.get("category"), req.get("target"), req.get("sub_type", "description")
    meta = load_metadata(game_id)
    prompt = prompts.ASSET_DESCRIPTION_PROMPT.format(asset_id=target, asset_type=f"{cat} {sub}", metadata=meta.model_dump_json(indent=2) if meta else "No metadata")
    try:
        desc = call_llm(prompt, game_id=game_id)
        desc = re.sub(r'^```[\w]*\s*\n?', '', desc, flags=re.MULTILINE)
        desc = re.sub(r'\n?```$', '', desc, flags=re.MULTILINE)
        if cat == "backgrounds": ref_p = get_game_path(game_id, "reference", "backgrounds", f"{target}.txt")
        else: ref_p = get_game_path(game_id, "reference", "characters", target, f"{target}_{sub}.txt")
        os.makedirs(os.path.dirname(ref_p), exist_ok=True)
        with open(ref_p, "w") as f: f.write(desc)
        return {"status": "success", "content": desc}
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))
