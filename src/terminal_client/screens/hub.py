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
        """Management hub for a specific game ID using a persistent Live context."""
        input_obj = create_input()
        
        while True:
            res = requests.get(f"{self.base_url}/games/{game_id}/metadata")
            meta = res.json()
            options = ["Start New Game", "Load Game", "Edit Game Metadata", "Scripts", "Characters", "Backgrounds", "Scenes", "Variables", "Validate Script", "Back"]
            
            with Live(self.render_game_hub(options, 0, meta), screen=True, auto_refresh=False) as live:
                idx = 0
                with input_obj.raw_mode():
                    while True:
                        live.update(self.render_game_hub(options, idx, meta)); live.refresh()
                        keys = input_obj.read_keys()
                        if not keys:
                            time.sleep(0.05); continue
                        
                        action_choice = None
                        for key in keys:
                            if key.key == Keys.Up: idx = (idx - 1) % len(options)
                            elif key.key == Keys.Down: idx = (idx + 1) % len(options)
                            elif key.key == Keys.Enter or key.key == Keys.ControlM:
                                action_choice = options[idx]
                            elif key.key == Keys.Escape: return # Back to launcher
                        
                        if action_choice:
                            if action_choice == "Back": return
                            
                            if action_choice == "Start New Game":
                                live.stop()
                                timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
                                sid = f"{game_id}_{timestamp}"
                                from src.terminal_client.screens.engine import GameEngine
                                engine = GameEngine(game_id, sid, self.console, self.base_url)
                                engine.run()
                                break # Break inner loop to refresh meta if needed
                            
                            elif action_choice == "Load Game":
                                self.save_manager_flow_shared(game_id, live, input_obj)
                                break # Refresh
                            
                            elif action_choice == "Scripts":
                                live.stop()
                                self.script_manager_flow(game_id)
                                live.start()
                                break
                            
                            elif action_choice in ["Characters", "Backgrounds", "Scenes", "Variables"]:
                                live.stop()
                                self.asset_manager_flow(game_id, meta, action_choice)
                                live.start()
                                break
                            
                            elif action_choice == "Edit Game Metadata":
                                live.stop()
                                self.edit_metadata_flow(game_id, meta)
                                live.start()
                                break
                            
                            elif action_choice == "Validate Script":
                                live.stop()
                                self.validate_script_flow_shared(game_id)
                                live.start()
                                break

    def validate_script_flow(self, game_id):
        """Calls the validation API and displays results in the UI."""
        with console.status("[bold green]Validating script...[/bold green]"):
            res = requests.get(f"{self.base_url}/games/{game_id}/validate")
            data = res.json()
        
        layout = make_intro_layout()
        if data["valid"]:
            info = "[bold green]✓ Script is valid![/bold green]\n\nAll labels, indentation, and core syntax rules passed validation."
            border = "green"
        else:
            info = f"[bold red]✗ Script has {len(data['errors'])} errors:[/bold red]\n\n"
            for err in data["errors"][:20]:
                info += f"• {err}\n"
            if len(data["errors"]) > 20:
                info += f"\n[dim]... and {len(data['errors'])-20} more errors.[/dim]"
            border = "red"
            
        layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Validation Results", border_style=border, padding=(1, 3)))
        layout["right"].update(Panel(Align.center("[bold yellow][Enter] to continue[/bold yellow]", vertical="middle"), title="Action", border_style="yellow"))
        
        with Live(layout, screen=True, auto_refresh=False) as live:
            live.refresh()
            questionary.press_any_key_to_continue().ask()

    def render_save_manager(self, opts, idx, saves):
        """Compatibility wrapper for tests."""
        state = {"saves": saves, "main_idx": idx}
        # In a real run, this is inside save_manager_flow_shared
        # but for standalone test rendering we provide this
        layout = make_intro_layout()
        if idx < len(saves):
            s = saves[idx]
            dt = datetime.fromtimestamp(s['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            info = f"[bold cyan]Save: {s['id']}[/bold cyan]\n[dim]{dt}[/dim]\n\n"
            info += f"[bold white]Location:[/bold white] {s['label']}\n\n"
            info += f"[bold white]Last Dialogue:[/bold white]\n[italic]\"{s['last_text']}\"[/italic]"
        else: info = "[dim italic]Back to game hub.[/dim italic]"
        layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Save Preview", border_style="cyan", padding=(1, 3)))
        menu_text = ""
        for i, opt in enumerate(opts):
            if i == idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
            else: menu_text += f"  {opt}\n"
        layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Saves", border_style="yellow"))
        return layout

    def render_game_hub(self, options, selected_idx, meta):
        """Renders the game-specific hub screen with metadata summary and interactive menu."""
        layout = make_intro_layout()
        info = f"[bold cyan]{meta['title']}[/bold cyan]\n\n"
        info += f"{meta['summary']}\n\n"
        info += f"[bold white]Genre:[/bold white] {meta.get('genre', 'Unknown')}\n"
        
        chars = meta.get('characters', [])
        cap_chars = [c.capitalize() for c in chars]
        info += f"[bold white]Characters:[/bold white] {', '.join(cap_chars[:10]) if cap_chars else 'None'}{'...' if len(cap_chars) > 10 else ''}\n\n"
        
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
        # Compatibility wrapper
        with Live(None, screen=True, auto_refresh=False) as live:
            self.save_manager_flow_shared(game_id, live, create_input())

    def save_manager_flow_shared(self, game_id, live, input_obj):
        """Interactive flow to list, load, and delete saves using a shared Live context."""
        state = {"mode": "view", "save_id": None, "main_idx": 0, "saves": []}

        def fetch_saves():
            try:
                res = requests.get(f"{self.base_url}/games/{game_id}/saves", timeout=2)
                return res.json()["saves"]
            except: return []

        def render_saves(state):
            layout = make_intro_layout()
            saves = state["saves"]
            if not saves:
                info = "[dim italic]No saves found for this game.[/dim italic]"
            elif state["main_idx"] < len(saves):
                s = saves[state["main_idx"]]
                dt = datetime.fromtimestamp(s['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                info = f"[bold cyan]Save: {s['id']}[/bold cyan]\n[dim]{dt}[/dim]\n\n"
                info += f"[bold white]Location:[/bold white] {s['label']}\n\n"
                info += f"[bold white]Last Dialogue:[/bold white]\n[italic]\"{s['last_text']}\"[/italic]"
            else: info = "[dim italic]Back to game hub.[/dim italic]"
            layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Save Preview", border_style="cyan", padding=(1, 3)))
            
            menu_text = ""
            opts = [s["id"] for s in saves] + ["Back"]
            for i, opt in enumerate(opts):
                if i == state["main_idx"]: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Saves", border_style="yellow"))
            return layout

        state["saves"] = fetch_saves()
        while True:
            live.update(render_saves(state)); live.refresh()
            keys = input_obj.read_keys()
            if not keys:
                time.sleep(0.05); continue
            
            exit_flow = False
            for key in keys:
                opts = [s["id"] for s in state["saves"]] + ["Back"]
                if key.key == Keys.Up: state["main_idx"] = (state["main_idx"] - 1) % len(opts)
                elif key.key == Keys.Down: state["main_idx"] = (state["main_idx"] + 1) % len(opts)
                elif key.key == Keys.Enter or key.key == Keys.ControlM:
                    choice = opts[state["main_idx"]]
                    if choice == "Back": exit_flow = True; break
                    
                    live.stop(); console.clear()
                    action = questionary.select(f"Save: {choice}", choices=["Load Save", "Delete Save", "Back"]).ask()
                    if action == "Load Save":
                        from src.terminal_client.screens.engine import GameEngine
                        engine = GameEngine(game_id, choice, self.console, self.base_url)
                        engine.run()
                        exit_flow = True; break
                    elif action == "Delete Save":
                        if questionary.confirm(f"Delete '{choice}'?").ask():
                            requests.delete(f"{self.base_url}/games/{game_id}/saves/{choice}")
                            state["saves"] = fetch_saves()
                            state["main_idx"] = 0
                    live.start()
                elif key.key == Keys.Escape: exit_flow = True; break
            
            if exit_flow: break

    def validate_script_flow_shared(self, game_id):
        """Standard validate flow but uses existing console/UI."""
        res = requests.get(f"{self.base_url}/games/{game_id}/validate")
        data = res.json()
        layout = make_intro_layout()
        if data["valid"]:
            info = "[bold green]✓ Script is valid![/bold green]"
            border = "green"
        else:
            info = f"[bold red]✗ Script has {len(data['errors'])} errors.[/bold red]"
            border = "red"
        layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Validation", border_style=border))
        layout["right"].update(Panel(Align.center("[bold yellow]Press any key[/bold yellow]", vertical="middle"), title="Action"))
        console.clear(); console.print(layout)
        questionary.press_any_key_to_continue().ask()

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

    def asset_manager_flow(self, game_id, meta, start_category=None):
        """Advanced management for game reference assets using a single-loop interaction."""
        state = {"mode": "view", "category": start_category, "asset_id": None, "field": None, "sub_options": [], "sub_idx": 0, "main_idx": 0, "asset_content": ""}
        categories = ["Backgrounds", "Characters", "Scenes", "Variables", "Back"]
        input_obj = create_input()

        def fetch_preview(cat, aid):
            try:
                if cat.lower() == "characters":
                    res_p = requests.get(f"{self.base_url}/games/{game_id}/assets/characters/{aid}", params={"type": "profile"}, timeout=0.5)
                    res_d = requests.get(f"{self.base_url}/games/{game_id}/assets/characters/{aid}", params={"type": "description"}, timeout=0.5)
                    profile = res_p.json().get("content", "[No profile]") if res_p.status_code == 200 else "[No profile]"
                    desc = res_d.json().get("content", "[No description]") if res_d.status_code == 200 else "[No description]"
                    return f"[bold yellow]Profile:[/bold yellow]\n{profile}\n\n[bold yellow]Description:[/bold yellow]\n{desc}"
                
                res = requests.get(f"{self.base_url}/games/{game_id}/assets/{cat.lower()}/{aid}", timeout=0.5)
                if res.status_code == 200: return res.json().get("content", "")
            except: pass
            return "[No description available]"

        def fetch_category_assets(cat):
            if cat == "Back": return []
            try:
                res = requests.get(f"{self.base_url}/games/{game_id}/assets/{cat.lower()}", timeout=0.5)
                if res.status_code == 200: return res.json().get("assets", [])
            except: pass
            return []

        def render_assets(state):
            layout = make_intro_layout()
            
            # Left Panel Content
            if state["mode"] == "view":
                info = f"[bold cyan]{state['category'] or 'Asset Manager'}[/bold cyan]\n\n"
                if state.get("category_preview"):
                    cat = state["category_preview"]
                    info += f"[bold yellow]Previewing Category: {cat}[/bold yellow]\n"
                    assets = state.get("category_assets", [])
                    if assets:
                        info += "\n[dim]Available Assets:[/dim]\n"
                        for a in assets[:15]:
                            display_name = a.capitalize() if cat.lower() == "characters" else a
                            info += f"• {display_name}\n"
                        if len(assets) > 15:
                            info += f"[dim]... and {len(assets)-15} more[/dim]"
                    else:
                        info += "\n[dim italic]No assets found in this category.[/dim italic]"
                else:
                    info += "Select an asset on the right to browse and edit its properties.\n\n"
                    info += "[dim]Current Selection:[/dim]\n"
                    info += f"Category: [white]{state['category'] or 'None'}[/white]\n"
                    asset_display = state['asset_id']
                    if asset_display and state['category'].lower() == "characters":
                        asset_display = asset_display.capitalize()
                    info += f"Asset: [white]{asset_display or 'None'}[/white]"
                layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Overview", border_style="cyan", padding=(1, 3)))
            
            elif state["mode"] == "select":
                info = f"[bold yellow]Select {state['field']}[/bold yellow]\n\n"
                for i, s_opt in enumerate(state["sub_options"]):
                    if i == state["sub_idx"]: info += f"> [bold yellow]{s_opt}[/bold yellow]\n"
                    else: info += f"  {s_opt}\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title=f"Browse {state['field']}", border_style="yellow"))

            elif state["mode"] == "preview":
                # Use asset_id_preview for live scrolling, asset_id for locked action menu
                aid = state.get("asset_id_preview") or state.get("asset_id")
                display_aid = aid.capitalize() if state['category'].lower() == "characters" else aid
                info = f"[bold cyan]Asset: {display_aid}[/bold cyan] ({state['category'][:-1]})\n\n"
                content = state.get("asset_content", "")
                info += content[:1200] + ("..." if len(content) > 1200 else "")
                layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Asset Preview", border_style="cyan", padding=(1, 3)))

            elif state["mode"] == "loading":
                info = f"[bold yellow]Loading {state['field']}...[/bold yellow]\n\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Please Wait", border_style="yellow"))

            # Right Panel (Menu)
            menu_text = ""
            opts = state.get("active_menu", categories)
            for i, opt in enumerate(opts):
                label = opt
                if state["category"] and not state["asset_id"] and opt not in ["Add New", "Scan", "Back"]:
                    if state["category"].lower() == "characters":
                        label = opt.capitalize()
                
                if i == state["main_idx"]: menu_text += f"> [bold yellow]{label}[/bold yellow]\n"
                else: menu_text += f"  {label}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Asset Menu", border_style="yellow"))
            return layout

        # Setup initial state based on start_category
        if start_category:
            state["category"] = start_category
            state["mode"], state["field"] = "loading", start_category
            try:
                res = requests.get(f"{self.base_url}/games/{game_id}/assets/{start_category.lower()}")
                state["active_menu"] = ["Add New"] + res.json()["assets"] + ["Back"]
                state["main_idx"] = 0; state["mode"] = "view"
                if len(state["active_menu"]) > 1 and state["active_menu"][1] not in ["Add New", "Back"]:
                    state["mode"], state["asset_id_preview"] = "preview", state["active_menu"][1]
                    state["asset_content"] = fetch_preview(start_category, state["active_menu"][1])
            except:
                state["active_menu"] = ["Add New", "Back"]
                state["mode"] = "view"
        else:
            state["active_menu"] = categories
            # Initial preview
            state["category_preview"] = categories[0]
            state["category_assets"] = fetch_category_assets(categories[0])
        
        with Live(render_assets(state), screen=True, auto_refresh=False) as live:
            with input_obj.raw_mode():
                while True:
                    try:
                        live.update(render_assets(state)); live.refresh()
                        keys = input_obj.read_keys()
                        if not keys:
                            time.sleep(0.05); continue
                        for key in keys:
                            if key.key == Keys.Up or key.key == Keys.Down:
                                old_idx = state["main_idx"]
                                if key.key == Keys.Up: state["main_idx"] = (state["main_idx"] - 1) % len(state["active_menu"])
                                else: state["main_idx"] = (state["main_idx"] + 1) % len(state["active_menu"])
                                
                                choice = state["active_menu"][state["main_idx"]]
                                
                                # 1. Category Level Preview
                                if state["active_menu"] == categories:
                                    if choice != "Back":
                                        state["category_preview"] = choice
                                        state["category_assets"] = fetch_category_assets(choice)
                                    else:
                                        state["category_preview"] = None; state["category_assets"] = []

                                # 2. Asset Level Preview logic - Only if list changed
                                elif state["category"] and not state["asset_id"] and old_idx != state["main_idx"]:
                                    if choice not in ["Add New", "Scan", "Back"]:
                                        state["mode"], state["asset_id_preview"] = "preview", choice
                                        state["asset_content"] = fetch_preview(state["category"], choice)
                                    else:
                                        state["mode"] = "view"; state["asset_id_preview"] = None
                            
                            elif key.key == Keys.Enter or key.key == Keys.ControlM:
                                choice = state["active_menu"][state["main_idx"]]
                                if choice == "Back":
                                    if state["active_menu"] == categories: return
                                    elif state["category"] and state["asset_id"]: # In action menu
                                        state["asset_id"] = None
                                        # Reload assets list
                                        state["mode"], state["field"] = "loading", state["category"]
                                        live.update(render_assets(state)); live.refresh()
                                        res = requests.get(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}")
                                        state["active_menu"] = ["Add New", "Scan"] + res.json()["assets"] + ["Back"]
                                        state["main_idx"] = 0; state["mode"] = "view"
                                        # Immediate preview if first is asset
                                        # Index 2 because 0 is Add New, 1 is Scan
                                        if len(state["active_menu"]) > 2 and state["active_menu"][2] not in ["Add New", "Scan", "Back"]:
                                            state["mode"], state["asset_id_preview"] = "preview", state["active_menu"][2]
                                            state["asset_content"] = fetch_preview(state["category"], state["active_menu"][2])
                                    else: # In asset list
                                        if start_category: return # Go back to hub
                                        state["category"] = None; state["active_menu"] = categories; state["main_idx"] = 0; state["mode"] = "view"; state["asset_id_preview"] = None
                                    continue

                                # 1. Category Selection
                                if state["active_menu"] == categories:
                                    state["category"] = choice
                                    state["asset_id"] = None; state["asset_id_preview"] = None
                                    state["mode"], state["field"] = "loading", choice
                                    live.update(render_assets(state)); live.refresh()
                                    res = requests.get(f"{self.base_url}/games/{game_id}/assets/{choice.lower()}")
                                    # User wants Add New first, then existing, then Back
                                    state["active_menu"] = ["Add New", "Scan"] + res.json()["assets"] + ["Back"]
                                    state["main_idx"] = 0; state["mode"] = "view"
                                    # Trigger immediate preview if first item is an asset
                                    if len(state["active_menu"]) > 2 and state["active_menu"][2] not in ["Add New", "Scan", "Back"]:
                                        state["mode"], state["asset_id_preview"] = "preview", state["active_menu"][2]
                                        state["asset_content"] = fetch_preview(choice, state["active_menu"][2])
                                
                                # 2. Asset Selection
                                elif state["category"] and not state["asset_id"]:
                                    if choice == "Add New":
                                        live.stop(); console.clear(); console.print(render_assets(state))
                                        new_id = questionary.text("Unique ID?").ask()
                                        if new_id:
                                            if state["category"].lower() == "characters":
                                                new_id = new_id.lower().replace(" ", "_")
                                            
                                            # Create on server
                                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={
                                                "category": "reference", 
                                                "action": "update", 
                                                "sub_category": state["category"].lower()[:-1], 
                                                "target": new_id, 
                                                "content": ""
                                            })
                                            
                                            state["asset_id"] = new_id; state["asset_id_preview"] = new_id
                                            
                                            if state["category"].lower() == "characters":
                                                actions = ["Rename", "Edit Description", "Edit Profile", "AI Generate Description", "Delete", "Back"]
                                            else:
                                                actions = ["Rename", "Edit Description", "AI Generate Description", "Delete", "Back"]
                                            
                                            state["active_menu"] = actions
                                            state["main_idx"] = 0; state["mode"] = "preview"; state["asset_content"] = ""
                                        live.start()
                                    elif choice == "Scan":
                                        state["mode"], state["field"] = "loading", "Scanning script..."
                                        live.update(render_assets(state)); live.refresh()
                                        res = requests.post(f"{self.base_url}/games/{game_id}/assets/scan")
                                        added = res.json().get("added", {})
                                        count = sum(len(v) for v in added.values())
                                        
                                        live.stop()
                                        if count > 0:
                                            summary = "\n".join([f"  {k.capitalize()}: {', '.join(v)}" for k, v in added.items() if v])
                                            console.print(f"[bold green]Scan complete![/bold green] Added {count} new assets:\n{summary}")
                                        else:
                                            console.print("[bold yellow]Scan complete. No new assets found.[/bold yellow]")
                                        questionary.press_any_key_to_continue().ask()
                                        
                                        # Reload list
                                        res = requests.get(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}")
                                        state["active_menu"] = ["Add New", "Scan"] + res.json()["assets"] + ["Back"]
                                        state["main_idx"] = 1 # Stay on Scan
                                        state["mode"] = "view"
                                        live.start()
                                    else:
                                        state["asset_id"] = choice; state["asset_id_preview"] = choice
                                        state["mode"], state["field"] = "loading", choice
                                        live.update(render_assets(state)); live.refresh()
                                        state["asset_content"] = fetch_preview(state["category"], choice)
                                        
                                        # 1. Base actions available for all assets
                                        if state["category"].lower() == "characters":
                                            actions = ["Rename", "Edit Description", "Edit Profile", "AI Generate Description"]
                                        else:
                                            actions = ["Rename", "Edit Description", "AI Generate Description"]
                                            
                                        # 2. Add Delete option. Note: Server-side validation will block
                                        # deletion if the asset is still detected within the narrat script.
                                        actions.append("Delete")
                                        actions.append("Back")
                                        
                                        state["active_menu"] = actions
                                        state["main_idx"] = 0; state["mode"] = "preview"

                                # 3. Action Selection
                                elif state["asset_id"]:
                                    if choice == "Rename":
                                        live.stop(); console.clear(); console.print(render_assets(state))
                                        ni = questionary.text(f"New ID for {state['asset_id']}").ask()
                                        if ni:
                                            # Normalize character IDs: lowercase and underscores
                                            if state["category"].lower() == "characters":
                                                ni = ni.lower().replace(" ", "_")
                                            res = requests.post(f"{self.base_url}/games/{game_id}/assets/rename", json={"category": state["category"].lower(), "old_id": state["asset_id"], "new_id": ni})
                                            if res.status_code == 200: state["asset_id"] = ni
                                        live.start()
                                    elif choice == "Delete":
                                        # Deletion is permitted ONLY if the asset is not found in the script.
                                        # This is enforced by the server's DELETE handler.
                                        live.stop()
                                        if questionary.confirm(f"Delete {state['asset_id']}?").ask():
                                            res = requests.delete(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}/{state['asset_id']}")
                                            if res.status_code == 200:
                                                state["asset_id"] = None
                                                # Reload list
                                                res_list = requests.get(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}")
                                                state["active_menu"] = ["Add New", "Scan"] + res_list.json()["assets"] + ["Back"]
                                                state["main_idx"] = 0; state["mode"] = "view"
                                            else:
                                                console.print(f"[red]Error: {res.json().get('detail', 'Unknown error')}[/red]")
                                                time.sleep(2)
                                        live.start()
                                    elif choice in ["Edit Description", "Edit Profile"]:
                                        ctype = "description" if "Description" in choice else "profile"
                                        # Fetch the latest content for this specific type
                                        res = requests.get(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}/{state['asset_id']}", params={"type": ctype})
                                        current_val = res.json().get("content", "")
                                        
                                        res_config = requests.get(f"{self.base_url}/config")
                                        editor = res_config.json().get("editor", "")
                                        live.stop(); console.clear(); console.print(render_assets(state))
                                        if editor and editor != "None":
                                            console.print(f"\n[yellow]Opening {editor} for {state['asset_id']} ({ctype})...[/yellow]")
                                            time.sleep(0.3); console.clear()
                                            nv = edit_text_in_external_editor(current_val)
                                        else:
                                            nv = questionary.text(f"{choice}?", default=current_val).ask()
                                        
                                        if nv is not None:
                                            requests.post(f"{self.base_url}/games/{game_id}/sessions/any/edit", json={
                                                "category": "reference", 
                                                "action": "update", 
                                                "sub_category": state["category"].lower()[:-1], 
                                                "target": state["asset_id"], 
                                                "content": nv,
                                                "meta": {"type": ctype}
                                            })
                                            state["asset_content"] = fetch_preview(state["category"], state["asset_id"])
                                        live.start()
                                    elif choice == "AI Generate Description":
                                        state["mode"], state["field"] = "loading", "AI Generation"
                                        live.update(render_assets(state)); live.refresh()
                                        requests.post(f"{self.base_url}/games/{game_id}/assets/generate", json={"category": state["category"].lower(), "target": state["asset_id"]})
                                        # Reload
                                        res = requests.get(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}/{state['asset_id']}")
                                        state["asset_content"] = res.json().get("content", "")
                                        state["mode"] = "preview"

                            elif key.key == Keys.Escape:
                                if state["active_menu"] == categories: return
                                elif state["category"] and state["asset_id"]:
                                    state["asset_id"] = None
                                    res = requests.get(f"{self.base_url}/games/{game_id}/assets/{state['category'].lower()}")
                                    state["active_menu"] = res.json()["assets"] + ["Add New", "Back"]
                                    state["main_idx"] = 0; state["mode"] = "view"
                                else:
                                    state["category"] = None; state["active_menu"] = categories; state["main_idx"] = 0; state["mode"] = "view"

                    except Exception as e:
                        live.stop(); console.print(f"[red]Error in Asset Flow: {e}[/red]"); time.sleep(2); live.start()

    def script_manager_flow(self, game_id):
        """Management interface for modular script files."""
        input_obj = create_input()
        state = {"main_idx": 0, "active_menu": [], "scripts": [], "mode": "view", "preview_content": ""}

        def fetch_scripts():
            res = requests.get(f"{self.base_url}/games/{game_id}/scripts")
            return res.json().get("scripts", [])

        def fetch_preview(path):
            try:
                res = requests.get(f"{self.base_url}/games/{game_id}/scripts/content", params={"path": path}, timeout=0.5)
                if res.status_code == 200:
                    content = res.json().get("content", "")
                    lines = content.split("\n")
                    snippet = "\n".join(lines[:15]) + ("\n..." if len(lines) > 15 else "")
                    return f"[bold cyan]Path:[/bold cyan] {path}\n\n{snippet}"
                return "Error fetching content"
            except: return "Error fetching preview"

        def render_scripts(state):
            layout = make_intro_layout()
            
            # Left Panel: Preview
            if (state["mode"] == "preview" or state["mode"] == "actions") and state.get("selected_path"):
                info = fetch_preview(state["selected_path"])
                layout["left"].update(Panel(Align.left(info, vertical="middle"), title="Script Preview", border_style="cyan", padding=(1, 3)))
            else:
                info = "[bold cyan]Script Manager[/bold cyan]\n\nSelect a script file on the right to view its details or edit it.\n\n"
                info += f"[bold white]Total Scripts:[/bold white] {len(state['scripts'])}\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Overview", border_style="cyan"))

            # Right Panel: Menu
            menu_text = ""
            for i, opt in enumerate(state["active_menu"]):
                if i == state["main_idx"]: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Scripts", border_style="yellow"))
            return layout

        state["scripts"] = fetch_scripts()
        script_paths = [s["path"] for s in state["scripts"]]
        state["active_menu"] = ["Add New"] + script_paths + ["Back"]

        with Live(render_scripts(state), screen=True, auto_refresh=False) as live:
            with input_obj.raw_mode():
                while True:
                    live.update(render_scripts(state)); live.refresh()
                    keys = input_obj.read_keys()
                    if not keys:
                        time.sleep(0.05); continue
                    
                    for key in keys:
                        if key.key == Keys.Up: 
                            state["main_idx"] = (state["main_idx"] - 1) % len(state["active_menu"])
                            choice = state["active_menu"][state["main_idx"]]
                            if state["mode"] != "actions":
                                if choice not in ["Add New", "Back"]:
                                    state["mode"] = "preview"; state["selected_path"] = choice
                                else:
                                    state["mode"] = "view"
                        elif key.key == Keys.Down:
                            state["main_idx"] = (state["main_idx"] + 1) % len(state["active_menu"])
                            choice = state["active_menu"][state["main_idx"]]
                            if state["mode"] != "actions":
                                if choice not in ["Add New", "Back"]:
                                    state["mode"] = "preview"; state["selected_path"] = choice
                                else:
                                    state["mode"] = "view"
                        elif key.key == Keys.Enter or key.key == Keys.ControlM:
                            choice = state["active_menu"][state["main_idx"]]
                            if choice == "Back":
                                if state["mode"] == "actions":
                                    state["mode"] = "preview"
                                    state["active_menu"] = ["Add New"] + [s["path"] for s in state["scripts"]] + ["Back"]
                                    state["main_idx"] = script_paths.index(state["selected_path"]) + 1 if state.get("selected_path") in script_paths else 0
                                else:
                                    return
                            elif choice == "Add New":
                                live.stop(); console.clear()
                                stype = questionary.select("Script Type", choices=["chapter", "quest", "interaction", "other"]).ask()
                                if stype:
                                    sid = questionary.text("Script Name (e.g. intro)").ask()
                                    if sid:
                                        path = f"{stype}s/{sid}.narrat" if stype != "other" else f"{sid}.narrat"
                                        requests.post(f"{self.base_url}/games/{game_id}/scripts", json={"path": path})
                                        state["scripts"] = fetch_scripts()
                                        script_paths = [s["path"] for s in state["scripts"]]
                                        state["active_menu"] = ["Add New"] + script_paths + ["Back"]
                                        state["main_idx"] = 0
                                live.start()
                            elif state["mode"] == "preview":
                                state["mode"] = "actions"
                                state["selected_path"] = choice
                                state["active_menu"] = ["Edit", "Delete", "Back"]
                                state["main_idx"] = 0
                            elif choice == "Edit":
                                res_config = requests.get(f"{self.base_url}/config")
                                editor = res_config.json().get("editor")
                                if not editor or editor == "None":
                                    live.stop(); console.print("[red]No external editor configured in Options![/red]"); time.sleep(2); live.start()
                                    continue
                                
                                live.stop(); console.clear()
                                # Fetch content and open editor
                                res = requests.get(f"{self.base_url}/games/{game_id}/scripts/content", params={"path": state["selected_path"]})
                                if res.status_code == 200:
                                    content = res.json().get("content", "")
                                    from src.terminal_client.utils import edit_text_in_external_editor
                                    new_content = edit_text_in_external_editor(content)
                                    if new_content is not None and new_content != content:
                                        requests.put(f"{self.base_url}/games/{game_id}/scripts/content", json={"path": state["selected_path"], "content": new_content})
                                        state["scripts"] = fetch_scripts()
                                live.start()
                            elif choice == "Delete":
                                live.stop()
                                if questionary.confirm(f"Delete script {state['selected_path']}?").ask():
                                    res = requests.delete(f"{self.base_url}/games/{game_id}/scripts/content", params={"path": state['selected_path']})
                                    if res.status_code == 200:
                                        state["scripts"] = fetch_scripts()
                                        script_paths = [s["path"] for s in state["scripts"]]
                                        state["active_menu"] = ["Add New"] + script_paths + ["Back"]
                                        state["main_idx"] = 0
                                        state["mode"] = "view"
                                    else:
                                        console.print(f"[red]Error: {res.json().get('detail', 'Delete failed')}[/red]")
                                        time.sleep(2)
                                live.start()
                        elif key.key == Keys.Escape: return

