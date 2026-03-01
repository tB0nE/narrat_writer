import os
import json
import re
import shutil
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import requests as sync_requests # For AI API call
import prompts

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("narrat_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("narrat_api")

app = FastAPI(title="Headless Narrat API")

# --- CONFIGURATION ---
GAMES_DIR = os.getenv("GARRAT_GAMES_DIR", "games")

# --- DATA MODELS ---

class GameMetadata(BaseModel):
    title: str
    summary: str
    genre: str
    characters: List[str] = []
    starting_point: str = "main"
    plot_outline: Optional[str] = None
    prompt_prefix: Optional[str] = None

class CreateGameRequest(BaseModel):
    name: str # The folder name/ID
    prompt: Optional[str] = None
    manual_data: Optional[GameMetadata] = None

class SessionState(BaseModel):
    session_id: str
    current_label: str = "main"
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

def call_llm(prompt: str, retries: int = 3, game_id: str = None) -> str:
    """
    Core LLM API wrapper with retry logic, global/local prompt_prefix support, 
    and detailed logging.
    """
    with open("config.json", "r") as f:
        config = json.load(f)
    
    # Prefix Logic
    prefix = ""
    # 1. Global Prefix
    if config.get("global_prompt_prefix"):
        prefix = config.get("global_prompt_prefix")
    
    # 2. Per-Game Prefix (overrides global)
    if game_id:
        meta = load_metadata(game_id)
        if meta and meta.prompt_prefix:
            prefix = meta.prompt_prefix
            
    final_prompt = f"{prefix}\n\n{prompt}" if prefix else prompt

    if config.get("api_key") == "YOUR_API_KEY_HERE":
        logger.warning("API Key not configured. Returning fallback data.")
        return '{"title": "Unconfigured Game", "summary": "Please set your API key in config.json", "genre": "System", "characters": [], "starting_point": "main", "plot_outline": ""}'

    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    payload = {"model": config["model"], "messages": [{"role": "user", "content": final_prompt}]}
    
    for attempt in range(retries):
        try:
            logger.info(f"AI Request (Attempt {attempt + 1}/{retries}): {final_prompt[:100]}...")
            res = sync_requests.post(config["api_url"], json=payload, headers=headers, timeout=90)
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            logger.info(f"AI Response received: {len(content)} chars.")
            return content
        except Exception as e:
            logger.error(f"AI Attempt {attempt + 1} failed: {str(e)}")
            if attempt == retries - 1:
                raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
            import time
            time.sleep(1)
    return ""

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
        self.labels = {}
        current_label = None
        label_content = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped: continue
            
            # Match labels: 'label name:' or just 'name:' at the VERY START of the line
            # We exclude common keywords that might end in a colon
            label_match = re.match(r"^(?:label\s+)?([\w_]+):\s*(?://.*)?$", line.rstrip())
            if label_match:
                lbl_name = label_match.group(1)
                if lbl_name in ["choice", "if", "talk", "set", "jump", "background", "scene", "play", "stop"]:
                    label_match = None

            if label_match:
                if current_label: 
                    self.labels[current_label] = label_content
                current_label = label_match.group(1)
                label_content = []
                continue
            if current_label: label_content.append((i, line.rstrip()))
        if current_label: 
            self.labels[current_label] = label_content
        logger.info(f"Parsed {len(self.labels)} labels from {self.filepath}")

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
    return SessionState(session_id=session_id, current_label=meta.starting_point if meta else "main")

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

# --- CONFIGURATION ENDPOINTS ---

@app.get("/config")
async def get_api_config():
    """Returns the current API and global configuration."""
    with open("config.json", "r") as f:
        return json.load(f)

@app.post("/config")
async def update_api_config(new_config: Dict[str, Any]):
    """Updates and persists the global configuration."""
    with open("config.json", "r") as f:
        config = json.load(f)
    config.update(new_config)
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
    return {"status": "success", "config": config}

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
    
    meta = None
    if req.prompt:
        ai_prompt = prompts.CREATE_GAME_PROMPT.format(user_prompt=req.prompt)
        try:
            raw = call_llm(ai_prompt, game_id=req.name)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                json_str = match.group(0)
                try:
                    meta = GameMetadata(**json.loads(json_str))
                except json.JSONDecodeError as je:
                    logger.error(f"JSON Decode Error at char {je.pos}: {je.msg}")
                    logger.error(f"Raw section that failed: {json_str}")
                    raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {je.msg}")
            else:
                logger.error(f"Failed to find JSON in AI response: {raw}")
                raise HTTPException(status_code=500, detail="AI returned invalid format (no JSON found)")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Unexpected error during AI game creation")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    else: meta = req.manual_data or GameMetadata(title=req.name, summary="Custom", genre="Blank")
    
    # Create structure ONLY if we have meta and no error raised above
    os.makedirs(os.path.join(game_dir, "reference", "backgrounds"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "characters"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "scenes"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "reference", "animations"), exist_ok=True)
    os.makedirs(os.path.join(game_dir, "saves"), exist_ok=True)

    save_metadata(req.name, meta)
    
    # Generate Initial Script
    logger.info(f"Generating initial script for {meta.title}...")
    script_prompt = prompts.INITIAL_SCRIPT_PROMPT.format(
        metadata=meta.model_dump_json(indent=2),
        starting_point=meta.starting_point
    )
    try:
        initial_script = call_llm(script_prompt, game_id=req.name)
        # Clean up any potential markdown formatting if the AI added it
        initial_script = re.sub(r'^```narrat\s*\n?', '', initial_script, flags=re.MULTILINE)
        initial_script = re.sub(r'\n?```$', '', initial_script, flags=re.MULTILINE)
    except:
        logger.warning("Failed to generate AI script, falling back to simple template.")
        initial_script = f"{meta.starting_point}:\n    talk narrator \"Welcome to {meta.title}.\"\n    choice:\n        \"Explore\":\n            jump explore_start\n\nexplore_start:\n    talk narrator \"Exploration.\"\n    jump {meta.starting_point}\n"

    with open(os.path.join(game_dir, "phase1.narrat"), "w") as f:
        f.write(initial_script)
    
    return {"status": "success", "game_id": req.name}

@app.post("/games/{game_id}/sessions/{session_id}/step")
async def step_game(game_id: str, session_id: str, update: GameUpdate):
    state = load_session(game_id, session_id)
    parser = NarratParser(game_id)
    
    # Pre-check if current label exists at all
    if state.current_label not in parser.labels:
        logger.warning(f"Session loaded at missing label '{state.current_label}'.")
        return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' is missing.", variables=state.variables, dialogue_log=state.dialogue_log)

    if update.command == "R":
        parser.parse()
        meta = load_metadata(game_id)
        state.current_label = meta.starting_point if meta else "main"
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
            # If the label itself doesn't exist in the parser at all, it's definitely missing
            if state.current_label not in parser.labels:
                logger.warning(f"Label '{state.current_label}' is missing from script! Triggering AI request flow.")
                return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' is missing.", variables=state.variables, dialogue_log=state.dialogue_log)
            
            # If the label exists but we ran out of lines, it's the end of that script part
            logger.info(f"End of label '{state.current_label}' reached at index {state.line_index}.")
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
            
            # Fetch the most up-to-date background/scene after potential changes in the loop
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
            # Track for UI
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            var_name = f"{char}_emotion"
            if var_name not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(var_name)
            state.variables[var_name] = emo
            continue
        if re.match(r'set\s+([\w_]+)\s+(.*)', stripped):
            m = re.match(r'set\s+([\w_]+)\s+(.*)', stripped)
            var, val = m.group(1), m.group(2).strip()
            state.variables[var] = int(val) if val.isdigit() else val
            # Track for UI
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            if var not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(var)
            if len(state.variables["__updated_vars"]) > 5: state.variables["__updated_vars"].pop(0)
            continue
        if re.match(r'^jump\s+([\w_]+)', stripped) or re.match(r'^->\s+([\w_]+)', stripped):
            target = re.match(r'^(?:jump|->)\s+([\w_]+)', stripped).group(1)
            state.current_label, state.line_index = target, 0
            continue
        if stripped == "choice:":
            logger.info(f"Entering choice block at label '{state.current_label}' index {state.line_index}")
            options, opt_idx, temp_idx = {}, 1, state.line_index
            while True:
                next_data = parser.get_line(state.current_label, temp_idx)
                if not next_data: 
                    logger.info("No more lines found in label for choice.")
                    break
                
                line_content = next_data[1].strip()
                logger.info(f"Checking line {temp_idx}: '{next_data[1]}'")
                if not line_content: 
                    temp_idx += 1
                    continue
                
                # Match standard Narrat option: "Text":
                opt_match = re.match(r'^\s*"(.*)":$', next_data[1])
                
                if opt_match:
                    text = opt_match.group(1)
                    logger.info(f"Found option: {text}")
                    # Scan for a jump in subsequent lines belonging to this option
                    found_jump = False
                    search_idx = temp_idx + 1
                    while True:
                        jump_data = parser.get_line(state.current_label, search_idx)
                        if not jump_data: break
                        
                        jump_content = jump_data[1].strip()
                        if not jump_content: 
                            search_idx += 1
                            continue
                            
                        # If we hit another option, we stop searching for a jump
                        if re.match(r'^\s*"(.*)":$', jump_data[1]): 
                            logger.info(f"Hit next option at {search_idx} while searching for jump.")
                            break
                        
                        # Match 'jump label_name' or '-> label_name'
                        jump_match = re.search(r'(?:jump|->)\s+([\w_]+)', jump_content)
                        if jump_match:
                            target_label = jump_match.group(1)
                            logger.info(f"Found jump to {target_label} for option {text}")
                            options[opt_idx] = {"text": text, "target": target_label}
                            opt_idx += 1
                            found_jump = True
                            break
                        search_idx += 1
                    
                    if found_jump:
                        temp_idx = search_idx + 1 # Continue after the jump we found
                        continue
                
                logger.info(f"Line {temp_idx} did not match an option or was already processed.")
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

@app.post("/games/{game_id}/assets/rename")
async def rename_asset(game_id: str, req: Dict[str, str]):
    """
    Globally renames an asset (character, background, or scene) in metadata, 
    script, and reference files. Case-insensitive matching for the script.
    """
    category = req.get("category") # characters, backgrounds, scenes
    old_id = req.get("old_id")
    new_id = req.get("new_id")
    
    if not all([category, old_id, new_id]):
        raise HTTPException(status_code=400, detail="Missing category, old_id, or new_id")

    meta = load_metadata(game_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Game not found")

    # 1. Update Metadata
    if category == "characters":
        # Find index case-insensitively
        new_char_list = []
        found = False
        for c in meta.characters:
            if c.lower() == old_id.lower():
                new_char_list.append(new_id)
                found = True
            else:
                new_char_list.append(c)
        
        if found:
            meta.characters = new_char_list
            save_metadata(game_id, meta)
            logger.info(f"Updated metadata character list: {old_id} -> {new_id}")

    # 2. Update Script File (phase1.narrat) - Case Insensitive Refactor
    p = get_game_path(game_id, "phase1.narrat")
    if os.path.exists(p):
        with open(p, "r") as f:
            content = f.read()
        
        if category == "characters":
            # Match technical commands: 'talk old_id' or 'set_expression old_id'
            content = re.sub(rf'(\btalk\s+){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
            content = re.sub(rf'(\bset_expression\s+){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
            # Match spoken instances in dialogue: "Hello old_id!" -> "Hello new_id!"
            # We look for the ID when it's NOT followed by a colon (which would be a technical label)
            # and is inside quotes or at word boundaries.
            content = re.sub(rf'(\b){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
        elif category == "backgrounds":
            content = re.sub(rf'(\bbackground\s+){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
            content = re.sub(rf'(\b){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
        elif category == "scenes":
            content = re.sub(rf'(\bscene\s+){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
            content = re.sub(rf'(\b){old_id}(\b)', f'\\1{new_id}\\2', content, flags=re.IGNORECASE)
        
        # Ensure label definitions are also renamed
        content = re.sub(rf'^(\s*){old_id}:', f'\\1{new_id}:', content, flags=re.MULTILINE | re.IGNORECASE)
        
        with open(p, "w") as f:
            f.write(content)
        logger.info(f"Refactored script content: {old_id} -> {new_id}")

    # 3. Rename Reference Assets
    old_ref_dir = get_game_path(game_id, "reference", category)
    if category == "characters":
        old_path = os.path.join(old_ref_dir, old_id)
        new_path = os.path.join(old_ref_dir, new_id)
    else:
        old_path = os.path.join(old_ref_dir, f"{old_id}.txt")
        new_path = os.path.join(old_ref_dir, f"{new_id}.txt")
    
    if os.path.exists(old_path):
        if os.path.exists(new_path):
            if os.path.isdir(new_path): shutil.rmtree(new_path)
            else: os.remove(new_path)
        
        os.rename(old_path, new_path)
        
        # Character-specific internal file renaming
        if category == "characters" and os.path.isdir(new_path):
            for filename in os.listdir(new_path):
                if filename.lower().startswith(f"{old_id.lower()}_"):
                    new_filename = filename.replace(old_id, new_id, 1) # Keep case of suffix
                    # If the above failed due to casing, try a simple lower replace
                    if new_filename == filename:
                         new_filename = re.sub(rf'^{old_id}_', f'{new_id}_', filename, flags=re.IGNORECASE)
                    os.rename(os.path.join(new_path, filename), os.path.join(new_path, new_filename))
        
        logger.info(f"Renamed reference assets for {category}")

    return {"status": "success", "old_id": old_id, "new_id": new_id}

@app.post("/games/{game_id}/sessions/{session_id}/generate")
async def generate_label(game_id: str, session_id: str, req: GenerateRequest):
    """Generates a new Narrat label using AI when a jump target is missing."""
    state = load_session(game_id, session_id)
    meta = load_metadata(game_id)
    
    # Build context from dialogue log
    context_lines = [f"{d['character']}: {d['text']}" for d in state.dialogue_log[-20:]]
    context_str = "\n".join(context_lines)
    
    prompt = prompts.GENERATE_STORY_PROMPT.format(
        context=context_str,
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata",
        target_label=req.target
    )
    
    try:
        logger.info(f"Generating story continuation for label: {req.target}")
        new_content = call_llm(prompt, game_id=game_id)
        
        # Clean up markdown
        new_content = re.sub(r'^```[\w]*\s*\n?', '', new_content, flags=re.MULTILINE)
        new_content = re.sub(r'\n?```$', '', new_content, flags=re.MULTILINE)
        
        # Append to the script file
        p = get_game_path(game_id, "phase1.narrat")
        with open(p, "a") as f:
            # Add a clear comment and the new content
            f.write(f"\n\n// AI Generated Label: {req.target}\n{req.target}:\n{new_content}\n")
            
        logger.info(f"Successfully appended AI content for label {req.target}")
        return {"status": "success"}
    except Exception as e:
        logger.exception("Failed to generate story continuation")
        raise HTTPException(status_code=502, detail=f"Story generation failed: {str(e)}")

@app.post("/games/{game_id}/sessions/{session_id}/continue")
async def continue_story(game_id: str, session_id: str):
    """Generates more content when the current script ends."""
    state = load_session(game_id, session_id)
    meta = load_metadata(game_id)
    
    # Create a unique new label name
    import time
    unique_suffix = hex(int(time.time()))[2:]
    next_label = f"cont_{unique_suffix}"
    
    # Build context
    context_lines = [f"{d['character']}: {d['text']}" for d in state.dialogue_log[-20:]]
    context_str = "\n".join(context_lines)
    
    prompt = prompts.CONTINUE_STORY_PROMPT.format(
        context=context_str,
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata",
        current_label=state.current_label,
        next_label=next_label
    )
    
    try:
        logger.info(f"Continuing story from label: {state.current_label} -> {next_label}")
        new_content = call_llm(prompt, game_id=game_id)
        new_content = re.sub(r'^```[\w]*\s*\n?', '', new_content, flags=re.MULTILINE)
        new_content = re.sub(r'\n?```$', '', new_content, flags=re.MULTILINE)
        
        # Append jump to the old label AND THEN the new label content
        p = get_game_path(game_id, "phase1.narrat")
        with open(p, "a") as f:
            # We add a jump line to the end of the script to connect the current label to the new one
            f.write(f"\n    jump {next_label}\n\n{next_label}:\n{new_content}\n")
            
        # Update the session to point to the new label
        state.current_label = next_label
        state.line_index = 0
        save_session(game_id, state)
        
        return {"status": "success", "new_label": next_label}
    except Exception as e:
        logger.exception("Failed to continue story")
        raise HTTPException(status_code=502, detail=f"Story continuation failed: {str(e)}")

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

@app.post("/games/{game_id}/regenerate")
async def regenerate_metadata(game_id: str, req: CreateGameRequest):
    """Regenerates or refines game metadata using AI based on a new instruction."""
    current_meta = load_metadata(game_id)
    if not current_meta: raise HTTPException(status_code=404, detail="Game not found")
    
    prompt = prompts.REGENERATE_METADATA_PROMPT.format(
        user_prompt=req.prompt or "Refine the existing metadata.",
        current_metadata=current_meta.model_dump_json(indent=2)
    )
    
    try:
        raw = call_llm(prompt, game_id=game_id)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            new_meta_data = json.loads(match.group(0))
            # Merge with existing prefix if it wasn't in AI output
            if "prompt_prefix" not in new_meta_data:
                new_meta_data["prompt_prefix"] = current_meta.prompt_prefix
            
            new_meta = GameMetadata(**new_meta_data)
            save_metadata(game_id, new_meta)
            return {"status": "success", "metadata": new_meta}
        else:
            raise HTTPException(status_code=500, detail="AI returned invalid format")
    except Exception as e:
        logger.exception("Metadata regeneration failed")
        raise HTTPException(status_code=502, detail=f"Regeneration failed: {str(e)}")

@app.get("/games/{game_id}/assets/{category}")
async def list_assets(game_id: str, category: str):
    """Lists existing asset IDs for a given category (backgrounds, characters, etc.)."""
    p = get_game_path(game_id, "reference", category)
    assets = [f.replace(".txt", "") for f in os.listdir(p) if f.endswith(".txt")] if os.path.exists(p) else []
    return {"assets": assets}

@app.post("/games/{game_id}/assets/generate")
async def generate_asset_description(game_id: str, req: Dict[str, str]):
    """Generates a description for a missing asset (character or background) via AI."""
    category = req.get("category") # backgrounds, characters
    target = req.get("target")     # asset id
    sub_type = req.get("sub_type", "description") # profile, description
    
    meta = load_metadata(game_id)
    prompt = prompts.ASSET_DESCRIPTION_PROMPT.format(
        asset_id=target,
        asset_type=f"{category} {sub_type}",
        metadata=meta.model_dump_json(indent=2) if meta else "No metadata"
    )
    
    try:
        logger.info(f"Generating AI description for {category}/{target}...")
        description = call_llm(prompt, game_id=game_id)
        description = re.sub(r'^```[\w]*\s*\n?', '', description, flags=re.MULTILINE)
        description = re.sub(r'\n?```$', '', description, flags=re.MULTILINE)
        
        # Determine path
        ref_p = ""
        if category == "backgrounds": 
            ref_p = get_game_path(game_id, "reference", "backgrounds", f"{target}.txt")
        elif category == "characters":
            os.makedirs(get_game_path(game_id, "reference", "characters", target), exist_ok=True)
            ref_p = get_game_path(game_id, "reference", "characters", target, f"{target}_{sub_type}.txt")
        
        if ref_p:
            os.makedirs(os.path.dirname(ref_p), exist_ok=True)
            with open(ref_p, "w") as f:
                f.write(description)
            logger.info(f"Successfully saved AI description to {ref_p}")
            return {"status": "success", "content": description}
        else:
            raise HTTPException(status_code=400, detail="Invalid asset category")
    except Exception as e:
        logger.exception("Asset generation failed")
        raise HTTPException(status_code=502, detail=f"Generation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8045)
