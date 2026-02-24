import os
import json
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any

app = FastAPI(title="Headless Narrat API")

# --- HELPERS ---

def evaluate_expression(expr: str, variables: Dict[str, Any]) -> bool:
    """
    Evaluates Narrat-style expressions: (operator operand1 operand2)
    Examples: (== $data.var 1), (> $security 10), (! $flag)
    """
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1].strip()
    
    parts = expr.split()
    if not parts:
        return False
    
    op = parts[0]
    
    def get_val(v):
        v = v.strip()
        # Handle $data. prefix or just $ prefix
        if v.startswith("$"):
            var_name = v.replace("$data.", "").replace("$", "")
            return variables.get(var_name, 0)
        # Handle literals
        if v.isdigit(): return int(v)
        if v.lower() == "true": return True
        if v.lower() == "false": return False
        return v

    try:
        if op == "==":
            return get_val(parts[1]) == get_val(parts[2])
        if op == "!=":
            return get_val(parts[1]) != get_val(parts[2])
        if op == ">":
            return get_val(parts[1]) > get_val(parts[2])
        if op == "<":
            return get_val(parts[1]) < get_val(parts[2])
        if op == ">=":
            return get_val(parts[1]) >= get_val(parts[2])
        if op == "<=":
            return get_val(parts[1]) <= get_val(parts[2])
        if op == "!":
            return not get_val(parts[1])
    except Exception:
        return False
    
    return False

# --- DATA MODELS ---

class SessionState(BaseModel):
    session_id: str
    current_label: str = "start"
    line_index: int = 0
    variables: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []
    dialogue_log: List[Dict[str, Any]] = []

class GameUpdate(BaseModel):
    command: str  # [Number], R, B, E

class GenerateRequest(BaseModel):
    target: str

class DialogueResponse(BaseModel):
    type: str  # talk, choice, background, end
    current_label: Optional[str] = None
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

# --- NARRAT PARSER ---

class NarratParser:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.labels = {}
        self.parse()

    def parse(self):
        if not os.path.exists(self.filepath):
            return
        
        with open(self.filepath, "r") as f:
            lines = f.readlines()

        current_label = None
        label_content = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            
            # Label detection: "label name:"
            label_match = re.match(r"^label\s+([\w_]+):", stripped)
            if label_match:
                if current_label:
                    self.labels[current_label] = label_content
                current_label = label_match.group(1)
                label_content = []
                continue
            
            if current_label:
                # Basic indentation check could be added, but for now just collect
                label_content.append(line.rstrip())
        
        if current_label:
            self.labels[current_label] = label_content

    def get_line(self, label: str, index: int):
        if label not in self.labels:
            return None
        if index >= len(self.labels[label]):
            return None
        return self.labels[label][index]

# --- SESSION MANAGEMENT ---

def load_session(session_id: str) -> SessionState:
    path = f"{session_id}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            return SessionState(**data)
    return SessionState(session_id=session_id)

def save_session(state: SessionState):
    with open(f"{state.session_id}.json", "w") as f:
        f.write(state.json())

def get_reference(category: str, name: str, sub_type: str = None) -> str:
    path = ""
    if category == "characters":
        # Check for specific profile/description if needed
        if sub_type:
            path = f"reference/characters/{name}/{name}_{sub_type}.txt"
        else:
            # Fallback to description
            path = f"reference/characters/{name}/{name}_description.txt"
    elif category == "backgrounds":
        path = f"reference/backgrounds/{name}.txt"
    elif category == "scenes":
        path = f"reference/scenes/{name}.txt"
    elif category == "animations":
        path = f"reference/animations/{name}.txt"
    
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return f"[{name} {sub_type or ''} placeholder]"

# --- API ENDPOINTS ---

@app.get("/session/{session_id}")
async def get_state(session_id: str):
    state = load_session(session_id)
    return state

@app.post("/session/{session_id}/step")
async def step_game(session_id: str, update: GameUpdate):
    state = load_session(session_id)
    parser = NarratParser("phase1.narrat")
    
    if update.command == "R":
        parser.parse()
        state.line_index = 0
        state.dialogue_log = []
        save_session(state)
        return await process_current_step(state, parser)
        
    if update.command == "B":
        if state.history:
            last_state = state.history.pop()
            state.current_label = last_state["current_label"]
            state.line_index = last_state["line_index"]
            state.variables = last_state.get("variables", {})
            state.dialogue_log = last_state.get("dialogue_log", [])
            save_session(state)
        return await process_current_step(state, parser)

    state.history.append({
        "current_label": state.current_label,
        "line_index": state.line_index,
        "variables": state.variables.copy(),
        "dialogue_log": state.dialogue_log.copy()
    })
    
    return await process_current_step(state, parser, update.command)

async def process_current_step(state: SessionState, parser: NarratParser, command: str = None):
    current_bg = state.variables.get("__current_bg", "None")
    current_scene = state.variables.get("__current_scene")
    current_anim = state.variables.get("__current_anim")
    
    while True:
        line_text = parser.get_line(state.current_label, state.line_index)
        if line_text is None:
            return DialogueResponse(
                type="end", 
                text="End of script reached.", 
                current_label=state.current_label,
                background=current_bg,
                background_desc=get_reference("backgrounds", current_bg) if current_bg != "None" else "",
                variables=state.variables
            )
        
        stripped = line_text.strip()
        state.line_index += 1
        
        # talk [char] "[text]"
        talk_match = re.match(r'talk\s+([\w_]+)\s+"(.*)"', stripped)
        if talk_match:
            char = talk_match.group(1)
            text = talk_match.group(2)
            
            state.dialogue_log.append({"character": char, "text": text})
            # Keep log reasonably sized
            if len(state.dialogue_log) > 20:
                state.dialogue_log.pop(0)

            meta = {
                "profile": get_reference("characters", char, "profile"),
                "description": get_reference("characters", char, "description"),
                "placeholder": get_reference("characters", char, "idle"),
                "emotion": state.variables.get(f"__emo_{char}", "Neutral")
            }
            save_session(state)
            
            scene_data = None
            if current_scene:
                scene_data = {"name": current_scene, "content": get_reference("scenes", current_scene)}
            
            anim_data = None
            if current_anim:
                anim_data = {"name": current_anim, "content": get_reference("animations", current_anim)}

            return DialogueResponse(
                type="talk", 
                character=char, 
                text=text, 
                meta=meta, 
                current_label=state.current_label,
                background=current_bg,
                background_desc=get_reference("backgrounds", current_bg) if current_bg != "None" else "",
                active_scene=scene_data,
                active_animation=anim_data,
                variables=state.variables,
                dialogue_log=state.dialogue_log
            )

        # background [name]
        bg_match = re.match(r'background\s+([\w_]+)', stripped)
        if bg_match:
            bg_name = bg_match.group(1)
            state.variables["__current_bg"] = bg_name
            state.variables["__current_scene"] = None # Clear on new BG
            state.variables["__current_anim"] = None
            current_bg = bg_name
            current_scene = None
            current_anim = None
            continue

        # scene [name]
        scene_match = re.match(r'scene\s+([\w_]+)', stripped)
        if scene_match:
            scene_name = scene_match.group(1)
            state.variables["__current_scene"] = scene_name
            current_scene = scene_name
            continue

        # play_animation [name]
        anim_match = re.match(r'play_animation\s+([\w_]+)', stripped)
        if anim_match:
            anim_name = anim_match.group(1)
            state.variables["__current_anim"] = anim_name
            current_anim = anim_name
            continue

        # set_expression [char] [expression]
        exp_match = re.match(r'set_expression\s+([\w_]+)\s+([\w_]+)', stripped)
        if exp_match:
            char_id = exp_match.group(1)
            expression = exp_match.group(2)
            state.variables[f"__emo_{char_id}"] = expression
            continue

        # set [var] [val]
        set_match = re.match(r'set\s+([\w_]+)\s+(.*)', stripped)
        if set_match:
            var = set_match.group(1)
            val = set_match.group(2).strip()
            if val.isdigit(): val = int(val)
            state.variables[var] = val
            # Track last updated vars for the UI
            updated_vars = state.variables.get("__updated_vars", [])
            if var not in updated_vars:
                updated_vars.append(var)
            if len(updated_vars) > 3:
                updated_vars.pop(0)
            state.variables["__updated_vars"] = updated_vars
            continue

        # choice:
        if stripped == "choice:":
            options = {}
            opt_idx = 1
            temp_idx = state.line_index
            while True:
                next_line = parser.get_line(state.current_label, temp_idx)
                if not next_line: break
                opt_match = re.search(r'label:\s+"(.*)"\s+->\s+([\w_]+)', next_line)
                if opt_match:
                    options[opt_idx] = {"text": opt_match.group(1), "target": opt_match.group(2)}
                    opt_idx += 1
                    temp_idx += 1
                else:
                    break
            
            if command and command.strip().isdigit():
                idx = int(command.strip())
                if idx in options:
                    target = options[idx]["target"]
                    if target not in parser.labels:
                        save_session(state)
                        return DialogueResponse(
                            type="missing_label", 
                            text=f"Label '{target}' is missing.", 
                            meta={"target": target}, 
                            current_label=state.current_label,
                            background=current_bg,
                            background_desc=get_reference("backgrounds", current_bg) if current_bg != "None" else "",
                            variables=state.variables,
                            dialogue_log=state.dialogue_log
                        )
                    
                    state.current_label = target
                    state.line_index = 0
                    save_session(state)
                    return await process_current_step(state, parser, None)
            
            state.line_index -= 1 
            save_session(state)
            return DialogueResponse(
                type="choice", 
                options=options, 
                current_label=state.current_label,
                background=current_bg,
                background_desc=get_reference("backgrounds", current_bg) if current_bg != "None" else "",
                variables=state.variables,
                dialogue_log=state.dialogue_log
            )

        # if [expression]:
        if_match = re.match(r'if\s+(.*):', stripped)
        if if_match:
            expression = if_match.group(1).strip()
            # If the expression doesn't evaluate to True, skip the next line
            if not evaluate_expression(expression, state.variables):
                state.line_index += 1
            continue

    save_session(state)
    return DialogueResponse(
        type="end", 
        text="Script error or end.", 
        current_label=state.current_label,
        variables=state.variables,
        dialogue_log=state.dialogue_log
    )

import requests as sync_requests # For AI API call

def get_ai_context():
    with open("narrat_syntax.md", "r") as f:
        syntax = f.read()
    
    # Get character context
    anya_profile = get_reference("characters", "anya", "profile")
    anya_desc = get_reference("characters", "anya", "description")
    
    return f"""
SYNTX REFERENCE:
{syntax}

CHARACTER CONTEXT:
Anya Profile: {anya_profile}
Anya Appearance: {anya_desc}
"""

@app.post("/session/{session_id}/generate")
async def generate_label(session_id: str, req: GenerateRequest):
    with open("config.json", "r") as f:
        config = json.load(f)
    
    if config["api_key"] == "YOUR_API_KEY_HERE":
        new_content = f"\nlabel {req.target}:\n    talk anya \"This is a fallback for {req.target}. Set your API key in config.json!\"\n    -> start\n"
    else:
        context = get_ai_context()
        prompt = f"""
You are an expert Narrat script writer. Based on the context below, write a NEW label named '{req.target}'.

RULES:
1. Follow character's voice and immersive cyberpunk style.
2. End with a valid choice block or '-> start'.
3. Use exact syntax: label: "Text" -> target_label
4. If you introduce a NEW background (e.g. background club_bar) or NEW character, you MUST provide a description for it at the end.

{context}

Format your response as follows:
[SCRIPT]
(Your .narrat code here)

[METADATA]
background: name | description
character: name | profile | appearance

Generate only the code and metadata.
"""
        
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            res = sync_requests.post(config["api_url"], json=payload, headers=headers)
            res.raise_for_status()
            raw_ai_response = res.json()["choices"][0]["message"]["content"]
            
            # Parsing Script
            script_part = ""
            if "[SCRIPT]" in raw_ai_response:
                script_part = raw_ai_response.split("[SCRIPT]")[1].split("[METADATA]")[0].strip()
            else:
                script_part = raw_ai_response.split("[METADATA]")[0].strip()
            
            script_part = script_part.replace("```narrat", "").replace("```", "").strip()
            if not script_part.startswith(f"label {req.target}:"):
                new_content = f"\nlabel {req.target}:\n" + script_part
            else:
                new_content = "\n" + script_part

            # Parsing Metadata
            if "[METADATA]" in raw_ai_response:
                meta_part = raw_ai_response.split("[METADATA]")[1].strip()
                for line in meta_part.split("\n"):
                    if line.startswith("background:"):
                        _, content = line.split(":", 1)
                        parts = content.split("|")
                        if len(parts) >= 2:
                            bg_name = parts[0].strip()
                            bg_desc = parts[1].strip()
                            with open(f"reference/backgrounds/{bg_name}.txt", "w") as f:
                                f.write(bg_desc)
                    elif line.startswith("character:"):
                        _, content = line.split(":", 1)
                        parts = content.split("|")
                        if len(parts) >= 3:
                            char_name = parts[0].strip()
                            char_prof = parts[1].strip()
                            char_desc = parts[2].strip()
                            os.makedirs(f"reference/characters/{char_name}", exist_ok=True)
                            with open(f"reference/characters/{char_name}/{char_name}_profile.txt", "w") as f:
                                f.write(char_prof)
                            with open(f"reference/characters/{char_name}/{char_name}_description.txt", "w") as f:
                                f.write(char_desc)
                
        except Exception as e:
            return HTTPException(status_code=500, detail=f"AI Generation failed: {str(e)}")

    with open("phase1.narrat", "a") as f:
        f.write("\n" + new_content)
    
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8045)
