import re
import json
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from src.server.models import DialogueResponse, SessionState
from src.server.utils import get_reference, save_session
from src.server.expressions import evaluate_expression

if TYPE_CHECKING:
    from src.server.parser import NarratParser

logger = logging.getLogger("narrat_api")

async def process_current_step(game_id: str, state: SessionState, parser: 'NarratParser', command: str = None):
    """
    The main execution loop for the Narrat script parser.
    Handles non-blocking commands automatically and returns on blocking ones (talk, choice).
    """
    logger.info(f"--- STEP START: {state.current_label} @ {state.line_index} (Cmd: '{command}') ---")
    
    # reprocessing = (command == "B_REPROCESS" or command == "R")
    
    loop_safety = 0
    while loop_safety < 1000:
        loop_safety += 1
        line_data = parser.get_line(state.current_label, state.line_index)
        
        if line_data is None:
            if state.current_label not in parser.labels:
                last_char = state.dialogue_log[-1]["character"] if state.dialogue_log else "narrator"
                return DialogueResponse(
                    type="missing_label", 
                    character=last_char,
                    meta={"target": state.current_label}, 
                    text=f"Label '{state.current_label}' missing.", 
                    variables=state.variables, 
                    dialogue_log=state.dialogue_log
                )
            return DialogueResponse(type="end", text="End of script.", variables=state.variables, dialogue_log=state.dialogue_log)

        line_num, line_text = line_data
        stripped = line_text.strip()

        if not stripped or stripped.startswith("//"):
            state.line_index += 1
            continue

        # --- NON-BLOCKING COMMANDS ---
        
        if re.match(r'^background\s+([\w_]+)', stripped):
            bg = re.match(r'^background\s+([\w_]+)', stripped).group(1)
            state.variables["__current_bg"] = bg
            state.line_index += 1; continue

        if re.match(r'^scene\s+([\w_]+)', stripped):
            sc = re.match(r'^scene\s+([\w_]+)', stripped).group(1)
            state.variables["__current_scene"] = sc
            state.line_index += 1; continue

        if re.match(r'^set_expression\s+([\w_]+)\s+([\w_]+)', stripped):
            m = re.match(r'^set_expression\s+([\w_]+)\s+([\w_]+)', stripped)
            char, emo = m.group(1), m.group(2)
            state.variables[f"__emo_{char}"] = emo
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            vn = f"{char}_emotion"
            if vn not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(vn)
            state.variables[vn] = emo
            state.line_index += 1; continue

        if re.match(r'^set\s+([\w_.]+)\s+(.*)$', stripped):
            m = re.match(r'^set\s+([\w_.]+)\s+(.*)$', stripped)
            var_path, val_str = m.group(1), m.group(2).strip()
            if val_str.isdigit(): val = int(val_str)
            elif val_str.lower() == "true": val = True
            elif val_str.lower() == "false": val = False
            else: val = val_str.strip('"').strip("'")
            
            clean_path = var_path[5:] if var_path.startswith("data.") else var_path
            path_parts = clean_path.split(".")
            curr = state.variables
            for p in path_parts[:-1]:
                if p not in curr or not isinstance(curr[p], dict): curr[p] = {}
                curr = curr[p]
            curr[path_parts[-1]] = val
            
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            if var_path not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(var_path)
            if len(state.variables["__updated_vars"]) > 10: state.variables["__updated_vars"].pop(0)
            state.line_index += 1; continue

        if re.match(r'^(?:jump|->)\s+([\w_]+)', stripped):
            target = re.match(r'^(?:jump|->)\s+([\w_]+)', stripped).group(1)
            state.current_label, state.line_index = target, 0
            continue

        if re.match(r'^if\s+(.*):$', stripped):
            expr = re.match(r'^if\s+(.*):$', stripped).group(1).strip()
            if evaluate_expression(expr, state.variables):
                state.line_index += 1
            else:
                base_indent = len(line_text) - len(line_text.lstrip())
                state.line_index += 1
                while True:
                    nxt = parser.get_line(state.current_label, state.line_index)
                    if not nxt: break
                    if not nxt[1].strip(): state.line_index += 1; continue
                    if (len(nxt[1]) - len(nxt[1].lstrip())) <= base_indent: break
                    state.line_index += 1
            continue

        # --- BLOCKING COMMANDS ---

        # 1. Choice
        if stripped == "choice:":
            # Parse options
            options, opt_idx, temp_idx = {}, 1, state.line_index + 1
            while True:
                nxt = parser.get_line(state.current_label, temp_idx)
                if not nxt: break
                if not nxt[1].strip() or nxt[1].strip().startswith("//"): 
                    temp_idx += 1; continue
                opt_m = re.match(r'^\s*"(.*)":\s*(?://.*)?$', nxt[1])
                if opt_m:
                    label_text, s_idx, target_lbl = opt_m.group(1), temp_idx + 1, None
                    while True:
                        j_data = parser.get_line(state.current_label, s_idx)
                        if not j_data: break
                        if not j_data[1].strip() or j_data[1].strip().startswith("//"): s_idx += 1; continue
                        if re.match(r'^\s*"(.*)":\s*(?://.*)?$', j_data[1]): break
                        m = re.search(r'(?:jump|->)\s+([\w_]+)', j_data[1])
                        if m: target_lbl = m.group(1); break
                        s_idx += 1
                    if target_lbl:
                        options[str(opt_idx)] = {"text": label_text, "target": target_lbl}
                        opt_idx += 1; temp_idx = s_idx + 1; continue
                break
            
            # Handle selection
            if command and command.strip().isdigit():
                cmd_str = command.strip()
                if cmd_str in options:
                    state.current_label, state.line_index = options[cmd_str]["target"], 0
                    save_session(game_id, state)
                    return await process_current_step(game_id, state, parser, "B_REPROCESS")

            # Otherwise, return choice response and STAY on this line index
            bg = state.variables.get("__current_bg", "None")
            last_char = state.dialogue_log[-1]["character"] if state.dialogue_log else "narrator"
            
            char_meta = {
                "profile": get_reference(game_id, "characters", last_char, "profile"),
                "description": get_reference(game_id, "characters", last_char, "description"),
                "placeholder": get_reference(game_id, "characters", last_char, "idle"),
                "emotion": state.variables.get(f"__emo_{last_char}", "Neutral")
            }
            
            return DialogueResponse(
                type="choice", options=options, text="Select an option:", 
                character=last_char, background=bg, meta=char_meta,
                current_label=state.current_label, line_index=state.line_index,
                background_desc=get_reference(game_id, "backgrounds", bg) if bg != "None" else "",
                variables=state.variables, dialogue_log=state.dialogue_log
            )

        # 2. Dialogue / Talk
        char, text = None, None
        t_m = re.match(r'^(?:talk\s+)?([\w_]+)(?:\s+[\w_]+)?\s+"(.*)"$', stripped)
        if t_m and t_m.group(1) not in ["background", "scene", "jump", "set", "set_expression", "choice", "if", "var"]:
            char, text = t_m.group(1), t_m.group(2)
        elif re.match(r'^"(.*)"$', stripped):
            char, text = "narrator", re.match(r'^"(.*)"$', stripped).group(1)

        if char and text is not None:
            current_idx = state.line_index
            state.line_index += 1
            
            state.dialogue_log.append({"character": char, "text": text})
            if len(state.dialogue_log) > 20: state.dialogue_log.pop(0)
            state.history.append(json.loads(state.model_dump_json()))
            save_session(game_id, state)
            
            bg = state.variables.get("__current_bg", "None")
            meta = {
                "profile": get_reference(game_id, "characters", char, "profile"),
                "description": get_reference(game_id, "characters", char, "description"),
                "placeholder": get_reference(game_id, "characters", char, "idle"),
                "emotion": state.variables.get(f"__emo_{char}", "Neutral")
            }
            return DialogueResponse(
                type="talk", character=char, text=text, meta=meta,
                current_label=state.current_label, line_index=current_idx,
                background=bg, background_desc=get_reference(game_id, "backgrounds", bg) if bg != "None" else "",
                variables=state.variables, dialogue_log=state.dialogue_log
            )

        # 3. Fallback
        state.line_index += 1
        
    return DialogueResponse(type="end", text="Execution safety limit reached.")
