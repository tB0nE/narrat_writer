import requests
import questionary
import time
from datetime import datetime
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.layout import Layout
from src.terminal_client.utils import make_intro_layout, get_menu_choice, console, BASE_URL, edit_text_in_external_editor

class GameHub:
    def __init__(self, custom_console, base_url):
        self.console = custom_console
        self.base_url = base_url

    def render_save_manager(self, options, selected_idx, saves) -> Layout:
        """Renders the save browser with a preview of the highlighted save."""
        layout = make_intro_layout()
        if selected_idx < len(saves):
            s = saves[selected_idx]
            dt = datetime.fromtimestamp(s['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            info = f"[bold cyan]Save: {s['id']}[/bold cyan]\n[dim]{dt}[/dim]\n\n[bold white]Location:[/bold white] {s['label']}\n\n[bold white]Last Dialogue:[/bold white]\n[italic]\"{s['last_text']}\"[/italic]"
        else:
            info = "[dim]Go back to the game hub.[/dim]"
        layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Save Preview", border_style="cyan"))
        menu_text = ""
        for i, opt in enumerate(options):
            if i == selected_idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
            else: menu_text += f"  {opt}\n"
        layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Saves", border_style="yellow"))
        return layout

    def render_game_hub(self, options, selected_idx, meta):
        """Renders the game-specific hub screen with metadata summary and interactive menu."""
        layout = make_intro_layout()
        info = f"[bold cyan]{meta['title']}[/bold cyan]\n\n{meta['summary']}\n\n[dim]Genre: {meta['genre']}[/dim]\n[dim]Characters: {', '.join(meta['characters'])}[/dim]"
        if meta.get("plot_outline"): info += f"\n\n[bold white]Plot Outline:[/bold white]\n{meta['plot_outline'][:200]}..."
        layout["left"].update(Panel(Align.center(info, vertical="middle"), border_style="cyan"))
        menu_text = ""
        for i, opt in enumerate(options):
            if i == selected_idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
            else: menu_text += f"  {opt}\n"
        layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Game Hub", border_style="yellow"))
        return layout

    def run(self, game_id):
        """Management hub for a specific game ID."""
        while True:
            res = requests.get(f"{self.base_url}/games/{game_id}/metadata")
            meta = res.json()
            options = ["Start New Game", "Load Game", "Manage Assets", "Edit Options", "Back"]
            choice = get_menu_choice(options, lambda opts, idx: self.render_game_hub(opts, idx, meta))
            if choice == "Back" or choice is None: return
            if choice == "Start New Game":
                sid = questionary.text("Enter new session name", default="autosave").ask()
                if sid:
                    from src.terminal_client.screens.engine import GameEngine
                    engine = GameEngine(game_id, sid, self.console, self.base_url)
                    engine.run()
            elif choice == "Load Game": self.save_manager_flow(game_id)
            elif choice == "Manage Assets": self.asset_manager_flow(game_id, meta)
            elif choice == "Edit Options": self.edit_metadata_flow(game_id, meta)

    def save_manager_flow(self, game_id):
        """Interactive flow to list, load, and delete saves."""
        while True:
            res = requests.get(f"{self.base_url}/games/{game_id}/saves")
            saves = res.json()["saves"]
            if not saves:
                questionary.text("No saves found. [Enter] to continue").ask()
                return
            def render_save(opts, idx, saves=saves):
                layout = make_intro_layout()
                if idx < len(saves):
                    s = saves[idx]
                    dt = datetime.fromtimestamp(s['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    info = f"[bold cyan]Save: {s['id']}[/bold cyan]\n[dim]{dt}[/dim]\n\n[bold white]Location:[/bold white] {s['label']}\n\n[bold white]Last Dialogue:[/bold white]\n[italic]\"{s['last_text']}\"[/italic]"
                else: info = "[dim]Back to game hub.[/dim]"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Save Preview", border_style="cyan"))
                menu_text = ""
                for i, opt in enumerate(opts):
                    if i == idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                    else: menu_text += f"  {opt}\n"
                layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Saves", border_style="yellow"))
                return layout
            options = [s["id"] for s in saves] + ["Back"]
            choice = get_menu_choice(options, render_save)
            if choice == "Back" or choice is None: return
            action = questionary.select(f"Save: {choice}", choices=["Load Save", "Delete Save", "Back"]).ask()
            if action == "Load Save":
                from src.terminal_client.screens.engine import GameEngine
                engine = GameEngine(game_id, choice, self.console, self.base_url)
                engine.run()
                return
            elif action == "Delete Save":
                if questionary.confirm(f"Delete '{choice}'?").ask():
                    requests.delete(f"{self.base_url}/games/{game_id}/saves/{choice}")

    def edit_metadata_flow(self, game_id, meta):
        """Dedicated UI for browsing and editing game metadata with live feedback."""
        while True:
            options = ["Title", "Summary", "Genre", "Plot Outline", "Prompt Prefix", "Starting Point", "Regenerate with AI", "Back"]
            def render_meta(opts, idx, meta=meta):
                layout = make_intro_layout()
                info = f"[bold cyan]Title:[/bold cyan] {meta['title']}\n[bold cyan]Genre:[/bold cyan] {meta['genre']}\n\n[bold white]Summary:[/bold white]\n{meta['summary']}\n\n"
                if meta.get("plot_outline"): info += f"[bold white]Plot Outline:[/bold white]\n{meta['plot_outline']}\n\n"
                info += f"[bold white]Starting Point:[/bold white] {meta.get('starting_point', 'main')}"
                layout["left"].update(Panel(info, title="Metadata Preview", border_style="cyan", padding=(1, 2)))
                menu_text = ""
                for i, opt in enumerate(opts):
                    if i == idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                    else: menu_text += f"  {opt}\n"
                layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Edit Metadata", border_style="yellow"))
                return layout
            choice = get_menu_choice(options, render_meta)
            if choice == "Back" or choice is None: break
            if choice == "Regenerate with AI":
                p = questionary.text("Prompt?").ask()
                if p is None: continue
                with console.status("Regenerating..."):
                    res = requests.post(f"{self.base_url}/games/{game_id}/regenerate", json={"name": game_id, "prompt": p or meta['summary']})
                if res.status_code == 200: meta = res.json()["metadata"]
                continue
            field_map = {"Title": "title", "Summary": "summary", "Genre": "genre", "Plot Outline": "plot_outline", "Prompt Prefix": "prompt_prefix", "Starting Point": "starting_point"}
            field = field_map[choice]
            initial_val = str(meta.get(field, ""))
            nv = None
            if len(initial_val) > 50 or choice in ["Summary", "Plot Outline", "Prompt Prefix"]:
                action = questionary.select("How to edit?", choices=["Inline", "External Editor", "Back"]).ask()
                if action == "Inline":
                    nv = questionary.text(f"New {field}", default=initial_val).ask()
                elif action == "External Editor":
                    nv = edit_text_in_external_editor(initial_val)
            else:
                nv = questionary.text(f"New {field}", default=initial_val).ask()
            
            if nv is not None:
                requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": field, "content": nv})
                meta[field] = nv

    def asset_manager_flow(self, game_id, meta):
        """Advanced management for game reference assets."""
        while True:
            cat_choice = questionary.select("Category", choices=["Backgrounds", "Characters", "Scenes", "Back"]).ask()
            if cat_choice == "Back" or cat_choice is None: break
            category = cat_choice.lower()
            while True:
                res = requests.get(f"{self.base_url}/games/{game_id}/assets/{category}")
                assets = res.json()["assets"]
                asset_id = questionary.select(f"Select {category[:-1].capitalize()}", choices=assets + [questionary.Separator(), "Add New", "Back"]).ask()
                if asset_id == "Back" or asset_id is None: break
                if asset_id == "Add New":
                    asset_id = questionary.text("Unique ID?").ask()
                    if not asset_id: continue
                while True:
                    action = questionary.select(f"{asset_id}", choices=["Rename Globally", "Edit Description", "AI Generate Description", "Back"]).ask()
                    if action == "Back" or action is None: break
                    if action == "Rename Globally":
                        ni = questionary.text(f"New ID for {asset_id}").ask()
                        if ni:
                            res = requests.post(f"{self.base_url}/games/{game_id}/assets/rename", json={"category": category, "old_id": asset_id, "new_id": ni})
                            if res.status_code == 200: asset_id = ni; break
                    elif action == "Edit Description":
                        res = requests.get(f"{self.base_url}/games/{game_id}/assets/{category}/{asset_id}")
                        initial_val = res.json().get("content", "")
                        method = questionary.select("How to edit?", choices=["Inline", "External Editor", "Back"]).ask()
                        if method == "Inline":
                            nd = questionary.text("Description?", default=initial_val).ask()
                        elif method == "External Editor":
                            nd = edit_text_in_external_editor(initial_val)
                        else: nd = None
                        
                        if nd is not None:
                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "reference", "action": "update", "sub_category": category[:-1], "target": asset_id, "content": nd})
                    elif action == "AI Generate Description":
                        with console.status("Generating..."):
                            requests.post(f"{self.base_url}/games/{game_id}/assets/generate", json={"category": category, "target": asset_id})
                    questionary.text("[Enter] to continue").ask()
