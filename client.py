import sys
import requests
import os
import json
import time
import subprocess
import re
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.align import Align

console = Console()
BASE_URL = "http://localhost:8045"

def ensure_server_running():
    """Checks if server is up, starts it if not."""
    try:
        requests.get(f"{BASE_URL}/games", timeout=0.5)
        return None # Already running
    except:
        # Start server using the same python interpreter
        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid # Ensure it gets its own process group for clean killing
        )
        # Wait for startup
        for _ in range(15):
            try:
                requests.get(f"{BASE_URL}/games", timeout=0.5)
                return proc
            except:
                time.sleep(0.5)
        return proc

# --- LAUNCHER UI ---
# --- LAUNCHER UI ---

class Launcher:
    def __init__(self):
        self.show_script = True

    def make_intro_layout(self) -> Layout:
        layout = Layout()
        layout.split_row(
            Layout(name="left", ratio=7),
            Layout(name="right", ratio=3)
        )
        return layout

    def display_intro(self):
        layout = self.make_intro_layout()
        
        logo = r"""
[bold cyan]
  _   _   _   ____    ____       _      _____               _ 
 | \ | | / \ |  _ \  |  _ \     / \    |_   _|  __ _  _ __ (_)
 |  \| |/ _ \| |_) | | |_) |   / _ \     | |   / _` || '_ \| |
 | |\  / ___ \  _ <  |  _ <   / ___ \    | |  | (_| || |_) | |
 |_| \/_/   \_\_| \_\ |_| \_\ /_/   \_\   |_|   \__,_|| .__/|_|
                                                      |_|     
[/bold cyan]
        """
        description = """
[bold white]Welcome to NARRATapi[/bold white]

A CLI-based development environment for writing and playing visual novels. 
Experience immersive storytelling, dynamic AI generation, and real-time script editing.

[dim]Version 1.2.0[/dim]
        """
        
        layout["left"].update(Panel(Align.center(logo + description, vertical="middle"), border_style="cyan"))
        
        options = "[bold yellow]Use Arrow Keys to Navigate[/bold yellow]\n\nSelect an option from the menu below."
        layout["right"].update(Panel(Align.center(options, vertical="middle"), title="Menu", border_style="yellow"))
        
        console.clear()
        console.print(layout, height=console.height - 2)

    def run(self):
        while True:
            self.display_intro()
            choice = questionary.select(
                "Main Menu",
                choices=[
                    "Create Game",
                    "Select Game",
                    "Options",
                    "Exit"
                ],
                style=questionary.Style([
                    ('selected', 'fg:yellow bold'),
                ])
            ).ask()
            
            if choice == "Exit" or choice is None:
                console.print("[red]Exiting...[/red]")
                sys.exit()
            elif choice == "Create Game":
                self.create_game_flow()
            elif choice == "Select Game":
                self.select_game_flow()
            elif choice == "Options":
                self.global_options_flow()

    def global_options_flow(self):
        while True:
            res = requests.get(f"{BASE_URL}/config")
            config = res.json()
            console.clear()
            table = Table(title="Global Options")
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="bold white")
            table.add_row("Prompt Prefix", config.get("global_prompt_prefix", "None"))
            console.print(table)
            
            choice = questionary.select(
                "Options",
                choices=["Edit Prompt Prefix", "Back"]
            ).ask()
            
            if choice == "Back" or choice is None: break
            
            if choice == "Edit Prompt Prefix":
                new_prefix = Prompt.ask("Enter new global prompt prefix", default=config.get("global_prompt_prefix", ""))
                requests.post(f"{BASE_URL}/config", json={"global_prompt_prefix": new_prefix})

    def create_game_flow(self):
        console.clear()
        console.print(Panel("[bold yellow]Create New Game[/bold yellow]", border_style="yellow"))
        
        method = questionary.select(
            "Choose Creation Method",
            choices=[
                "AI Assisted",
                "Manual",
                "Back"
            ]
        ).ask()
        
        if method == "Back" or method is None: return

        game_id = Prompt.ask("Enter unique Game ID (no spaces)")
        if not game_id: return
        
        if method == "AI Assisted":
            console.print("\n[bold cyan]AI Guidance:[/bold cyan]")
            console.print("Describe your game idea. Include [italic]Genre, Setting, Characters, and Plot hooks.[/italic]")
            prompt = Prompt.ask("\n[bold green]Enter your prompt[/bold green]")
            
            while True:
                with console.status("[bold green]AI is scaffolding your game...[/bold green]"):
                    res = requests.post(f"{BASE_URL}/games/create", json={"name": game_id, "prompt": prompt})
                
                if res.status_code == 200:
                    console.print(f"[green]Game '{game_id}' created successfully![/green]")
                    self.game_hub(game_id)
                    return
                else:
                    error_detail = res.json().get('detail', 'Unknown error')
                    console.print(Panel(f"[red]Error:[/red] {error_detail}", title="Generation Failed", border_style="red"))
                    
                    action = questionary.select(
                        "What would you like to do?",
                        choices=["Retry same prompt", "Edit prompt", "Back to menu"]
                    ).ask()
                    
                    if action == "Back to menu" or action is None: return
                    if action == "Edit prompt":
                        prompt = Prompt.ask("\n[bold green]Enter new prompt[/bold green]")
        else:
            title = Prompt.ask("Game Title")
            summary = Prompt.ask("Game Summary")
            res = requests.post(f"{BASE_URL}/games/create", json={"name": game_id, "manual_data": {"title": title, "summary": summary, "genre": "Custom"}})
            if res.status_code == 200:
                console.print(f"[green]Game '{game_id}' created successfully![/green]")
                self.game_hub(game_id)
            else:
                console.print(f"[red]Error: {res.json().get('detail', 'Unknown error')}[/red]")
                Prompt.ask("[Enter] to continue")

    def select_game_flow(self):
        res = requests.get(f"{BASE_URL}/games")
        games = res.json()["games"]
        
        if not games:
            console.print("[yellow]No games found. Create one first![/yellow]")
            Prompt.ask("[Enter] to continue")
            return

        table = Table(title="Available Games")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="bold white")
        table.add_column("Summary", style="dim")
        
        for g in games:
            table.add_row(g["id"], g["title"], g["summary"][:50] + "...")
        
        console.clear()
        console.print(table)
        
        game_ids = [g["id"] for g in games]
        choice = questionary.select(
            "Select Game ID",
            choices=game_ids + [questionary.Separator(), "Back"]
        ).ask()
        
        if choice == "Back" or choice is None: return
        
        self.game_hub(choice)

    def game_hub(self, game_id):
        while True:
            res = requests.get(f"{BASE_URL}/games/{game_id}/metadata")
            meta = res.json()
            
            layout = self.make_intro_layout()
            info = f"[bold cyan]{meta['title']}[/bold cyan]\n\n{meta['summary']}\n\n[dim]Genre: {meta['genre']}[/dim]\n[dim]Characters: {', '.join(meta['characters'])}[/dim]"
            if meta.get("plot_outline"):
                info += f"\n\n[bold white]Plot Outline:[/bold white]\n{meta['plot_outline'][:200]}..."
            
            layout["left"].update(Panel(Align.center(info, vertical="middle"), border_style="cyan"))
            
            options = "[bold yellow]Use Arrow Keys to Navigate[/bold yellow]\n\nManage your session or game assets."
            layout["right"].update(Panel(Align.center(options, vertical="middle"), title="Game Hub", border_style="yellow"))
            
            console.clear()
            console.print(layout, height=console.height - 2)
            
            choice = questionary.select(
                f"Game Hub: {game_id}",
                choices=[
                    "Start New Game",
                    "Load Game",
                    "Manage Assets",
                    "Edit Options",
                    "Back"
                ]
            ).ask()
            
            if choice == "Back" or choice is None: return
            
            if choice == "Start New Game":
                session_id = Prompt.ask("Enter new session name", default="autosave")
                engine = GameEngine(game_id, session_id)
                engine.run()
            elif choice == "Load Game":
                # List saves (Simplified for now)
                engine = GameEngine(game_id, "autosave")
                engine.run()
            elif choice == "Manage Assets":
                self.asset_manager_flow(game_id, meta)
            elif choice == "Edit Options":
                self.edit_metadata_flow(game_id, meta)

    def asset_manager_flow(self, game_id, meta):
        while True:
            console.clear()
            console.print(Panel(f"[bold yellow]Asset Manager: {meta['title']}[/bold yellow]", border_style="yellow"))
            
            category_choice = questionary.select(
                "Select Category",
                choices=[
                    "Backgrounds",
                    "Characters",
                    "Scenes",
                    "Back"
                ]
            ).ask()
            
            if category_choice == "Back" or category_choice is None: break
            category = category_choice.lower()
            
            while True:
                res = requests.get(f"{BASE_URL}/games/{game_id}/assets/{category}")
                assets = res.json()["assets"]
                
                table = Table(title=f"Manage {category.capitalize()}")
                table.add_column("ID", style="cyan")
                for a in assets: table.add_row(a)
                console.clear()
                console.print(table)
                
                asset_id = questionary.select(
                    f"Select {category[:-1].capitalize()}",
                    choices=assets + [questionary.Separator(), "Add New", "Back"]
                ).ask()
                
                if asset_id == "Back" or asset_id is None: break
                
                if asset_id == "Add New":
                    asset_id = Prompt.ask("Enter unique ID for new asset")
                    if not asset_id: continue
                
                # Sub-menu for specific asset
                while True:
                    console.clear()
                    console.print(Panel(f"[bold cyan]Editing {category[:-1].capitalize()}: {asset_id}[/bold cyan]"))
                    
                    action = questionary.select(
                        "Action",
                        choices=[
                            "Rename Globally",
                            "Edit Description",
                            "AI Generate Description",
                            "Back"
                        ]
                    ).ask()
                    
                    if action == "Back" or action is None: break
                    
                    if action == "Rename Globally":
                        new_id = Prompt.ask(f"Enter new ID for {asset_id}")
                        if new_id:
                            with console.status(f"Refactoring {asset_id} -> {new_id}..."):
                                res = requests.post(f"{BASE_URL}/games/{game_id}/assets/rename", json={"category": category, "old_id": asset_id, "new_id": new_id})
                            if res.status_code == 200:
                                console.print("[green]Success![/green]")
                                asset_id = new_id
                                break # Back to asset list
                    elif action == "Edit Description":
                        nd = Prompt.ask("Enter new description")
                        requests.post(f"{BASE_URL}/games/{game_id}/sessions/any/edit", json={"category": "reference", "action": "update", "sub_category": category[:-1], "target": asset_id, "content": nd})
                    elif action == "AI Generate Description":
                        with console.status("AI is generating..."):
                            requests.post(f"{BASE_URL}/games/{game_id}/assets/generate", json={"category": category, "target": asset_id})
                        console.print("[green]AI generation complete![/green]")
                    Prompt.ask("[Enter] to continue")

    def edit_metadata_flow(self, game_id, meta):
        while True:
            console.clear()
            table = Table(title=f"Edit Options: {meta['title']}")
            table.add_column("Option", style="cyan")
            table.add_column("Field", style="bold")
            table.add_column("Current Value", style="dim")
            table.add_row("1", "Title", meta["title"])
            table.add_row("2", "Summary", meta["summary"][:50] + "...")
            table.add_row("3", "Genre", meta["genre"])
            table.add_row("4", "Plot Outline", (meta.get("plot_outline") or "N/A")[:50] + "...")
            table.add_row("5", "Prompt Prefix", (meta.get("prompt_prefix") or "None")[:50] + "...")
            console.print(table)
            
            choice = questionary.select(
                "Edit Metadata",
                choices=[
                    "Title",
                    "Summary",
                    "Genre",
                    "Plot Outline",
                    "Prompt Prefix",
                    "Regenerate All with AI",
                    "Back"
                ]
            ).ask()
            
            if choice == "Back" or choice is None: break
            
            if choice == "Regenerate All with AI":
                prompt = Prompt.ask("Enter prompt for regeneration (or leave blank to use existing)")
                with console.status("[bold green]Regenerating metadata...[/bold green]"):
                    res = requests.post(f"{BASE_URL}/games/{game_id}/regenerate", json={"name": game_id, "prompt": prompt or meta['summary']})
                if res.status_code == 200:
                    console.print("[green]Metadata regenerated![/green]")
                    meta = res.json()["metadata"]
                else:
                    console.print(f"[red]Regeneration failed: {res.json().get('detail')}[/red]")
                Prompt.ask("[Enter] to continue")
                continue

            field_map = {
                "Title": "title",
                "Summary": "summary",
                "Genre": "genre",
                "Plot Outline": "plot_outline",
                "Prompt Prefix": "prompt_prefix"
            }
            field = field_map[choice]
            new_val = Prompt.ask(f"Enter new {field}", default=meta.get(field, ""))
            
            res = requests.post(f"{BASE_URL}/games/{game_id}/sessions/any/edit", json={
                "category": "metadata",
                "action": "update",
                "target": field,
                "content": new_val
            })
            if res.status_code == 200:
                meta[field] = new_val
                console.print("[green]Metadata updated![/green]")
            else:
                console.print("[red]Update failed.[/red]")
            Prompt.ask("[Enter] to continue")

# --- GAME ENGINE ---

class GameEngine:
    def __init__(self, game_id, session_id):
        self.game_id = game_id
        self.session_id = session_id
        self.show_script = True
        self.data = {}

    def get_descriptions_panel(self):
        anim = self.data.get("active_animation")
        scene = self.data.get("active_scene")
        if anim: return Panel(f"[bold magenta]ANIMATION: {anim['name']}[/bold magenta]\n\n{anim['content']}", title="Active Animation", border_style="magenta")
        if scene: return Panel(f"[bold green]SCENE: {scene['name']}[/bold green]\n\n{scene['content']}", title="Active Scene", border_style="green")
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[bold cyan]BG:[/bold cyan]", f"[italic]{self.data.get('background', 'None')}[/italic]")
        table.add_row("", f"[dim]{self.data.get('background_desc', 'No description.')}[/dim]")
        if self.data.get("character"):
            char, meta = self.data["character"], self.data.get("meta", {})
            table.add_row("[bold yellow]CHAR:[/bold yellow]", f"[bold]{char}[/bold] [italic]({meta.get('emotion', 'Neutral')})[/italic]")
            table.add_row("", f"[dim]{meta.get('description', 'No description.')}[/dim]")
        return Panel(table, title="Descriptions", border_style="blue")

    def get_state_panel(self):
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[bold green]Label:[/bold green]", self.data.get("current_label", "Unknown"))
        vars_dict = self.data.get("variables", {})
        updated_vars = vars_dict.get("__updated_vars", [])
        table.add_row("", "")
        table.add_row("[bold]Recent Variables:[/bold]", "")
        if not updated_vars: table.add_row("", "[dim]No variables updated yet.[/dim]")
        else:
            for var in reversed(updated_vars): table.add_row(f"  {var}:", str(vars_dict.get(var)))
        return Panel(table, title="Current State", border_style="green")

    def get_script_panel(self):
        try:
            with open(f"games/{self.game_id}/phase1.narrat", "r") as f: lines = f.readlines()
        except: return Panel("Script file not found.", title="Script Viewer", border_style="red")
        
        curr_label = self.data.get("current_label", "")
        logical_index = self.data.get("line_index", 0)
        target_line_idx = -1
        
        # 1. Find the label line
        label_file_idx = -1
        for i, line in enumerate(lines):
            if re.match(rf"^(?:label\s+)?{curr_label}:\s*(?://.*)?$", line.strip()):
                label_file_idx = i
                break
        
        if label_file_idx != -1:
            # 2. Match the logical index to physical lines, skipping blanks/comments
            current_logical = 0
            target_line_idx = label_file_idx # Default to label if index is 0
            
            for i in range(label_file_idx + 1, len(lines)):
                if current_logical >= logical_index:
                    break
                
                stripped = lines[i].strip()
                if not stripped or stripped.startswith("//"):
                    continue # Skip whitespace/comments
                
                # If we hit another label, we've gone too far (shouldn't happen with valid index)
                if re.match(r"^(?:label\s+)?[\w_]+:\s*(?://.*)?$", stripped):
                    break
                    
                target_line_idx = i
                current_logical += 1
        
        # 3. Calculate display range (Centered)
        h = console.height - 10 # Allow room for title and padding
        half_h = h // 2
        
        display_idx = target_line_idx if target_line_idx != -1 else label_file_idx
        
        start = max(0, display_idx - half_h)
        end = min(len(lines), start + h)
        
        # Adjust start if we hit the end of the file
        if end == len(lines):
            start = max(0, end - h)
        
        table = Table(show_header=False, box=None, padding=(0, 1), collapse_padding=True)
        table.add_column("num", justify="right", style="dim cyan", width=4)
        table.add_column("content")
        
        for i in range(start, end):
            # Highlight the line we are currently on
            if i == target_line_idx:
                table.add_row(f"[bold cyan]{i+1}[/bold cyan]", Text(f"> {lines[i].rstrip()}", style="bold white on grey15"))
            elif i == label_file_idx and target_line_idx == label_file_idx: # Special highlight for label if index 0
                table.add_row(f"[bold cyan]{i+1}[/bold cyan]", Text(f"> {lines[i].rstrip()}", style="bold yellow on grey15"))
            else:
                table.add_row(str(i+1), lines[i].rstrip())
        
        return Panel(table, title=f"Script: {self.game_id}/phase1.narrat", border_style="white", padding=(1, 1))

    def display_game(self):
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
        for i in range(min(len(log), 6)):
            entry = log[-(i+1)]
            lines.insert(0, styles[i].format(char=entry['character'], text=entry['text']))
        box_h = int((console.height - 3) * 0.35) - 2
        pad = "\n" * max(0, box_h - sum(len(l.split("\n")) + 1 for l in lines) - 1)
        main["diag"].update(Panel(pad + "\n\n".join(lines), title="Dialogue", border_style="cyan"))

        sys_msg = ""
        if self.data["type"] == "missing_label": sys_msg = f"\n[bold red]System: Label '{self.data['meta']['target']}' is missing![/bold red]"
        elif self.data["type"] == "choice":
            sys_msg = "\n" + "\n".join(f"  {i}. {o['text']}" for i, o in self.data["options"].items())
        elif self.data["type"] == "end": sys_msg = f"\n[bold red]{self.data['text']}[/bold red]"
        main["low"].update(Panel(sys_msg, title="System / Choices", border_style="yellow"))
        
        console.clear()
        console.print("\n")
        console.print(layout, height=console.height - 3)

    def handle_edit(self):
        p = f"games/{self.game_id}/phase1.narrat"
        with open(p, "r") as f: lines = f.readlines()
        idx = -1
        for i, line in enumerate(lines):
            if re.match(rf"^(?:label\s+)?{self.data['current_label']}:\s*(?://.*)?$", line.strip()):
                idx = i + self.data.get("line_index", 0)
                break
        if idx == -1: return
        
        edit_type = questionary.select(
            "What would you like to edit?",
            choices=[
                "Background",
                "Character",
                "Dialogue",
                "Choice",
                "Scene",
                "Back"
            ]
        ).ask()
        
        if edit_type == "Back" or edit_type is None: return
        
        if edit_type == "Background":
            p = questionary.select("Background Edit", choices=["Change ID", "Edit Description", "Back"]).ask()
            if p == "Change ID":
                opt = questionary.select("Method", choices=["Choose Existing", "Add New", "Back"]).ask()
                if opt == "Choose Existing":
                    assets = requests.get(f"{BASE_URL}/games/{self.game_id}/assets/backgrounds").json()["assets"]
                    c = questionary.select("Select Background", choices=assets + ["Back"]).ask()
                    if c != "Back" and c is not None: 
                        requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "script", "action": "update", "target": str(idx), "content": f"background {c}"})
            elif p == "Edit Description":
                bg = self.data.get("background", "None")
                nd = Prompt.ask(f"  New Desc for {bg} (or [G]enerate with AI)", default="G")
                if nd.upper() == "G":
                    with console.status(f"[bold green]AI is describing {bg}...[/bold green]"):
                        res = requests.post(f"{BASE_URL}/games/{self.game_id}/assets/generate", json={"category": "backgrounds", "target": bg})
                    if res.status_code == 200:
                        console.print(f"[green]AI described {bg}![/green]")
                    else:
                        console.print(f"[red]Generation failed: {res.json().get('detail')}[/red]")
                        Prompt.ask("[Enter] to continue")
                else:
                    requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "background", "target": bg, "content": nd})
        elif edit_type == "Character":
            char = self.data.get("character")
            if not char:
                console.print("[red]No character active.[/red]")
                Prompt.ask("[Enter] to continue")
                return
            p = questionary.select(
                f"Character Edit: {char}",
                choices=["Edit Description", "Edit Profile", "AI Generate All", "Rename Globally", "Back"]
            ).ask()
            
            if p == "AI Generate All":
                with console.status(f"[bold green]AI is describing {char}...[/bold green]"):
                    requests.post(f"{BASE_URL}/games/{self.game_id}/assets/generate", json={"category": "characters", "target": char, "sub_type": "description"})
                    requests.post(f"{BASE_URL}/games/{self.game_id}/assets/generate", json={"category": "characters", "target": char, "sub_type": "profile"})
                console.print(f"[green]AI described {char}![/green]")
            elif p == "Rename Globally":
                new_name = Prompt.ask(f"Enter new global ID for {char} (no spaces)")
                if new_name:
                    with console.status(f"[bold yellow]Refactoring {char} to {new_name}...[/bold yellow]"):
                        res = requests.post(f"{BASE_URL}/games/{self.game_id}/characters/rename", json={"old_id": char, "new_id": new_name})
                    if res.status_code == 200:
                        console.print(f"[green]Successfully renamed {char} to {new_name} across all files![/green]")
                        self.data["character"] = new_name
                    else:
                        console.print(f"[red]Rename failed: {res.json().get('detail')}[/red]")
                Prompt.ask("[Enter] to continue")
            elif p == "Edit Description":
                nd = Prompt.ask(f"  New description for {char}")
                requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "character", "target": char, "content": nd, "meta": {"type": "description"}})
            elif p == "Edit Profile":
                nd = Prompt.ask(f"  New profile for {char}")
                requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "character", "target": char, "content": nd, "meta": {"type": "profile"}})
        elif edit_type == "Dialogue":
            new_text = Prompt.ask("  New Text")
            if new_text:
                requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "script", "action": "update", "target": str(idx), "content": f"talk {self.data.get('character', 'narrator')} \"{new_text}\""})

    def run(self):
        res = requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": "R"})
        self.data = res.json()
        while True:
            self.display_game()
            
            if self.data["type"] == "end":
                choice = questionary.select(
                    "End of Script.",
                    choices=["Generate More", "Restart", "Exit"]
                ).ask()
                
                if choice == "Generate More":
                    with console.status("[bold green]AI is writing more...[/bold green]"):
                        res = requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/continue")
                    if res.status_code == 200:
                        res = requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": " "})
                        self.data = res.json()
                        continue
                    else:
                        console.print(f"[red]Error: {res.json().get('detail')}[/red]")
                        Prompt.ask("[Enter] to continue")
                        continue
                elif choice == "Restart":
                    res = requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": "R"})
                    self.data = res.json()
                    continue
                else:
                    break

            if self.data["type"] == "missing_label":
                choice = questionary.select(
                    f"Label '{self.data['meta']['target']}' is missing!",
                    choices=["Generate with AI", "Back (Undo)"]
                ).ask()
                
                if choice == "Generate with AI":
                    with console.status("Generating..."): requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/generate", json={"target": self.data["meta"]["target"]})
                    cmd = "R"
                else: cmd = "B"
            elif self.data["type"] == "choice":
                options = [f"{i}. {o['text']}" for i, o in self.data["options"].items()]
                choice_text = questionary.select(
                    "Make a Choice",
                    choices=options + [questionary.Separator(), "View Script", "Reload", "Back", "Edit", "Exit"]
                ).ask()
                
                if choice_text is None: break
                
                if choice_text == "View Script": cmd = "V"
                elif choice_text == "Reload": cmd = "R"
                elif choice_text == "Back": cmd = "B"
                elif choice_text == "Edit": cmd = "E"
                elif choice_text == "Exit": break
                else:
                    # Extract index from "1. Text"
                    cmd = choice_text.split(".")[0]
            else:
                cmd = questionary.select(
                    "Action",
                    choices=["Next", "View Script", "Reload", "Back", "Edit", "Exit"],
                    use_shortcuts=True
                ).ask()
                
                if cmd is None or cmd == "Exit": break
                if cmd == "Next": cmd = " "
                elif cmd == "View Script": cmd = "V"
                elif cmd == "Reload": cmd = "R"
                elif cmd == "Back": cmd = "B"
                elif cmd == "Edit": cmd = "E"
            
            if cmd.upper() == "V": self.show_script = not self.show_script; continue
            if cmd.upper() == "E": self.handle_edit(); cmd = "REFRESH"
            
            res = requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": cmd.upper() if cmd else " "})
            self.data = res.json()

# --- MAIN ---

def main():
    server_proc = ensure_server_running()
    
    try:
        if len(sys.argv) > 1:
            game_id = sys.argv[1]
            session_id = sys.argv[2] if len(sys.argv) > 2 else "autosave"
            engine = GameEngine(game_id, session_id)
            engine.run()
        else:
            launcher = Launcher()
            launcher.run()
    finally:
        if server_proc:
            console.print("[dim]Shutting down background server...[/dim]")
            import signal
            os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)

if __name__ == "__main__":
    main()
