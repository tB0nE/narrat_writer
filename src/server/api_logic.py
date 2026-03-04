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
    Standard VN 'Run-until-blocked' loop.
    Processes script lines until a talk or choice is reached.
    """
    logger.info(f"Step: {state.current_label} @ {state.line_index} (Cmd: '{command}')")
    
    # 1. Handle Choice selection if command is numeric
    if command and command.strip().isdigit():
        # Choice selection always happens when we are already AT a choice block.
        # We need to re-parse the current choice to find the target.
        line_data = parser.get_line(state.current_label, state.line_index)
        if line_data and line_data[1].strip() == "choice:":
            options = parse_choice_options(parser, state.current_label, state.line_index + 1)
            if command.strip() in options:
                state.current_label, state.line_index = options[command.strip()]["target"], 0
                logger.info(f"Choice selected: {command} -> {state.current_label}")
                # After a choice jump, we fall through to the main execution loop
            else:
                logger.warning(f"Invalid choice index: {command}")

    # 2. Main Execution Loop
    loop_safety = 0
    while loop_safety < 500:
        loop_safety += 1
        line_data = parser.get_line(state.current_label, state.line_index)
        
        if line_data is None:
            if state.current_label not in parser.labels:
                return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' missing.", variables=state.variables, dialogue_log=state.dialogue_log)
            return DialogueResponse(type="end", text="End of script.", variables=state.variables, dialogue_log=state.dialogue_log)

        line_num, line_text = line_data
        stripped = line_text.strip()

        if not stripped or stripped.startswith("//"):
            state.line_index += 1; continue

        # --- A. NON-BLOCKING COMMANDS (Update state and continue) ---
        
        if re.match(r'^background\s+([\w_]+)', stripped):
            state.variables["__current_bg"] = re.match(r'^background\s+([\w_]+)', stripped).group(1)
            state.line_index += 1; continue

        if re.match(r'^scene\s+([\w_]+)', stripped):
            state.variables["__current_scene"] = re.match(r'^scene\s+([\w_]+)', stripped).group(1)
            state.line_index += 1; continue

        if re.match(r'^set_expression\s+([\w_]+)\s+([\w_]+)', stripped):
            m = re.match(r'^set_expression\s+([\w_]+)\s+([\w_]+)', stripped)
            char, emo = m.group(1), m.group(2)
            state.variables[f"__emo_{char}"] = emo
            state.line_index += 1; continue

        if re.match(r'^set\s+([\w_.]+)\s+(.*)$', stripped):
            m = re.match(r'^set\s+([\w_.]+)\s+(.*)$', stripped)
            var_path, val_str = m.group(1), m.group(2).strip()
            # Basic parsing
            if val_str.isdigit(): val = int(val_str)
            elif val_str.lower() == "true": val = True
            elif val_str.lower() == "false": val = False
            else: val = val_str.strip('"').strip("'")
            
            # Nested update
            clean_path = var_path[5:] if var_path.startswith("data.") else var_path
            path_parts = clean_path.split(".")
            curr = state.variables
            for p in path_parts[:-1]:
                if p not in curr or not isinstance(curr[p], dict): curr[p] = {}
                curr = curr[p]
            curr[path_parts[-1]] = val
            
            # Tracking
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
                # Skip block
                base_indent = len(line_text) - len(line_text.lstrip())
                state.line_index += 1
                while True:
                    nxt = parser.get_line(state.current_label, state.line_index)
                    if not nxt: break
                    if not nxt[1].strip(): state.line_index += 1; continue
                    if (len(nxt[1]) - len(nxt[1].lstrip())) <= base_indent: break
                    state.line_index += 1
            continue

        # --- B. BLOCKING COMMANDS (Update state and return) ---

        if stripped == "choice:":
            options = parse_choice_options(parser, state.current_label, state.line_index + 1)
            save_and_log_state(game_id, state)
            return build_response(game_id, state, "choice", options=options)

        # Dialogue match
        char, text = match_dialogue(stripped)
        if char:
            res_idx = state.line_index
            state.line_index += 1
            state.dialogue_log.append({"character": char, "text": text})
            if len(state.dialogue_log) > 20: state.dialogue_log.pop(0)
            save_and_log_state(game_id, state)
            return build_response(game_id, state, "talk", character=char, text=text, line_index=res_idx)

        # Unrecognized - skip
        logger.warning(f"Unknown line: {stripped}")
        state.line_index += 1

    return DialogueResponse(type="end", text="Safety limit.")

# --- HELPERS ---

def parse_choice_options(parser, label, start_idx):
    options, opt_idx, temp_idx = {}, 1, start_idx
    while True:
        nxt = parser.get_line(label, temp_idx)
        if not nxt: break
        txt = nxt[1].strip()
        if not txt or txt.startswith("//"): temp_idx += 1; continue
        opt_m = re.match(r'^\s*"(.*)":\s*(?://.*)?$', nxt[1])
        if opt_m:
            label_text = opt_m.group(1)
            s_idx, target_lbl = temp_idx + 1, None
            while True:
                j_data = parser.get_line(label, s_idx)
                if not j_data: break
                jc = j_data[1].strip()
                if not jc or jc.startswith("//"): s_idx += 1; continue
                if re.match(r'^\s*"(.*)":', j_data[1]): break # Next option
                m = re.search(r'(?:jump|->)\s+([\w_]+)', jc)
                if m: target_lbl = m.group(1); break
                s_idx += 1
            if target_lbl:
                options[str(opt_idx)] = {"text": label_text, "target": target_lbl}
                opt_idx += 1; temp_idx = s_idx + 1; continue
        break
    return options

def match_dialogue(stripped):
    # talk char "text"
    m = re.match(r'^(?:talk\s+)?([\w_]+)(?:\s+[\w_]+)?\s+"(.*)"$', stripped)
    if m and m.group(1) not in ["background", "scene", "jump", "set", "set_expression", "choice", "if", "var"]:
        return m.group(1), m.group(2)
    # "text" (implicit narrate)
    m = re.match(r'^"(.*)"$', stripped)
    if m: return "narrator", m.group(1)
    return None, None

def save_and_log_state(game_id, state):
    state.history.append(json.loads(state.model_dump_json()))
    if len(state.history) > 50: state.history.pop(0)
    save_session(game_id, state)

def build_response(game_id, state, rtype, **kwargs):
    bg = state.variables.get("__current_bg", "None")
    char = kwargs.get("character") or (state.dialogue_log[-1]["character"] if state.dialogue_log else "narrator")
    char_meta = {
        "profile": get_reference(game_id, "characters", char, "profile"),
        "description": get_reference(game_id, "characters", char, "description"),
        "placeholder": get_reference(game_id, "characters", char, "idle"),
        "emotion": state.variables.get(f"__emo_{char}", "Neutral")
    }
    return DialogueResponse(
        type=rtype,
        character=char,
        background=bg,
        background_desc=get_reference(game_id, "backgrounds", bg) if bg != "None" else "",
        meta={**char_meta, **kwargs.get("meta", {})},
        current_label=state.current_label,
        line_index=kwargs.get("line_index", state.line_index),
        variables=state.variables,
        dialogue_log=state.dialogue_log,
        options=kwargs.get("options"),
        text=kwargs.get("text")
    )
