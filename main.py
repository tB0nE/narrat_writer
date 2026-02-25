import os
import json
import re
import shutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import requests as sync_requests # For AI API call

app = FastAPI(title="Headless Narrat API")

# --- CONFIGURATION ---
GAMES_DIR = os.getenv("GARRAT_GAMES_DIR", "games")

# --- DATA MODELS ---

class GameMetadata(BaseModel):
    title: str
    summary: str
    genre: str
    characters: List[str] = []
    starting_point: str = "start"
    plot_outline: Optional[str] = None

class CreateGameRequest(BaseModel):
    name: str # The folder name/ID
    prompt: Optional[str] = None
    manual_data: Optional[GameMetadata] = None

class SessionState(BaseModel):
    session_id: str
    current_label: str = "start"
    line_index: int = 0
    variables: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []
    dialogue_log: List[Dict[str, Any]] = []
    last_type: str = "talk"

class GameUpdate(BaseModel):
    command: str  # [Number], R, B, E

class GenerateRequest(BaseModel):
    target: str

class DialogueResponse(BaseModel):
    type: str  # talk, choice, background, end
    current_label: Optional[str] = None
    line_index: Optional[int] = None
    character: Optional[str] = None
    text: Optional[str] = None
    options: Optional[Dict[int, Dict[str, str]]] = None
    background: Optional[str] = None
    background_desc: Optional[str] = None
    active_scene: Optional[Dict[str, str]] = None 
    active_animation: Optional[Dict[str, str]] = None
    variables: Optional[Dict[str, Any]] = None
    dialogue_log: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = {}

class EditRequest(BaseModel):
    category: str  # script, reference, metadata
    action: str    # update, insert, delete, clear
    target: str    # global_idx for script, filename for reference
    content: Optional[str] = None
    sub_category: Optional[str] = None # e.g., 'profile', 'description'
    meta: Optional[Dict[str, Any]] = {}

# --- HELPERS ---

def get_game_path(game_id: str, *subpaths):
    return os.path.join(GAMES_DIR, game_id, *subpaths)

def evaluate_expression(expr: str, variables: Dict[str, Any]) -> bool:
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1].strip()
    parts = expr.split()
    if not parts: return False
    op = parts[0]
    def get_val(v):
        v = v.strip()
        if v.startswith("$"):
            var_name = v.replace("$data.", "").replace("$", "")
            return variables.get(var_name, 0)
        if v.isdigit(): return int(v)
        if v.lower() == "true": return True
        if v.lower() == "false": return False
        return v
    try:
        if op == "==": return get_val(parts[1]) == get_val(parts[2])
        if op == "!=": return get_val(parts[1]) != get_val(parts[2])
        if op == ">": return get_val(parts[1]) > get_val(parts[2])
        if op == "<": return get_val(parts[1]) < get_val(parts[2])
        if op == ">=": return get_val(parts[1]) >= get_val(parts[2])
        if op == "<=": return get_val(parts[1]) <= get_val(parts[2])
        if op == "!": return not get_val(parts[1])
    except: return False
    return False

# --- NARRAT PARSER ---

class NarratParser:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.filepath = get_game_path(game_id, "phase1.narrat")
        self.labels = {} 
        self.parse()

    def parse(self):
        if not os.path.exists(self.filepath): return
        with open(self.filepath, "r") as f:
            lines = f.readlines()
        current_label = None
        label_content = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped: continue
            label_match = re.match(r"^label\s+([\w_]+):", stripped)
            if label_match:
                if current_label: self.labels[current_label] = label_content
                current_label = label_match.group(1)
                label_content = []
                continue
            if current_label: label_content.append((i, line.rstrip()))
        if current_label: self.labels[current_label] = label_content

    def get_line(self, label: str, index: int):
        if label not in self.labels: return None
        if index >= len(self.labels[label]): return None
        return self.labels[label][index]

# --- SESSION MANAGEMENT ---

def load_session(game_id: str, session_id: str) -> SessionState:
    path = get_game_path(game_id, "saves", f"{session_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            return SessionState(**data)
    meta = load_metadata(game_id)
    return SessionState(session_id=session_id, current_label=meta.starting_point if meta else "start")

def save_session(game_id: str, state: SessionState):
    path = get_game_path(game_id, "saves")
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, f"{state.session_id}.json"), "w") as f:
        f.write(state.model_dump_json())

def load_metadata(game_id: str) -> Optional[GameMetadata]:
    path = get_game_path(game_id, "metadata.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return GameMetadata(**json.load(f))
    return None

def save_metadata(game_id: str, meta: GameMetadata):
    path = get_game_path(game_id, "metadata.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(meta.model_dump_json())

def get_reference(game_id: str, category: str, name: str, sub_type: str = None) -> str:
    path = ""
    if category == "characters":
        if sub_type: path = get_game_path(game_id, "reference", "characters", name, f"{name}_{sub_type}.txt")
        else: path = get_game_path(game_id, "reference", "characters", name, f"{name}_description.txt")
    elif category == "backgrounds": path = get_game_path(game_id, "reference", "backgrounds", f"{name}.txt")
    elif category == "scenes": path = get_game_path(game_id, "reference", "scenes", f"{name}.txt")
    elif category == "animations": path = get_game_path(game_id, "reference", "animations", f"{name}.txt")
    if os.path.exists(path):
        with open(path, "r") as f: return f.read().strip()
    return f"[{name} {sub_type or ''} placeholder]"

# --- API ENDPOINTS ---

@app.get("/games")
async def list_games():
    if not os.path.exists(GAMES_DIR): return {"games": []}
    games = []
    for d in os.listdir(GAMES_DIR):
        if os.path.isdir(os.path.join(GAMES_DIR, d)):
            meta = load_metadata(d)
            if meta: games.append({"id": d, "title": meta.title, "summary": meta.summary})
    return {"games": games}

@app.get("/games/{game_id}/metadata")
async def get_game_metadata(game_id: str):
    meta = load_metadata(game_id)
    if not meta: raise HTTPException(status_code=404, detail="Game not found")
    return meta

@app.post("/games/create")
async def create_game(req: CreateGameRequest):
    game_dir = get_game_path(req.name)
    if os.path.exists(game_dir): raise HTTPException(status_code=400, detail="Game already exists")
    os.makedirs(os.path.join(game_dir, "reference", "backgrounds"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "characters"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "scenes"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "animations"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "saves"), exist_ok=True)
    meta = None
    if req.prompt:
        with open("config.json", "r") as f: config = json.load(f)
        if config["api_key"] == "YOUR_API_KEY_HERE":
            meta = GameMetadata(title=req.name, summary="Fallback", genre="General")
        else:
            ai_prompt = f"Create a visual novel concept: {req.prompt}. Return ONLY JSON: {{title, summary, genre, characters, starting_point, plot_outline}}"
            headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
            payload = {"model": config["model"], "messages": [{"role": "user", "content": ai_prompt}]}
            try:
                res = sync_requests.post(config["api_url"], json=payload, headers=headers)
                raw = res.json()["choices"][0]["message"]["content"]
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match: meta = GameMetadata(**json.loads(match.group(0)))
            except: meta = GameMetadata(title=req.name, summary="AI Error", genre="Unknown")
    else: meta = req.manual_data or GameMetadata(title=req.name, summary="Custom", genre="Blank")
    save_metadata(req.name, meta)
    with open(os.path.join(game_dir, "phase1.narrat"), "w") as f:
        f.write(f"label {meta.starting_point}:\n    talk narrator \"Welcome to {meta.title}.\"\n    choice:\n        label: \"Explore\" -> explore_start\n\nlabel explore_start:\n    talk narrator \"Exploration.\"\n    -> {meta.starting_point}\n")
    return {"status": "success", "game_id": req.name}

@app.post("/games/{game_id}/sessions/{session_id}/step")
async def step_game(game_id: str, session_id: str, update: GameUpdate):
    state = load_session(game_id, session_id)
    parser = NarratParser(game_id)
    
    if update.command == "R":
        parser.parse()
        state.line_index, state.dialogue_log, state.history = 0, [], []
        save_session(game_id, state)
        return await process_current_step(game_id, state, parser)
    
    if update.command == "B":
        if len(state.history) >= 2:
            state.history.pop() # Remove current
            prev_state_data = state.history.pop() 
            state = SessionState(**prev_state_data)
            save_session(game_id, state)
        return await process_current_step(game_id, state, parser, "B_REPROCESS")

    if update.command == "REFRESH":
        parser.parse()
        if state.last_type == "talk":
            state.line_index = max(0, state.line_index - 1)
            if state.dialogue_log: state.dialogue_log.pop()
        return await process_current_step(game_id, state, parser)

    return await process_current_step(game_id, state, parser, update.command)

async def process_current_step(game_id: str, state: SessionState, parser: NarratParser, command: str = None):
    current_bg = state.variables.get("__current_bg", "None")
    current_scene, current_anim = state.variables.get("__current_scene"), state.variables.get("__current_anim")
    
    # If we are coming from a 'Back' command, we don't want to advance yet, 
    # we want to re-process the line the restored state is pointing to.
    skip_advance = (command == "B_REPROCESS")

    while True:
        line_data = parser.get_line(state.current_label, state.line_index)
        if line_data is None:
            return DialogueResponse(type="end", text="End.", current_label=state.current_label, line_index=state.line_index, variables=state.variables, dialogue_log=state.dialogue_log)
        
        global_idx, line_text = line_data
        stripped = line_text.strip()
        
        if not skip_advance:
            state.line_index += 1
        skip_advance = False # Reset for subsequent loops
        
        talk_match = re.match(r'talk\s+([\w_]+)\s+"(.*)"', stripped)
        if talk_match:
            char, text = talk_match.group(1), talk_match.group(2)
            state.dialogue_log.append({"character": char, "text": text})
            if len(state.dialogue_log) > 20: state.dialogue_log.pop(0)
            state.last_type = "talk"
            # Save to history BEFORE returning
            state.history.append(json.loads(state.model_dump_json()))
            save_session(game_id, state)
            meta = {"profile": get_reference(game_id, "characters", char, "profile"), "description": get_reference(game_id, "characters", char, "description"), "placeholder": get_reference(game_id, "characters", char, "idle"), "emotion": state.variables.get(f"__emo_{char}", "Neutral")}
            return DialogueResponse(type="talk", character=char, text=text, meta=meta, current_label=state.current_label, line_index=state.line_index, background=current_bg, background_desc=get_reference(game_id, "backgrounds", current_bg) if current_bg != "None" else "", variables=state.variables, dialogue_log=state.dialogue_log)

        if re.match(r'background\s+([\w_]+)', stripped):
            state.variables["__current_bg"] = re.match(r'background\s+([\w_]+)', stripped).group(1)
            continue
        if re.match(r'scene\s+([\w_]+)', stripped):
            state.variables["__current_scene"] = re.match(r'scene\s+([\w_]+)', stripped).group(1)
            continue
        if re.match(r'set_expression\s+([\w_]+)\s+([\w_]+)', stripped):
            m = re.match(r'set_expression\s+([\w_]+)\s+([\w_]+)', stripped)
            state.variables[f"__emo_{m.group(1)}"] = m.group(2)
            continue
        if re.match(r'set\s+([\w_]+)\s+(.*)', stripped):
            m = re.match(r'set\s+([\w_]+)\s+(.*)', stripped)
            var, val = m.group(1), m.group(2).strip()
            state.variables[var] = int(val) if val.isdigit() else val
            continue
        if re.match(r'^->\s+([\w_]+)', stripped):
            state.current_label, state.line_index = re.match(r'^->\s+([\w_]+)', stripped).group(1), 0
            continue
        if stripped == "choice:":
            options, opt_idx, temp_idx = {}, 1, state.line_index
            while True:
                next_data = parser.get_line(state.current_label, temp_idx)
                if not next_data: break
                opt_match = re.search(r'label:\s+"(.*)"\s+->\s+([\w_]+)', next_data[1])
                if opt_match:
                    options[opt_idx] = {"text": opt_match.group(1), "target": opt_match.group(2)}
                    opt_idx, temp_idx = opt_idx + 1, temp_idx + 1
                else: break
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

@app.post("/games/{game_id}/sessions/{session_id}/generate")
async def generate_label(game_id: str, session_id: str, req: GenerateRequest):
    # (Existing AI generation logic)
    return {"status": "success"}

@app.post("/games/{game_id}/sessions/{session_id}/edit")
async def edit_game(game_id: str, session_id: str, req: EditRequest):
    p = get_game_path(game_id, "phase1.narrat")
    if req.category == "script":
        with open(p, "r") as f: lines = f.readlines()
        idx = int(req.target)
        if req.action == "update": lines[idx] = f"{re.match(r'^\s*', lines[idx]).group(0)}{req.content}\n"
        elif req.action == "insert": lines.insert(idx + 1, f"{re.match(r'^\s*', lines[idx]).group(0)}{req.content}\n")
        with open(p, "w") as f: f.writelines(lines)
    elif req.category == "reference":
        ref_p = ""
        if req.sub_category == "background": 
            ref_p = get_game_path(game_id, "reference", "backgrounds", f"{req.target}.txt")
        elif req.sub_category == "character":
            os.makedirs(get_game_path(game_id, "reference", "characters", req.target), exist_ok=True)
            suffix = req.meta.get("type", "description")
            ref_p = get_game_path(game_id, "reference", "characters", req.target, f"{req.target}_{suffix}.txt")
        
        if ref_p:
            os.makedirs(os.path.dirname(ref_p), exist_ok=True)
            with open(ref_p, "w") as f: f.write(req.content)
    elif req.category == "metadata":
        meta = load_metadata(game_id)
        if meta: setattr(meta, req.target, req.content); save_metadata(game_id, meta)
    return {"status": "success"}

@app.get("/games/{game_id}/assets/{category}")
async def list_assets(game_id: str, category: str):
    p = get_game_path(game_id, "reference", category)
    assets = [f.replace(".txt", "") for f in os.listdir(p) if f.endswith(".txt")] if os.path.exists(p) else []
    return {"assets": assets}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8045)
