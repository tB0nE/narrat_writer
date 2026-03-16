import re
import json
import logging
import asyncio
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
    logger.info(f"--- Step Start: {state.current_label} @ {state.line_index} (Cmd: '{command}') ---")
    
    # 1. Handle Choice selection if command is numeric
    if command and command.strip().isdigit():
        target_idx = state.last_choice_index if state.last_choice_index is not None else state.line_index - 1
        line_data = parser.get_line(state.current_label, target_idx)
        
        if line_data and re.match(r'^\s*choice:\s*(?://.*)?$', line_data[1]):
            options, _, end_idx = parse_choice_options(parser, state, state.current_label, target_idx + 1)
            if command.strip() in options:
                opt = options[command.strip()]
                
                # Push to choice stack for nested logic
                if "__choice_stack" not in state.variables: state.variables["__choice_stack"] = []
                state.variables["__choice_stack"].append(end_idx)
                
                state.current_label = opt["target"]
                if "target_line" in opt:
                    state.line_index = opt["target_line"]
                    logger.info(f"Choice '{command}' -> {state.current_label} @ {state.line_index}")
                else:
                    state.line_index = 0
                    state.variables.pop("__choice_stack", None)
                    logger.info(f"Choice '{command}' -> New label: {state.current_label}")
                
                state.last_choice_index = None # Reset after successful selection
            else:
                logger.warning(f"Invalid choice index '{command}' for choice at index {target_idx}")

    # 2. Main Execution Loop
    loop_safety = 0
    while loop_safety < 500:
        loop_safety += 1
        line_data = parser.get_line(state.current_label, state.line_index)
        
        if line_data is None:
            if "__choice_stack" in state.variables and state.variables["__choice_stack"]:
                state.line_index = state.variables["__choice_stack"].pop()
                logger.info(f"End of label, returning to choice stack @ {state.line_index}")
                continue
            if state.current_label not in parser.labels:
                return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' missing.", variables=state.variables, dialogue_log=state.dialogue_log)
            return DialogueResponse(type="end", text="End of script.", variables=state.variables, dialogue_log=state.dialogue_log)

        line_num, line_text = line_data
        stripped = line_text.strip()
        indent = len(line_text) - len(line_text.lstrip())

        if not stripped or stripped.startswith("//"):
            state.line_index += 1; continue

        logger.debug(f"Processing: [{state.current_label}:{state.line_index}] {stripped}")

        # --- A. NON-BLOCKING COMMANDS ---
        
        if stripped == "clear_dialog":
            state.dialogue_log = []
            state.line_index += 1; continue

        if re.match(r'^background\s+([\w_]+)', stripped):
            state.variables["__current_bg"] = re.match(r'^background\s+([\w_]+)', stripped).group(1)
            state.line_index += 1; continue

        if re.match(r'^scene\s+([\w_]+)', stripped):
            state.variables["__current_scene"] = re.match(r'^scene\s+([\w_]+)', stripped).group(1)
            state.line_index += 1; continue

        if re.match(r'^set_expression\s+([\w_]+)\s+([\w_]+)', stripped):
            m = re.match(r'^set_expression\s+([\w_]+)\s+([\w_]+)', stripped)
            state.variables[f"__emo_{m.group(1)}"] = m.group(2)
            state.line_index += 1; continue

        if re.match(r'^(?:set|var|set_stat)\s+([\w_.]+)\s+(.*)$', stripped):
            m = re.match(r'^(?:set|var|set_stat)\s+([\w_.]+)\s+(.*)$', stripped)
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
            logger.info(f"Var set: {var_path} = {val}")
            state.line_index += 1; continue

        if re.match(r'^add(?:_stat|_level)?\s+([\w_.]+)\s+(.*)$', stripped):
            m = re.match(r'^add(?:_stat|_level)?\s+([\w_.]+)\s+(.*)$', stripped)
            var_path, val_str = m.group(1), m.group(2).strip()
            try: val = int(val_str)
            except: val = evaluate_expression(val_str, state.variables) or 0
            
            clean_path = var_path[5:] if var_path.startswith("data.") else var_path
            path_parts = clean_path.split(".")
            curr = state.variables
            for p in path_parts[:-1]:
                if p not in curr or not isinstance(curr[p], dict): curr[p] = {}
                curr = curr[p]
            
            old_val = curr.get(path_parts[-1], 0)
            if isinstance(old_val, (int, float)) and isinstance(val, (int, float)):
                curr[path_parts[-1]] = old_val + val

            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            if var_path not in state.variables["__updated_vars"]: state.variables["__updated_vars"].append(var_path)
            logger.info(f"Var add: {var_path} + {val} = {curr[path_parts[-1]]}")
            state.line_index += 1; continue

        if re.match(r'^(?:jump|->)\s+([\w_]+)', stripped):
            target = re.match(r'^(?:jump|->)\s+([\w_]+)', stripped).group(1)
            logger.info(f"Jump: {target}")
            state.current_label, state.line_index = target, 0
            state.variables.pop("__choice_stack", None)
            continue

        if re.match(r'^if\s+(.*):$', stripped):
            expr = re.match(r'^if\s+(.*):$', stripped).group(1).strip()
            if evaluate_expression(expr, state.variables):
                logger.info(f"If TRUE: {expr}")
                state.line_index += 1
            else:
                logger.info(f"If FALSE: {expr}, skipping block")
                base_indent = indent
                state.line_index += 1
                while True:
                    nxt = parser.get_line(state.current_label, state.line_index)
                    if not nxt: break
                    if not nxt[1].strip(): state.line_index += 1; continue
                    if (len(nxt[1]) - len(nxt[1].lstrip())) <= base_indent: break
                    state.line_index += 1
            continue

        if stripped == "else:":
            logger.info("Skipping else block (if was true)")
            base_indent = indent
            state.line_index += 1
            while True:
                nxt = parser.get_line(state.current_label, state.line_index)
                if not nxt: break
                if not nxt[1].strip(): state.line_index += 1; continue
                if (len(nxt[1]) - len(nxt[1].lstrip())) <= base_indent: break
                state.line_index += 1
            continue

        if re.match(r'^wait\s+(\d+)', stripped):
            ms = int(re.match(r'^wait\s+(\d+)', stripped).group(1))
            await asyncio.sleep(ms / 1000.0)
            state.line_index += 1; continue

        if re.match(r'^(?:play|stop|run|save|load|complete_objective|set_button|clear_dialog|add_stat|add_level)\b', stripped):
            state.line_index += 1; continue

        # --- B. BLOCKING COMMANDS ---

        if re.match(r'^\s*choice:\s*(?://.*)?$', stripped):
            state.last_choice_index = state.line_index
            options, prompt_text, end_idx = parse_choice_options(parser, state, state.current_label, state.line_index + 1)
            res_idx = state.line_index
            state.line_index += 1
            save_and_log_state(game_id, state)
            return build_response(game_id, state, "choice", options=options, text=prompt_text or None, line_index=res_idx)

        char, text = match_dialogue(stripped)
        if char:
            res_idx = state.line_index
            state.line_index += 1
            state.dialogue_log.append({"character": char, "text": text})
            if len(state.dialogue_log) > 20: state.dialogue_log.pop(0)
            save_and_log_state(game_id, state)
            return build_response(game_id, state, "talk", character=char, text=text, line_index=res_idx)

        if "__choice_stack" in state.variables and state.variables["__choice_stack"]:
             if re.match(r'^\s*"(.*)"\s*(?:if\s+.*)?:\s*(?://.*)?$', line_text):
                 state.line_index = state.variables["__choice_stack"].pop()
                 logger.info(f"Choice option finished, returning to choice stack @ {state.line_index}")
                 continue

        logger.warning(f"Unknown line at {state.current_label} @ {state.line_index}: '{stripped}'")
        state.line_index += 1

    return DialogueResponse(type="end", text="Safety limit.")

def parse_choice_options(parser, state, label, start_idx):
    options, opt_idx, temp_idx = {}, 1, start_idx
    prompt_text = []
    
    # 1. Collect leading text
    while True:
        nxt = parser.get_line(label, temp_idx)
        if not nxt: break
        raw = nxt[1]
        txt = raw.strip()
        if not txt or txt.startswith("//"): 
            temp_idx += 1; continue
        if re.match(r'^\s*"(.*)"\s*(?:if\s+.*)?:\s*(?://.*)?$', raw): break
        char, text = match_dialogue(txt)
        if char: prompt_text.append(f"{char}: {text}" if char != "narrator" else text)
        temp_idx += 1

    # 2. Collect options
    while True:
        nxt = parser.get_line(label, temp_idx)
        if not nxt: break
        raw = nxt[1]; txt = raw.strip()
        if not txt or txt.startswith("//"): temp_idx += 1; continue
        opt_match = re.match(r'^\s*"(.*)"\s*(?:if\s+(.*))?:\s*(?://.*)?$', raw)
        if not opt_match: break
            
        label_text = opt_match.group(1); condition = opt_match.group(2)
        base_indent = len(raw) - len(raw.lstrip())
        
        if condition:
            condition = condition.strip().rstrip(":")
            if not evaluate_expression(condition, state.variables):
                temp_idx += 1
                while True:
                    n_data = parser.get_line(label, temp_idx)
                    if not n_data: break
                    if n_data[1].strip() and (len(n_data[1]) - len(n_data[1].lstrip())) <= base_indent: break
                    temp_idx += 1
                continue

        options[str(opt_idx)] = {"text": label_text, "target": label, "target_line": temp_idx + 1}
        logger.info(f"Option {opt_idx} registered at line {temp_idx + 1}")
        
        opt_idx += 1; temp_idx += 1
        while True:
            n_data = parser.get_line(label, temp_idx)
            if not n_data or (n_data[1].strip() and (len(n_data[1]) - len(n_data[1].lstrip())) <= base_indent): break
            temp_idx += 1
                
    return options, "\n".join(prompt_text), temp_idx

def match_dialogue(stripped):
    m = re.match(r'^(?:talk\s+)?([\w_]+)(?:\s+[\w_]+)?\s+"(.*)"$', stripped)
    if m and m.group(1) not in ["background", "scene", "jump", "set", "set_expression", "choice", "if", "else", "var", "wait", "add", "clear_dialog", "play", "stop", "run", "roll", "complete_objective", "set_button", "save", "load"]:
        return m.group(1), m.group(2)
    m = re.match(r'^"(.*)"$', stripped)
    if m: return "narrator", m.group(1)
    return None, None

def save_and_log_state(game_id, state):
    snapshot = state.model_dump(exclude={"history"})
    state.history.append(snapshot)
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
    res_label = kwargs.get("current_label", state.current_label) or "main"
    return DialogueResponse(
        type=rtype, character=char, background=bg,
        background_desc=get_reference(game_id, "backgrounds", bg) if bg != "None" else "",
        meta={**char_meta, **kwargs.get("meta", {})},
        current_label=res_label, line_index=kwargs.get("line_index", state.line_index),
        variables=state.variables, dialogue_log=state.dialogue_log,
        options=kwargs.get("options"), text=kwargs.get("text")
    )
