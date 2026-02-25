import sys
import requests
import os
import json
import time
import subprocess
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
        
        logo = """
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

[dim]Version 1.0.0[/dim]
        """
        
        layout["left"].update(Panel(Align.center(logo + description, vertical="middle"), border_style="cyan"))
        
        options = "[1] Create Game\n[2] Select Game\n[X] Exit"
        layout["right"].update(Panel(Align.center(options, vertical="middle"), title="Menu", border_style="yellow"))
        
        console.clear()
        console.print(layout, height=console.height - 2)

    def run(self):
        while True:
            self.display_intro()
            choice = Prompt.ask("\n[bold green]Select Option[/bold green]", choices=["1", "2", "X", "x"])
            
            if choice.upper() == "X":
                console.print("[red]Exiting...[/red]")
                sys.exit()
            elif choice == "1":
                self.create_game_flow()
            elif choice == "2":
                self.select_game_flow()

    def create_game_flow(self):
        console.clear()
        console.print(Panel("[bold yellow]Create New Game[/bold yellow]", border_style="yellow"))
        method = Prompt.ask("Method: [1] AI Assisted | [2] Manual | [B]ack", choices=["1", "2", "B", "b"])
        if method.upper() == "B": return

        game_id = Prompt.ask("Enter unique Game ID (no spaces)")
        
        if method == "1":
            console.print("\n[bold cyan]AI Guidance:[/bold cyan]")
            console.print("Describe your game idea. Include [italic]Genre, Setting, Characters, and Plot hooks.[/italic]")
            console.print("Example: [dim]A dark fantasy world where magic is illegal. You play as a rogue alchemist trying to save their sibling from the Inquisitors.[/dim]")
            prompt = Prompt.ask("\n[bold green]Enter your prompt[/bold green]")
            with console.status("[bold green]AI is scaffolding your game...[/bold green]"):
                res = requests.post(f"{BASE_URL}/games/create", json={"name": game_id, "prompt": prompt})
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
        table.add_column("Summary", dim=True)
        
        for g in games:
            table.add_row(g["id"], g["title"], g["summary"][:50] + "...")
        
        console.clear()
        console.print(table)
        
        game_ids = [g["id"] for g in games]
        choice = Prompt.ask("\nSelect Game ID or [B]ack", choices=game_ids + ["B", "b"])
        if choice.upper() == "B": return
        
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
            
            options = "[1] Start New Game\n[2] Load Game\n[3] Edit Metadata\n[B]ack"
            layout["right"].update(Panel(Align.center(options, vertical="middle"), title="Game Hub", border_style="yellow"))
            
            console.clear()
            console.print(layout, height=console.height - 2)
            
            choice = Prompt.ask("\n[bold green]Select Option[/bold green]", choices=["1", "2", "3", "B", "b"])
            if choice.upper() == "B": return
            
            if choice == "1":
                session_id = Prompt.ask("Enter new session name", default="autosave")
                engine = GameEngine(game_id, session_id)
                engine.run()
            elif choice == "2":
                # List saves (Simplified for now)
                engine = GameEngine(game_id, "autosave")
                engine.run()
            elif choice == "3":
                self.edit_metadata_flow(game_id, meta)

    def edit_metadata_flow(self, game_id, meta):
        while True:
            console.clear()
            table = Table(title=f"Edit Metadata: {meta['title']}")
            table.add_column("Option", style="cyan")
            table.add_column("Field", style="bold")
            table.add_column("Current Value", dim=True)
            table.add_row("1", "Title", meta["title"])
            table.add_row("2", "Summary", meta["summary"][:50] + "...")
            table.add_row("3", "Genre", meta["genre"])
            table.add_row("4", "Plot Outline", (meta.get("plot_outline") or "N/A")[:50] + "...")
            console.print(table)
            
            choice = Prompt.ask("\nSelect field to edit, [R]egenerate All, or [B]ack", choices=["1", "2", "3", "4", "R", "r", "B", "b"])
            if choice.upper() == "B": break
            
            if choice.upper() == "R":
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

            fields = {"1": "title", "2": "summary", "3": "genre", "4": "plot_outline"}
            field = fields[choice]
            new_val = Prompt.ask(f"Enter new {field}")
            
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
        curr_label, target_line_idx = self.data.get("current_label", ""), -1
        for i, line in enumerate(lines):
            if line.strip().startswith(f"label {curr_label}:"):
                target_line_idx = i + self.data.get("line_index", 0)
                break
        h = console.height - 8
        start, end = max(0, target_line_idx - (h // 2)), min(len(lines), target_line_idx + h // 2)
        table = Table(show_header=False, box=None, padding=(0, 1), collapse_padding=True)
        table.add_column("num", justify="right", style="dim cyan", width=4)
        table.add_column("content")
        for i in range(start, end):
            if i == target_line_idx: table.add_row(f"[bold cyan]{i+1}[/bold cyan]", Text(f"> {lines[i].rstrip()}", style="bold white on grey15"))
            else: table.add_row(str(i+1), lines[i].rstrip())
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
            if line.strip().startswith(f"label {self.data['current_label']}:"):
                idx = i + self.data.get("line_index", 0)
                break
        if idx == -1: return
        
        et = Prompt.ask("\n[bold blue]Edit:[/bold blue] [1] BG | [2] Char | [3] Diag | [4] Choice | [5] Scene | [B]ack", choices=["1", "2", "3", "4", "5", "B", "b"])
        if et.upper() == "B": return
        
        if et == "1":
            p = Prompt.ask("  [1] ID | [2] Desc", choices=["1", "2"])
            if p == "1":
                opt = Prompt.ask("  [H]oose | [A]dd", choices=["H", "A"])
                if opt.upper() == "H":
                    assets = requests.get(f"{BASE_URL}/games/{self.game_id}/assets/backgrounds").json()["assets"]
                    c = Prompt.ask("  Select", choices=assets + ["B"])
                    if c != "B": requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "script", "action": "update", "target": str(idx), "content": f"background {c}"})
            elif p == "2":
                bg = self.data.get("background", "None")
                nd = Prompt.ask(f"  New Desc for {bg}")
                requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "background", "target": bg, "content": nd})
        elif et == "3":
            new_text = Prompt.ask("  New Text")
            requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/edit", json={"category": "script", "action": "update", "target": str(idx), "content": f"talk {self.data.get('character', 'narrator')} \"{new_text}\""})

    def run(self):
        res = requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/step", json={"command": "R"})
        self.data = res.json()
        while True:
            self.display_game()
            if self.data["type"] == "end": break
            if self.data["type"] == "missing_label":
                if Prompt.ask("\nGenerate with AI? (Y/N)", choices=["Y", "N", "y", "n"]).upper() == "Y":
                    with console.status("Generating..."): requests.post(f"{BASE_URL}/games/{self.game_id}/sessions/{self.session_id}/generate", json={"target": self.data["meta"]["target"]})
                    cmd = "R"
                else: cmd = "B"
            else:
                cmd = Prompt.ask("\n[bold green][Enter] Next | [V]iew Script | [R]eload | [B]ack | [E]dit | E[X]it[/bold green]")
            
            if cmd.upper() == "X": break
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
