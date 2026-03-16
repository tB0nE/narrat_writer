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
    logger.info(f"Step: {state.current_label} @ {state.line_index} (Cmd: '{command}')")
    
    # 1. Handle Choice selection if command is numeric
    if command and command.strip().isdigit():
        # The 'choice:' line is at state.line_index - 1
        line_data = parser.get_line(state.current_label, state.line_index - 1)
        if line_data and re.match(r'^\s*choice:\s*(?://.*)?$', line_data[1]):
            options, _, end_idx = parse_choice_options(parser, state, state.current_label, state.line_index)
            if command.strip() in options:
                opt = options[command.strip()]
                
                # Push to choice stack for nested logic
                if "__choice_stack" not in state.variables: state.variables["__choice_stack"] = []
                state.variables["__choice_stack"].append(end_idx)
                
                if "target_line" in opt:
                    # Jumping to a line in the same label
                    state.current_label = opt["target"] # ALWAYS update label
                    state.line_index = opt["target_line"]
                    logger.info(f"Choice selected: {command} -> {state.current_label} @ {state.line_index}")
                else:
                    # Jumping to a new label
                    target = opt["target"]
                    state.current_label, state.line_index = target, 0
                    # If we jumped to a NEW label, we lose the choice stack for that label's flow
                    # (Standard Narrat behavior: jump breaks out of blocks)
                    state.variables.pop("__choice_stack", None)
                    logger.info(f"Choice selected: {command} -> New label: {target}")
            else:
                logger.warning(f"Invalid choice index: {command}")

    # 2. Main Execution Loop
    loop_safety = 0
    while loop_safety < 500:
        loop_safety += 1
        if not state.current_label:
            logger.error("State current_label is EMPTY!")
            state.current_label = "main" # Recovery attempt

        line_data = parser.get_line(state.current_label, state.line_index)
        
        if line_data is None:
            logger.info(f"End of lines for label '{state.current_label}' at index {state.line_index}")
            # Check if we were in a choice block and need to return
            if "__choice_stack" in state.variables and state.variables["__choice_stack"]:
                state.line_index = state.variables["__choice_stack"].pop()
                logger.info(f"Popped from choice stack, returning to {state.line_index}")
                continue

            if state.current_label not in parser.labels:
                logger.warning(f"Label '{state.current_label}' missing from parser!")
                return DialogueResponse(type="missing_label", meta={"target": state.current_label}, text=f"Label '{state.current_label}' missing.", variables=state.variables, dialogue_log=state.dialogue_log)
            
            return DialogueResponse(type="end", text="End of script.", variables=state.variables, dialogue_log=state.dialogue_log)

        line_num, line_text = line_data
        stripped = line_text.strip()
        indent = len(line_text) - len(line_text.lstrip())

        if not stripped or stripped.startswith("//"):
            state.line_index += 1; continue

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
            char, emo = m.group(1), m.group(2)
            state.variables[f"__emo_{char}"] = emo
            state.line_index += 1; continue

        if re.match(r'^(?:set|var)\s+([\w_.]+)\s+(.*)$', stripped):
            m = re.match(r'^(?:set|var)\s+([\w_.]+)\s+(.*)$', stripped)
            var_path, val_str = m.group(1), m.group(2).strip()
            # ... (rest of set logic unchanged)
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

            # Tracking
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            if var_path not in state.variables["__updated_vars"]: 
                state.variables["__updated_vars"].append(var_path)
            if len(state.variables["__updated_vars"]) > 10: 
                state.variables["__updated_vars"].pop(0)

            state.line_index += 1; continue

        if re.match(r'^(?:jump|->)\s+([\w_]+)', stripped):
            target = re.match(r'^(?:jump|->)\s+([\w_]+)', stripped).group(1)
            logger.info(f"Jumping to '{target}'")
            state.current_label, state.line_index = target, 0
            state.variables.pop("__choice_stack", None) # Jump breaks choice block
            continue

        if re.match(r'^if\s+(.*):$', stripped):
            expr = re.match(r'^if\s+(.*):$', stripped).group(1).strip()
            if evaluate_expression(expr, state.variables):
                state.line_index += 1
            else:
                base_indent = indent
                state.line_index += 1
                while True:
                    nxt = parser.get_line(state.current_label, state.line_index)
                    if not nxt: break
                    if not nxt[1].strip(): state.line_index += 1; continue
                    if (len(nxt[1]) - len(nxt[1].lstrip())) <= base_indent: break
                    state.line_index += 1
            continue

        if re.match(r'^roll\s+([\w_.]+)\s+([\w_.]+)\s+(\d+)', stripped):
            # ... (roll logic unchanged)
            m = re.match(r'^roll\s+([\w_.]+)\s+([\w_.]+)\s+(\d+)', stripped)
            roll_id, stat_id, threshold = m.group(1), m.group(2), int(m.group(3))
            import random
            roll_val = random.randint(1, 100)
            success = roll_val >= threshold
            if "__updated_vars" not in state.variables: state.variables["__updated_vars"] = []
            if roll_id not in state.variables["__updated_vars"]: 
                state.variables["__updated_vars"].append(roll_id)
            if len(state.variables["__updated_vars"]) > 10: 
                state.variables["__updated_vars"].pop(0)
            state.variables[roll_id] = success
            state.line_index += 1; continue

        if re.match(r'^wait\s+(\d+)', stripped):
            ms = int(re.match(r'^wait\s+(\d+)', stripped).group(1))
            await asyncio.sleep(ms / 1000.0)
            state.line_index += 1; continue

        # --- B. BLOCKING COMMANDS ---

        if re.match(r'^\s*choice:\s*(?://.*)?$', stripped):
            options, prompt_text, end_idx = parse_choice_options(parser, state, state.current_label, state.line_index + 1)
            res_idx = state.line_index
            state.line_index += 1
            save_and_log_state(game_id, state)
            return build_response(game_id, state, "choice", options=options, text=prompt_text or None, line_index=res_idx)

        # Dialogue match
        char, text = match_dialogue(stripped)
        if char:
            res_idx = state.line_index
            state.line_index += 1
            state.dialogue_log.append({"character": char, "text": text})
            if len(state.dialogue_log) > 20: state.dialogue_log.pop(0)
            save_and_log_state(game_id, state)
            return build_response(game_id, state, "talk", character=char, text=text, line_index=res_idx)

        # If we haven't matched anything and we have a choice stack, 
        # check if we just hit another option (which means we should skip to the end)
        if "__choice_stack" in state.variables and state.variables["__choice_stack"]:
             # If this line is an option line at the same indent as the choice block's options,
             # it means we finished our selected option and are hitting the next one.
             if re.match(r'^\s*"(.*)"\s*(?:if\s+.*)?:\s*(?://.*)?$', line_text):
                 state.line_index = state.variables["__choice_stack"].pop()
                 logger.info(f"Hit another option, jumping to end index {state.line_index}")
                 continue

        # Unrecognized - skip
        logger.warning(f"Unknown line at {state.current_label} @ {state.line_index}: '{stripped}'")
        state.line_index += 1

    return DialogueResponse(type="end", text="Safety limit.")

# --- HELPERS ---

def parse_choice_options(parser, state, label, start_idx):
    options, opt_idx, temp_idx = {}, 1, start_idx
    prompt_text = []
    
    line_data = parser.get_line(label, start_idx - 1)
    choice_indent = len(line_data[1]) - len(line_data[1].lstrip()) if line_data else 0

    # 1. Collect leading text
    while True:
        nxt = parser.get_line(label, temp_idx)
        if not nxt: break
        raw = nxt[1]
        txt = raw.strip()
        if not txt or txt.startswith("//"): 
            temp_idx += 1; continue
        
        if re.match(r'^\s*"(.*)"\s*(?:if\s+.*)?:\s*(?://.*)?$', raw):
            break
        
        char, text = match_dialogue(txt)
        if char:
            prompt_text.append(f"{char}: {text}" if char != "narrator" else text)
        temp_idx += 1

    # 2. Collect options
    first_opt_idx = temp_idx
    while True:
        nxt = parser.get_line(label, temp_idx)
        if not nxt: break
        raw = nxt[1]
        txt = raw.strip()
        if not txt or txt.startswith("//"): 
            temp_idx += 1; continue
            
        opt_match = re.match(r'^\s*"(.*)"\s*(?:if\s+(.*))?:\s*(?://.*)?$', raw)
        if not opt_match: break
            
        label_text = opt_match.group(1)
        condition = opt_match.group(2)
        
        # Strip trailing colon from condition if it exists (captured by regex)
        if condition:
            condition = condition.strip().rstrip(":")
            if not evaluate_expression(condition, state.variables):
                # Skip this option
                base_indent = len(raw) - len(raw.lstrip())
                temp_idx += 1
                while True:
                    n_data = parser.get_line(label, temp_idx)
                    if not n_data: break
                    if not n_data[1].strip(): temp_idx += 1; continue
                    if (len(n_data[1]) - len(n_data[1].lstrip())) <= base_indent: break
                    temp_idx += 1
                continue

        base_indent = len(raw) - len(raw.lstrip())
        
        s_idx, target_lbl = temp_idx + 1, None
        while True:
            j_data = parser.get_line(label, s_idx)
            if not j_data: break
            jc = j_data[1].strip()
            if not jc or jc.startswith("//"): s_idx += 1; continue
            if (len(j_data[1]) - len(j_data[1].lstrip())) <= base_indent: break
            
            m = re.search(r'(?:jump|->)\s+([\w_]+)', jc)
            if m: target_lbl = m.group(1); break
            s_idx += 1
            
        if target_lbl:
            options[str(opt_idx)] = {"text": label_text, "target": target_lbl}
            logger.info(f"Option {opt_idx}: target={target_lbl}")
        else:
            # If no jump, jump to the next line after the option definition within the SAME label
            options[str(opt_idx)] = {"text": label_text, "target": label, "target_line": temp_idx + 1}
            logger.info(f"Option {opt_idx}: target_line={temp_idx + 1} (same label)")

        opt_idx += 1
        temp_idx += 1
        # Skip option block
        while True:
            n_data = parser.get_line(label, temp_idx)
            if not n_data: break
            if not n_data[1].strip(): temp_idx += 1; continue
            if (len(n_data[1]) - len(n_data[1].lstrip())) <= base_indent: break
            temp_idx += 1
                
    return options, "\n".join(prompt_text), temp_idx



def match_dialogue(stripped):
    # talk char "text"
    m = re.match(r'^(?:talk\s+)?([\w_]+)(?:\s+[\w_]+)?\s+"(.*)"$', stripped)
    if m and m.group(1) not in ["background", "scene", "jump", "set", "set_expression", "choice", "if", "var", "wait", "add", "clear_dialog"]:
        return m.group(1), m.group(2)
    # "text" (implicit narrate)
    m = re.match(r'^"(.*)"$', stripped)
    if m: return "narrator", m.group(1)
    return None, None

def save_and_log_state(game_id, state):
    # Snapshot WITHOUT history to prevent exponential growth
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
    
    res_label = kwargs.get("current_label", state.current_label)
    if not res_label:
        logger.error("Attempting to build response with EMPTY label!")
        res_label = "main"

    return DialogueResponse(
        type=rtype,
        character=char,
        background=bg,
        background_desc=get_reference(game_id, "backgrounds", bg) if bg != "None" else "",
        meta={**char_meta, **kwargs.get("meta", {})},
        current_label=res_label,
        line_index=kwargs.get("line_index", state.line_index),
        variables=state.variables,
        dialogue_log=state.dialogue_log,
        options=kwargs.get("options"),
        text=kwargs.get("text")
    )
