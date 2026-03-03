import requests
import questionary
import time
import os
import re
from datetime import datetime
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from src.terminal_client.utils import (
    make_intro_layout, get_menu_choice, console, BASE_URL, 
    edit_text_in_external_editor
)

class GameHub:
    def __init__(self, custom_console, base_url):
        self.console = custom_console
        self.base_url = base_url

    def run(self, game_id):
        """Management hub for a specific game ID."""
        while True:
            res = requests.get(f"{self.base_url}/games/{game_id}/metadata")
            meta = res.json()
            options = ["Start New Game", "Load Game", "Manage Assets", "Edit Game", "Back"]
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
            elif choice == "Edit Game": self.edit_metadata_flow(game_id, meta)

    def render_game_hub(self, options, selected_idx, meta):
        """Renders the game-specific hub screen with metadata summary and interactive menu."""
        layout = make_intro_layout()
        info = f"[bold cyan]{meta['title']}[/bold cyan]\n\n"
        info += f"{meta['summary']}\n\n"
        info += f"[bold white]Genre:[/bold white] {meta.get('genre', 'Unknown')}\n"
        chars = meta.get('characters', [])
        info += f"[bold white]Characters:[/bold white] {', '.join(chars) if chars else 'None'}\n\n"
        plot = meta.get('plot_outline', '')
        if plot:
            info += f"[bold white]Plot Outline:[/bold white]\n{plot[:500]}{'...' if len(plot) > 500 else ''}"
            
        layout["left"].update(Panel(Align.left(info, vertical="middle"), border_style="cyan", padding=(1, 3)))
        
        menu_text = ""
        for i, opt in enumerate(options):
            if i == selected_idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
            else: menu_text += f"  {opt}\n"
        layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Game Hub", border_style="yellow"))
        return layout

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
                    info = f"[bold cyan]Save: {s['id']}[/bold cyan]\n[dim]{dt}[/dim]\n\n"
                    info += f"[bold white]Location:[/bold white] {s['label']}\n\n"
                    info += f"[bold white]Last Dialogue:[/bold white]\n[italic]\"{s['last_text']}\"[/italic]"
                else: 
                    info = "[dim italic]Back to game hub.[/dim italic]"
                
                layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Save Preview", border_style="cyan", padding=(1, 3)))
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
        """Dedicated UI for browsing and editing game metadata with live feedback and inline inputs."""
        state = {"mode": "view", "field": None, "sub_options": [], "sub_idx": 0, "input_val": "", "main_idx": 0}
        main_options = ["Title", "Summary", "Genre", "Plot Outline", "Prompt Prefix", "Starting Point", "Refine with AI", "Back"]
        input_obj = create_input()
        genres = ["Cyberpunk", "Fantasy", "Mystery", "Sci-Fi", "Horror", "Romance", "Slice of Life", "Drama", "Comedy", "Thriller", "Custom", "Back"]

        def render_meta(meta, state):
            layout = make_intro_layout()
            if state["mode"] == "view":
                info = f"[bold cyan]Metadata Preview[/bold cyan]\n\n"
                info += f"[bold white]Title:[/bold white] {meta.get('title')}\n"
                info += f"[bold white]Genre:[/bold white] {meta.get('genre')}\n"
                info += f"[bold white]Starting Point:[/bold white] {meta.get('starting_point', 'main')}\n\n"
                info += f"[bold white]Summary:[/bold white]\n{meta.get('summary', '')[:300]}...\n\n"
                if meta.get("plot_outline"):
                    info += f"[bold white]Plot Outline:[/bold white]\n{meta.get('plot_outline', '')[:300]}...\n"
                layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Current Metadata", border_style="cyan", padding=(1, 3)))
            elif state["mode"] == "select":
                info = f"[bold yellow]Select {state['field']}[/bold yellow]\n\n"
                for i, s_opt in enumerate(state["sub_options"]):
                    if i == state["sub_idx"]: info += f"> [bold yellow]{s_opt}[/bold yellow]\n"
                    else: info += f"  {s_opt}\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title=f"Choose {state['field']}", border_style="yellow"))
            elif state["mode"] == "input":
                info = f"[bold green]Editing {state['field']}[/bold green]\n\n"
                info += f"[dim italic]Please see the input prompt below...[/dim italic]\n"
                info += f"\nCurrent Value: [bold]{state['input_val']}[/bold]"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title=f"Enter {state['field']}", border_style="green"))
            elif state["mode"] == "loading":
                info = f"[bold yellow]Loading {state['field']}...[/bold yellow]\n\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Please Wait", border_style="yellow"))

            menu_text = ""
            for i, opt in enumerate(main_options):
                if i == state["main_idx"]: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Edit Game", border_style="yellow"))
            return layout

        with Live(render_meta(meta, state), screen=True, auto_refresh=False) as live:
            with input_obj.raw_mode():
                while True:
                    try:
                        live.update(render_meta(meta, state)); live.refresh()
                        keys = input_obj.read_keys()
                        if not keys:
                            time.sleep(0.05); continue
                        for key in keys:
                            if key.key == Keys.Up:
                                if state["mode"] == "view": state["main_idx"] = (state["main_idx"] - 1) % len(main_options)
                                elif state["mode"] == "select": state["sub_idx"] = (state["sub_idx"] - 1) % len(state["sub_options"])
                            elif key.key == Keys.Down:
                                if state["mode"] == "view": state["main_idx"] = (state["main_idx"] + 1) % len(main_options)
                                elif state["mode"] == "select": state["sub_idx"] = (state["sub_idx"] + 1) % len(state["sub_options"])
                            elif key.key == Keys.Enter or key.key == Keys.ControlM:
                                if state["mode"] == "view":
                                    choice = main_options[state["main_idx"]]
                                    if choice == "Back": return
                                    field_map = {"Title": "title", "Summary": "summary", "Genre": "genre", "Plot Outline": "plot_outline", "Prompt Prefix": "prompt_prefix", "Starting Point": "starting_point"}
                                    field_key = field_map.get(choice)
                                    
                                    if choice == "Title":
                                        state["mode"], state["field"], state["input_val"] = "input", "Title", meta.get("title", "")
                                        live.stop(); console.clear(); console.print(render_meta(meta, state))
                                        nv = questionary.text("New Title", default=state["input_val"]).ask()
                                        if nv: 
                                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": "title", "content": nv})
                                            meta["title"] = nv
                                        state["mode"] = "view"; live.start()
                                    elif choice in ["Summary", "Plot Outline", "Prompt Prefix"]:
                                        res_config = requests.get(f"{self.base_url}/config")
                                        editor = res_config.json().get("editor", "")
                                        current_val = meta.get(field_key, "") or ""
                                        live.stop(); console.clear(); console.print(render_meta(meta, state))
                                        if editor and editor != "None":
                                            console.print(f"\n[yellow]Opening {editor} for {choice}...[/yellow]")
                                            time.sleep(0.3); console.clear()
                                            nv = edit_text_in_external_editor(current_val)
                                        else:
                                            nv = questionary.text(f"New {choice}", default=current_val).ask()
                                        if nv is not None:
                                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": field_key, "content": nv})
                                            meta[field_key] = nv
                                        state["mode"] = "view"; live.start()
                                    elif choice == "Genre":
                                        state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", "Genre", genres, 0
                                    elif choice == "Starting Point":
                                        state["mode"], state["field"] = "loading", "Labels"
                                        live.update(render_meta(meta, state)); live.refresh()
                                        res_l = requests.get(f"{self.base_url}/games/{game_id}/labels")
                                        labels = res_l.json().get("labels", ["main"])
                                        state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", "Starting Point", labels + ["Back"], 0
                                    elif choice == "Refine with AI":
                                        state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", "Field to Refine", ["Title", "Summary", "Plot Outline", "Back"], 0

                                elif state["mode"] == "select":
                                    selection = state["sub_options"][state["sub_idx"]]
                                    field = state["field"]
                                    if selection == "Back" or selection == "Keep Current":
                                        state["mode"] = "view"
                                    elif field == "Genre" and selection == "Custom":
                                        state["mode"], state["field"], state["input_val"] = "input", "Custom Genre", meta.get("genre", "")
                                        live.stop(); console.clear(); console.print(render_meta(meta, state))
                                        nv = questionary.text("Enter Genre").ask()
                                        if nv:
                                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": "genre", "content": nv})
                                            meta["genre"] = nv
                                        state["mode"] = "view"; live.start()
                                    elif field == "Genre":
                                        requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": "genre", "content": selection})
                                        meta["genre"] = selection; state["mode"] = "view"
                                    elif field == "Starting Point":
                                        requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": "starting_point", "content": selection})
                                        meta["starting_point"] = selection; state["mode"] = "view"
                                    elif field == "Field to Refine":
                                        if selection == "Back":
                                            state["mode"] = "view"; continue
                                            
                                        target_map = {"Title": "title", "Summary": "summary", "Plot Outline": "plot_outline"}
                                        target_field = target_map[selection]
                                        
                                        # Immediate Query
                                        state["mode"], state["field"] = "loading", f"Querying AI for {selection} ideas..."
                                        live.update(render_meta(meta, state)); live.refresh()
                                        
                                        try:
                                            # We send a default instruction since we want it immediate
                                            r_res = requests.post(f"{self.base_url}/games/{game_id}/refine/options", json={"field": target_field, "instruction": "Generate 3 creative and varied improvements for this field."})
                                            if r_res.status_code == 200:
                                                ai_opts = r_res.json()["options"]
                                                current_val = meta.get(target_field, "")
                                                # Show original + 3 AI options
                                                state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", f"New {selection}", [current_val] + ai_opts + ["Back"], 0
                                                state["target_field_key"] = target_field
                                            else: raise Exception("API Error")
                                        except Exception as e:
                                            live.stop(); console.print(f"[red]Error: {e}[/red]"); time.sleep(2); live.start()
                                            state["mode"] = "view"
                                    elif field.startswith("New "):
                                        tfk = state.get("target_field_key")
                                        if selection != "Back" and tfk:
                                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={"category": "metadata", "action": "update", "target": tfk, "content": selection})
                                            meta[tfk] = selection
                                        state["mode"] = "view"

                            elif key.key == Keys.Escape:
                                if state["mode"] != "view": state["mode"] = "view"
                                else: return
                    except Exception as e:
                        live.stop()
                        console.print(f"[red]Error in Metadata Flow: {e}[/red]")
                        time.sleep(2)
                        live.start()

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
