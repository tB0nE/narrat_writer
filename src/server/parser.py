import os
import re
import logging
import sys

logger = logging.getLogger("narrat_api")

from src.server.expressions import evaluate_expression

_parser_cache = {}

class NarratParser:
    def __new__(cls, game_id: str):
        if game_id in _parser_cache:
            return _parser_cache[game_id]
        instance = super(NarratParser, cls).__new__(cls)
        _parser_cache[game_id] = instance
        return instance

    def __init__(self, game_id: str):
        if hasattr(self, "_initialized"): return
        from src.server.utils import get_game_path
        self.game_id = game_id
        self.scripts_dir = get_game_path(game_id, "scripts")
        
        self.labels = {} # label_name -> list of (line_num, line_text)
        self.label_to_file = {} # label_name -> relative_file_path
        self.errors = []
        self.parse_all()
        self._initialized = True

    def refresh(self):
        self.labels = {}
        self.label_to_file = {}
        self.errors = []
        self.parse_all()

    def parse_all(self):
        """Recursively finds and parses all .narrat files in the scripts directory."""
        if not os.path.exists(self.scripts_dir):
            self.errors.append(f"Scripts directory not found: {self.scripts_dir}")
            return

        for root, _, files in os.walk(self.scripts_dir):
            for file in files:
                if file.endswith(".narrat"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.scripts_dir)
                    self.parse_file(full_path, rel_path)
        
        if "main" not in self.labels:
            self.errors.append("Missing required 'main:' label entry point in scripts.")

    def parse_file(self, full_path: str, rel_path: str):
        """Parses a single narrat file and adds labels to the global map."""
        with open(full_path, "r") as f:
            lines = f.readlines()
            
        current_label = None
        label_content = []
        
        valid_commands = [
            "talk", "think", "narrate", "choice", "set", "var", "jump", 
            "run", "return", "if", "else", "background", "scene", 
            "play", "pause", "stop", "add", "add_item", "remove_item",
            "start_quest", "complete_quest", "add_level", "roll", 
            "add_stat", "set_stat", "set_screen", "random", "wait"
        ]

        for i, line in enumerate(lines):
            line_num = i + 1
            raw_line = line.rstrip()
            stripped = raw_line.strip()
            
            if not stripped or stripped.startswith("//"):
                continue
            
            # 1. Check Label Definition
            label_match = re.match(r"^([\w_]+):\s*(?://.*)?$", raw_line)
            if label_match:
                lbl_name = label_match.group(1)
                if lbl_name in valid_commands:
                    self.errors.append(f"[{rel_path}] L{line_num}: Label name '{lbl_name}' is a reserved command.")
                
                if lbl_name in self.labels:
                    self.errors.append(f"[{rel_path}] L{line_num}: Duplicate label '{lbl_name}' (already defined in {self.label_to_file[lbl_name]})")
                
                if current_label:
                    self.labels[current_label] = label_content
                
                current_label = lbl_name
                self.label_to_file[lbl_name] = rel_path
                label_content = []
                continue

            # 2. Check Indentation
            if not current_label:
                self.errors.append(f"[{rel_path}] L{line_num}: Content found outside of any label: '{stripped}'")
                continue
                
            indent = len(raw_line) - len(raw_line.lstrip())
            if indent == 0:
                self.errors.append(f"[{rel_path}] L{line_num}: Command must be indented: '{stripped}'")

            # 3. Basic line validation
            if stripped.count('"') % 2 != 0:
                self.errors.append(f"[{rel_path}] L{line_num}: Unclosed double quotes.")

            label_content.append((i, raw_line))

        if current_label:
            self.labels[current_label] = label_content

    def detect_assets(self):
        """Extracts characters, backgrounds, and variables used in all script files."""
        assets = {"characters": set(), "backgrounds": set(), "variables": set()}
        valid_commands = [
            "talk", "think", "narrate", "choice", "set", "var", "jump", 
            "run", "return", "if", "else", "background", "scene", 
            "play", "pause", "stop", "add", "add_item", "remove_item",
            "start_quest", "complete_quest", "add_level", "roll", 
            "add_stat", "set_stat", "set_screen", "random", "wait"
        ]

        # Scan all .narrat files
        for root, _, files in os.walk(self.scripts_dir):
            for file in files:
                if file.endswith(".narrat"):
                    with open(os.path.join(root, file), "r") as f:
                        content = f.read()
                    
                    # Characters
                    talk_matches = re.findall(r'^\s*talk\s+([\w_]+)', content, re.MULTILINE)
                    think_matches = re.findall(r'^\s*think\s+([\w_]+)', content, re.MULTILINE)
                    shorthand_matches = re.findall(r'^\s*([\w_]+)\s+"', content, re.MULTILINE)
                    
                    for name in talk_matches + think_matches + shorthand_matches:
                        if name not in valid_commands and name != "narrator":
                            assets["characters"].add(name.lower())

                    # Backgrounds
                    bg_matches = re.findall(r'^\s*background\s+([\w_]+)', content, re.MULTILINE)
                    for bg in bg_matches:
                        assets["backgrounds"].add(bg.lower())

                    # Variables
                    set_matches = re.findall(r'^\s*(?:set|var)\s+([\w_.]+)', content, re.MULTILINE)
                    for var in set_matches:
                        base_var = var.split('.')[0]
                        assets["variables"].add(base_var.lower())

        return {k: sorted(list(v)) for k, v in assets.items()}

    def get_line(self, label: str, index: int):
        if label not in self.labels: return None
        if index >= len(self.labels[label]): return None
        return self.labels[label][index]

    def validate(self):
        """Returns (is_valid, list_of_errors)"""
        return len(self.errors) == 0, self.errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parser.py <path_to_narrat_file>")
        sys.exit(1)
    
    parser = NarratParser(filepath=sys.argv[1])
    is_valid, errors = parser.validate()
    if is_valid:
        print(f"✓ {sys.argv[1]} is valid!")
    else:
        print(f"✗ {sys.argv[1]} has {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
