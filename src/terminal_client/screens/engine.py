import requests
import re
import time
import questionary
import os
from typing import Dict, List, Optional, Any
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.align import Align
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from src.terminal_client.utils import console, BASE_URL, open_in_external_editor, process_spans

class GameEngine:
    def __init__(self, game_id, session_id, custom_console=None, base_url=None):
        self.game_id = game_id
        self.session_id = session_id
        self.show_script = True
        self.data = {}
        self.focus = "actions"
        self.action_idx = 0
        self.choice_idx = 0
        self.console = custom_console or console
        self.base_url = base_url or BASE_URL
        self.label_map = {}
        self.refresh_label_map()
        
        # Determine actions based on editor availability
        self.actions = ["Next", "Back", "Reload Section", "Edit Assets", "View Script"]
        try:
            res = requests.get(f"{self.base_url}/config")
            editor = res.json().get("editor")
            if editor and editor != "None":
                self.actions.append("Edit Script")
        except: pass
        self.actions.append("Exit Game")

    def refresh_label_map(self):
        try:
            res = requests.get(f"{self.base_url}/games/{self.game_id}/label_map")
            if res.status_code == 200:
                self.label_map = res.json().get("label_map", {})
        except: pass

    def get_actions_row(self):
        parts = []
        for i, act in enumerate(self.actions):
            display_name = act
            if act == "View Script" and self.show_script:
                display_name = "Hide Script"
            
            style = "bold yellow reverse" if (self.focus == "actions" and i == self.action_idx) else "dim"
            parts.append(f"[{style}]{display_name}[/{style}]")
        return "  ".join(parts)

    def get_choices_list(self):
        if self.data.get("type") != "choice": return ""
        lines = []
        options = self.data.get("options", {})
        if not options: return "[dim]No options available.[/dim]"
        # options is a dict { "1": {"text": "...", "target": "..."}, ... }
        for i, (key, opt) in enumerate(options.items()):
            text = process_spans(opt['text'])
            if self.focus == "choices" and i == self.choice_idx: 
                lines.append(f"> [bold black on yellow] {text} [/bold black on yellow]")
            else: 
                lines.append(f"  {text}")
        return "\n".join(lines)

    def get_descriptions_panel(self):
        char = self.data.get("character") or "narrator"
        meta = self.data.get("meta") or {}
        bg = self.data.get("background", "None")
        bg_desc = self.data.get("background_desc", "")
        text = f"[bold cyan]Background:[/bold cyan] {bg}\n[dim]{bg_desc}[/dim]\n\n"
        
        char_name = str(char).capitalize() if char else "Narrator"
        text += f"[bold cyan]Active Character:[/bold cyan] {char_name}\n"
        if meta.get("emotion"): text += f"[dim]Emotion: {meta['emotion']}[/dim]\n"
        if meta.get("description"): text += f"\n[italic]{meta['description']}[/italic]"
        return Panel(Align.center(text, vertical="middle"), title="References", border_style="magenta")

    def resolve_path(self, data, path):
        """Helper to resolve nested paths like 'data.ghost.chosePath'"""
        if path.startswith("data."):
            path = path[5:]
        parts = path.split(".")
        curr = data
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return "None"
        return curr

    def get_state_panel(self):
        table = Table(show_header=False, box=None, padding=(0, 1))
        vars_dict = self.data.get("variables", {})
        updated_vars = vars_dict.get("__updated_vars", [])
        if not updated_vars: table.add_row("", "[dim]No variables updated yet.[/dim]")
        else:
            for var in reversed(updated_vars): 
                val = self.resolve_path(vars_dict, var)
                table.add_row(f"  {var}:", str(val))
        return Panel(table, title="Current State", border_style="green")

    def get_script_panel(self):
        curr_label = self.data.get("current_label", "")
        logical_index = self.data.get("line_index", 0)
        rel_path = self.label_map.get(curr_label)
        
        if not rel_path:
            return Panel(f"Script location for label '{curr_label}' not found.", title="Script Viewer", border_style="red")
        
        try:
            # We must use the absolute path relative to the engine's perspective
            full_path = os.path.join("games", self.game_id, "scripts", rel_path)
            with open(full_path, "r") as f: lines = f.readlines()
        except: 
            return Panel(f"Script file not found: {rel_path}", title="Script Viewer", border_style="red")
        
        label_file_idx = -1
        
        # 1. Find the label in the file
        for i, line in enumerate(lines):
            # Strict label match: 'label:' or 'label name:' at start of line
            if re.match(rf"^{curr_label}:\s*(?://.*)?$", line.strip()) or \
               re.match(rf"^label\s+{curr_label}:\s*(?://.*)?$", line.strip()):
                label_file_idx = i
                break
        
        target_file_idx = -1
        if label_file_idx != -1:
            # 2. Count logical lines (non-empty, non-comment) until we reach logical_index
            current_logical = 0
            # If logical_index is 0, we are on the label line itself or first command
            target_file_idx = label_file_idx 
            
            for i in range(label_file_idx + 1, len(lines)):
                stripped = lines[i].strip()
                if not stripped or stripped.startswith("//"): continue
                # If we hit another label, we went too far
                if re.match(r"^[\w_]+:\s*(?://.*)?$", lines[i].rstrip()) or \
                   re.match(r"^label\s+[\w_]+:\s*(?://.*)?$", lines[i].rstrip()):
                    break
                
                if current_logical == logical_index:
                    target_file_idx = i
                    break
                current_logical += 1

        h = self.console.height - 10
        display_idx = target_file_idx if target_file_idx != -1 else label_file_idx
        start = max(0, display_idx - (h // 2))
        end = min(len(lines), start + h)
        
        table = Table(show_header=False, box=None, padding=(0, 1), collapse_padding=True)
        table.add_column("num", justify="right", style="dim cyan", width=4); table.add_column("content")
        
        for i in range(start, end):
            content = process_spans(lines[i].rstrip())
            if i == target_file_idx:
                table.add_row(f"[bold cyan]{i+1}[/bold cyan]", Text(f"> {content}", style="bold white on grey15"))
            else:
                table.add_row(str(i+1), content)
        return Panel(table, title=f"Script Viewer", border_style="white", padding=(1, 1))

    def display_game(self) -> Layout:
        layout = Layout()
        if self.show_script:
            layout.split_row(Layout(name="main", ratio=7), Layout(name="script", ratio=3))
            main, script = layout["main"], layout["script"]
            script.update(self.get_script_panel())
        else: main = layout
        main.split_column(Layout(name="up", ratio=35), Layout(name="diag", ratio=35), Layout(name="low", ratio=30))
        main["up"].split_row(Layout(name="desc"), Layout(name="state"))
        main["up"]["desc"].update(self.get_descriptions_panel())
        main["up"]["state"].update(self.get_state_panel())
        log = self.data.get("dialogue_log") or []
        styles = ["[bold yellow]{char}[/bold yellow]: [bold white]{text}[/bold white]", "[dim yellow]{char}[/dim yellow]: [grey42]{text}[/grey42]", "[grey30]{char}: {text}[/grey30]", "[grey15]{char}: {text}[/grey15]", "[grey11]{char}: {text}[/grey11]", "[grey3]{char}: {text}[/grey3]"]
        lines = []
        
        # If there's active text (like a choice prompt), show it first (as the most recent)
        raw_text = self.data.get("text")
        active_text = process_spans(raw_text)
        
        display_log = list(log)
        # Avoid duplicating the last log entry if it's identical to active text
        if active_text and display_log and process_spans(display_log[-1]['text']) == active_text:
            display_log.pop()

        start_idx = 0
        if active_text:
            char = self.data.get("character") or "narrator"
            # If the text already has a colon in the first 20 chars (e.g. "Orb: Debatable"),
            # it's already attributed, so we don't add the prefix again.
            if ": " in active_text[:20]:
                lines.append(active_text)
            else:
                lines.append(styles[0].format(char=char.capitalize(), text=active_text))
            start_idx = 1

        for i in range(start_idx, min(len(display_log) + start_idx, 6)):
            entry = display_log[-(i+1-start_idx)]
            processed_text = process_spans(entry['text'])
            lines.insert(0, styles[i].format(char=entry['character'].capitalize(), text=processed_text))
        
        # Original padding logic
        box_h = int((self.console.height - 3) * 0.35) - 2
        pad = "\n" * max(0, box_h - sum(len(l.split("\n")) + 1 for l in lines) - 1)
        main["diag"].update(Panel(pad + "\n\n".join(lines), title="Dialogue", border_style="cyan"))
        
        footer_content = ""
        if self.data.get("type") == "missing_label": 
            target = self.data.get("meta", {}).get("target", "unknown")
            footer_content = f"[bold red]Label '{target}' is missing![/bold red]\n\n"
            # Interactive options for missing label
            ml_opts = ["Generate with AI", "Back (Undo)"]
            ml_lines = []
            for i, opt in enumerate(ml_opts):
                if self.focus == "choices" and i == self.choice_idx:
                    ml_lines.append(f"> [bold black on yellow] {opt} [/bold black on yellow]")
                else: ml_lines.append(f"  {opt}")
            footer_content += "\n".join(ml_lines)
        elif self.data.get("type") == "choice": 
            choices = self.get_choices_list()
            footer_content = f"[bold white]Select an option:[/bold white]\n\n" + choices
        elif self.data.get("type") == "end": 
            footer_content = f"\n[bold red]End of Script.[/bold red]"
        
        low_border = "yellow"
        if self.focus == "choices": low_border = "bold green"
        main["low"].split_column(Layout(Panel(footer_content, title="Input / Choice", border_style=low_border), ratio=70), Layout(Align.center(self.get_actions_row()), ratio=30))
        return layout

    def set_data(self, data: Dict[str, Any]):
        self.data = data
        if self.data.get("type") in ["choice", "missing_label"]:
            self.focus = "choices"
            self.choice_idx = 0
        else:
            self.focus = "actions"

    def run(self):
        step_delay = float(os.getenv("NARRAT_STEP_DELAY", "0.2"))
        if not self.data:
            res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": " "})
            self.set_data(res.json())
            
            # Initial auto-step check
            while self.data.get("type") in ["choice_confirmed", "clear"]:
                self.console.print(self.display_game())
                if step_delay > 0: time.sleep(step_delay)
                res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": " "})
                self.set_data(res.json())
        
        if os.getenv("NARRAT_TEST_MODE") == "1":
            while True:
                self.console.print(self.display_game())
                if self.data["type"] == "end": return
                res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": " "})
                self.set_data(res.json())
                if step_delay > 0: time.sleep(step_delay)
            return
        
        input_obj = create_input()
        with Live(self.display_game(), auto_refresh=False, screen=True) as live:
            with input_obj.raw_mode():
                while True:
                    # Auto-step logic for transitional states
                    if self.data.get("type") in ["choice_confirmed", "clear"]:
                        live.update(self.display_game()); live.refresh()
                        if step_delay > 0: time.sleep(step_delay)
                        res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": " "})
                        self.set_data(res.json())
                        continue

                    live.update(self.display_game()); live.refresh()
                    keys = input_obj.read_keys()
                    if not keys:
                        if os.getenv("NARRAT_TEST_MODE") != "1": time.sleep(0.05)
                        continue
                    
                    cmd = None
                    for key in keys:
                        if key.key == Keys.Tab:
                            if self.data.get("type") in ["choice", "missing_label"]: 
                                self.focus = "actions" if self.focus == "choices" else "choices"
                            else: self.focus = "actions"
                        elif key.key == Keys.Left:
                            if self.focus == "actions": self.action_idx = (self.action_idx - 1) % len(self.actions)
                        elif key.key == Keys.Right:
                            if self.focus == "actions": self.action_idx = (self.action_idx + 1) % len(self.actions)
                        elif key.key == Keys.Up:
                            if self.focus == "choices":
                                count = len(self.data.get("options", {})) if self.data.get("type") == "choice" else 2
                                if count: self.choice_idx = (self.choice_idx - 1) % count
                        elif key.key == Keys.Down:
                            if self.focus == "choices":
                                count = len(self.data.get("options", {})) if self.data.get("type") == "choice" else 2
                                if count: self.choice_idx = (self.choice_idx + 1) % count
                        elif key.key == Keys.Enter or key.key == Keys.ControlM:
                            if self.focus == "choices":
                                if self.data.get("type") == "choice":
                                    opt_keys = list(self.data.get("options", {}).keys())
                                    if opt_keys and self.choice_idx < len(opt_keys):
                                        cmd = opt_keys[self.choice_idx]
                                elif self.data.get("type") == "missing_label":
                                    # 0: Generate, 1: Back
                                    cmd = "AI_GENERATE" if self.choice_idx == 0 else "B"
                                self.focus, self.choice_idx = "actions", 0
                            else:
                                action = self.actions[self.action_idx]
                                if action == "Next": cmd = " "
                                elif action == "Back": cmd = "B"
                                elif action == "Reload Section": cmd = "R"
                                elif action == "Edit Assets": cmd = "DO_EDIT"
                                elif action == "Edit Script": cmd = "EDIT_SCRIPT"
                                elif action == "View Script": self.show_script = not self.show_script
                                elif action == "Exit Game": return
                        elif key.key == Keys.Escape or key.key == Keys.ControlC: return
                    
                    if cmd:
                        if cmd == "DO_EDIT" or cmd == "EDIT_SCRIPT":
                            live.stop()
                            if cmd == "EDIT_SCRIPT":
                                # Find current line index in file for external editor
                                curr_label, l_idx = self.data.get("current_label"), self.data.get("line_index", 0)
                                rel_path = self.label_map.get(curr_label)
                                
                                if not rel_path:
                                    console.print(f"[red]Could not find script file for label '{curr_label}'[/red]")
                                    time.sleep(2); live.start(); continue

                                full_p = os.path.join("games", self.game_id, "scripts", rel_path)
                                
                                with open(full_p, "r") as f: lines = f.readlines()
                                file_idx = -1
                                for i, line in enumerate(lines):
                                    if re.match(rf"^(?:label\s+)?{curr_label}:", line.strip()):
                                        file_idx = i; break
                                if file_idx != -1:
                                    count = 0
                                    for i in range(file_idx + 1, len(lines)):
                                        if not lines[i].strip() or lines[i].strip().startswith("//"): continue
                                        if re.match(r"^[\w_]+:", lines[i].strip()): break
                                        if count == l_idx: file_idx = i; break
                                        count += 1
                                open_in_external_editor(full_p, file_idx + 1)
                            else:
                                self.handle_edit()
                            live.start()
                            res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": "B_REPROCESS"})
                            self.set_data(res.json())
                        elif cmd == "AI_GENERATE":
                            live.stop()
                            with console.status("AI is generating missing content..."):
                                requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/generate", json={"target": self.data["meta"]["target"]})
                            # Use B_REPROCESS to reload the script and stay on the current label (which now exists)
                            res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": "B_REPROCESS"})
                            self.set_data(res.json()); live.start()
                        else:
                            res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": str(cmd)})
                            self.set_data(res.json())
                            
                            # Only sleep for 'Next' command if we hit a content state.
                            # Choice selections (numeric cmd) are handled by the auto-step logic below to avoid double-sleeping.
                            # Utility commands like Reload (R) or Back (B) should be instant.
                            if cmd == " " and step_delay > 0:
                                if self.data.get("type") in ["talk", "choice", "end"]:
                                    time.sleep(step_delay)
                            
                            if cmd == "R": self.action_idx = 0
                            
                            if self.data.get("type") == "end":
                                live.stop()
                                c = questionary.select("End of Script.", choices=["Generate More", "Restart", "Exit"]).ask()
                                if c == "Generate More":
                                    requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/continue")
                                    res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": " "})
                                    self.set_data(res.json())
                                    if step_delay > 0: time.sleep(step_delay)
                                    live.start()
                                elif c == "Restart":
                                    res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": "R"})
                                    self.set_data(res.json())
                                    if step_delay > 0: time.sleep(step_delay)
                                    live.start()
                                else: return

    def handle_edit(self):
        curr_label, l_idx = self.data.get("current_label"), self.data.get("line_index", 0)
        rel_path = self.label_map.get(curr_label)
        if not rel_path:
            self.console.print(f"[red]Could not find script file for label '{curr_label}'[/red]")
            time.sleep(2); return

        full_p = os.path.join("games", self.game_id, "scripts", rel_path)
        
        with open(full_p, "r") as f: lines = f.readlines()
        idx = -1
        for i, line in enumerate(lines):
            if re.match(rf"^(?:label\s+)?{curr_label}:\s*(?://.*)?$", line.strip()):
                idx = i; break
        if idx != -1:
            count = 0
            for i in range(idx + 1, len(lines)):
                if not lines[i].strip() or lines[i].strip().startswith("//"): continue
                if re.match(r"^[\w_]+:", lines[i].strip()): break
                if count == l_idx: idx = i; break
                count += 1
        
        et = questionary.select("What to edit?", choices=["Dialogue", "Background", "Character", "Scene", "Back"]).ask()
        if et == "Back" or et is None: return

        if et == "Dialogue":
            action = questionary.select("Action", choices=["Edit Manually", "Edit in External Editor", "Rewrite with AI", "Back"]).ask()
            if action == "Edit Manually":
                nt = questionary.text("New Text").ask()
                if nt: requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/edit", json={
                    "category": "script", "action": "update", "target": str(idx), 
                    "content": f"talk {self.data.get('character', 'narrator')} \"{nt}\"",
                    "meta": {"path": rel_path}
                })
            elif action == "Edit in External Editor":
                from src.terminal_client.utils import edit_text_in_external_editor
                initial_text = self.data.get('text', '')
                nt = edit_text_in_external_editor(initial_text)
                if nt: requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/edit", json={
                    "category": "script", "action": "update", "target": str(idx), 
                    "content": f"talk {self.data.get('character', 'narrator')} \"{nt}\"",
                    "meta": {"path": rel_path}
                })
            elif action == "Rewrite with AI":
                instr = questionary.text("Instruction?").ask()
                if instr:
                    with console.status("AI is rewriting..."):
                        res = requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/edit/ai", json={
                            "target": str(idx), "content": instr,
                            "meta": {"path": rel_path}
                        })
                    if res.status_code == 200: questionary.press_any_key_to_continue().ask()
        
        elif et == "Background":
            bg = self.data.get("background", "None")
            if bg == "None": return
            res = requests.get(f"{self.base_url}/games/{self.game_id}/assets/backgrounds/{bg}")
            cur = res.json().get("content", "")
            method = questionary.select("Edit Method", choices=["Inline", "External Editor", "Back"]).ask()
            if method == "External Editor":
                from src.terminal_client.utils import edit_text_in_external_editor
                nv = edit_text_in_external_editor(cur)
            elif method == "Inline":
                nv = questionary.text("Description", default=cur).ask()
            else: nv = None
            if nv is not None:
                requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "background", "target": bg, "content": nv})

        elif et == "Character":
            char = self.data.get("character")
            if not char: return
            ctype = questionary.select("Edit what?", choices=["Profile", "Description", "Back"]).ask()
            if ctype == "Back" or ctype is None: return
            res = requests.get(f"{self.base_url}/games/{self.game_id}/assets/characters/{char}", params={"type": ctype.lower()})
            cur = res.json().get("content", "")
            method = questionary.select("Edit Method", choices=["Inline", "External Editor", "Back"]).ask()
            if method == "External Editor":
                from src.terminal_client.utils import edit_text_in_external_editor
                nv = edit_text_in_external_editor(cur)
            elif method == "Inline":
                nv = questionary.text(ctype, default=cur).ask()
            else: nv = None
            if nv is not None:
                requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "character", "target": char, "content": nv, "meta": {"type": ctype.lower()}})

        elif et == "Scene":
            sc = self.data.get("variables", {}).get("__current_scene")
            if not sc: return
            res = requests.get(f"{self.base_url}/games/{self.game_id}/assets/scenes/{sc}")
            cur = res.json().get("content", "")
            nv = questionary.text("Scene Description", default=cur).ask()
            if nv:
                requests.post(f"{self.base_url}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "scene", "target": sc, "content": nv})
        # Other edit types omitted for brevity in this fix...
