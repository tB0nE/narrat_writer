import os
import re
import logging

logger = logging.getLogger("narrat_api")

def evaluate_expression(expr: str, variables: dict) -> bool:
    """Simple expression evaluator for if statements."""
    try:
        if expr.startswith("(") and expr.endswith(")"):
            expr = expr[1:-1].strip()
        parts = expr.split()
        if len(parts) == 1:
            val = parts[0]
            if val.startswith("$"): return bool(variables.get(val[1:]))
            return val.lower() == "true"
        
        def get_val(v):
            if v.startswith("$"): return variables.get(v[1:], 0)
            return int(v) if v.isdigit() else v.strip('"').strip("'")
        
        op = parts[0]
        if op == "==": return get_val(parts[1]) == get_val(parts[2])
        if op == "!=": return get_val(parts[1]) != get_val(parts[2])
        if op == ">": return get_val(parts[1]) > get_val(parts[2])
        if op == "<": return get_val(parts[1]) < get_val(parts[2])
        return False
    except: return False

class NarratParser:
    def __init__(self, game_id: str):
        from src.server.utils import get_game_path
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
