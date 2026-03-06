import os
import re
import logging
import sys

logger = logging.getLogger("narrat_api")

from src.server.expressions import evaluate_expression

class NarratParser:
    def __init__(self, game_id: str = None, filepath: str = None):
        if filepath:
            self.filepath = filepath
        else:
            from src.server.utils import get_game_path
            self.filepath = get_game_path(game_id, "phase1.narrat")
        
        self.labels = {}
        self.errors = []
        self.parse()

    def parse(self):
        if not os.path.exists(self.filepath):
            self.errors.append(f"File not found: {self.filepath}")
            return
            
        with open(self.filepath, "r") as f:
            lines = f.readlines()
            
        self.labels = {}
        self.errors = []
        current_label = None
        label_content = []
        
        # Commands that usually start a block or are common
        valid_commands = [
            "talk", "think", "narrate", "choice", "set", "var", "jump", 
            "run", "return", "if", "else", "background", "scene", 
            "play", "pause", "stop", "add", "add_item", "remove_item",
            "start_quest", "complete_quest", "add_level", "roll", 
            "add_stat", "set_stat", "set_screen", "random"
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
                # Ensure labels aren't commands
                if lbl_name in valid_commands:
                    self.errors.append(f"L{line_num}: Label name '{lbl_name}' is a reserved command.")
                
                if current_label:
                    self.labels[current_label] = label_content
                current_label = lbl_name
                label_content = []
                continue

            # 2. Check Indentation (Must be under a label)
            if not current_label:
                self.errors.append(f"L{line_num}: Content found outside of any label: '{stripped}'")
                continue
                
            indent = len(raw_line) - len(raw_line.lstrip())
            if indent == 0:
                self.errors.append(f"L{line_num}: Command must be indented: '{stripped}'")
            elif indent % 4 != 0:
                # We recommend 4-space indentation
                pass # Non-critical for now but worth noting

            # 3. Check Quotes
            if stripped.count('"') % 2 != 0:
                self.errors.append(f"L{line_num}: Unclosed double quotes in line.")

            # 4. Check basic command validity
            first_word = stripped.split()[0].replace('(', '')
            # If it starts with a quote, it's implicit narrate
            if not stripped.startswith('"') and not first_word in valid_commands and not ":" in stripped:
                # Check if it's a shorthand char "text"
                shorthand = re.match(r'^([\w_]+)\s+"(.*)"$', stripped)
                if not shorthand:
                    # Might be an expression or something advanced, but worth a warning
                    pass

            label_content.append((i, raw_line))

        if current_label:
            self.labels[current_label] = label_content
            
        # Final validation
        if "main" not in self.labels:
            self.errors.append("Missing required 'main:' label entry point.")

        logger.info(f"Parsed {len(self.labels)} labels from {self.filepath}. Errors: {len(self.errors)}")

    def get_line(self, label: str, index: int):
        if label not in self.labels: return None
        if index >= len(self.labels[label]): return None
        return self.labels[label][index]

    def detect_assets(self):
        """
        Scans the narrat script content to automatically identify assets.
        - Characters: extracted from 'talk', 'think' or shorthand line start.
        - Backgrounds: extracted from 'background' command.
        - Variables: extracted from 'set' or 'var' commands (base path only).
        Returns a dictionary of sets containing the unique IDs found.
        """
        assets = {"characters": set(), "backgrounds": set(), "variables": set()}
        valid_commands = [
            "talk", "think", "narrate", "choice", "set", "var", "jump", 
            "run", "return", "if", "else", "background", "scene", 
            "play", "pause", "stop", "add", "add_item", "remove_item",
            "start_quest", "complete_quest", "add_level", "roll", 
            "add_stat", "set_stat", "set_screen", "random"
        ]

        if not os.path.exists(self.filepath): return assets
        with open(self.filepath, "r") as f: content = f.read()
        
        # 1. Characters: from 'talk name', 'think name', or 'name "text"'
        talk_matches = re.findall(r'^\s*talk\s+([\w_]+)', content, re.MULTILINE)
        think_matches = re.findall(r'^\s*think\s+([\w_]+)', content, re.MULTILINE)
        shorthand_matches = re.findall(r'^\s*([\w_]+)\s+"', content, re.MULTILINE)
        
        for name in talk_matches + think_matches + shorthand_matches:
            if name not in valid_commands and name != "narrator":
                assets["characters"].add(name.lower())

        # 2. Backgrounds: from 'background name'
        bg_matches = re.findall(r'^\s*background\s+([\w_]+)', content, re.MULTILINE)
        for bg in bg_matches:
            assets["backgrounds"].add(bg.lower())

        # 3. Variables: from 'set name value' or 'var name value'
        set_matches = re.findall(r'^\s*(?:set|var)\s+([\w_.]+)', content, re.MULTILINE)
        for var in set_matches:
            # We take the base name for variables (e.g. data.points -> data)
            base_var = var.split('.')[0]
            assets["variables"].add(base_var.lower())

        return {k: sorted(list(v)) for k, v in assets.items()}

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
