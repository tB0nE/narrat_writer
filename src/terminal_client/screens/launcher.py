import requests
import sys
import time
import shutil
import re
import os
import questionary
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.console import Group
from rich.live import Live
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from src.terminal_client.utils import (
    console, BASE_URL, make_intro_layout
)

class Launcher:
    def __init__(self, custom_console=None, base_url=None):
        self.show_script = True
        self.console = custom_console or console
        self.base_url = base_url or BASE_URL

    def display_intro(self, options=None, selected_idx=0):
        """Renders the main splash screen with centered logo and interactive menu panel."""
        layout = make_intro_layout()
        # Define the logo lines (User finalized version) without trailing whitespace 
        # to ensure proper grouping and centering in the layout.
        logo_lines = [
            "        █████████              █████████",
            "      ██████████████        ██████████████",
            "     ████████████████      ████████████████",
            "    ████████████████████████████████████████",
            "    ████████████████████████████████████████",
            "    ████████████████████████████████████████",
            "     ██████████████████████████████████████",
            "       ██████████████████████████████████",
            "           ██████████████████████████",
            "           ██████████████████████████",
            "            █          ██          █",
            "            ████████████████████████",
            "             ██████████████████████",
            "              ████████████████████",
            "            ██  ████████████████  ██",
            "                ████████████████",
            "                 ████      ████",
            "               ██  ███    ███  ██",
            "                    ████████"
        ]
        logo_text = Text("\n".join(logo_lines), style="red")
        
        try:
            mode = requests.get(f"{self.base_url}/config").json().get("narrat_mode", "unknown")
        except: mode = "unknown"

        description = f"""
[bold white]Narrat Writer[/bold white]

A CLI-based development environment for writing and playing visual novels. 
Experience immersive storytelling, dynamic AI generation, and real-time script editing.

[dim]Version 0.2.0 | Mode: {mode.capitalize()}[/dim]
        """
        
        # Group both elements and center them individually within the group's container
        intro_content = Group(
            Align.center(logo_text),
            Text("\n"), # Added two-line margin
            Align.center(Text.from_markup(description.strip()))
        )
        
        layout["left"].update(Panel(Align.center(intro_content, vertical="middle"), border_style="cyan"))
        
        menu_text = ""
        if options:
            for i, opt in enumerate(options):
                if i == selected_idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
        layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Main Menu", border_style="yellow"))
        return layout

    def run(self):
        """Primary Launcher loop handling top-level navigation with persistent Live context."""
        options = ["Create Game", "Select Game", "Options", "Exit"]
        input_obj = create_input()
        idx = 0
        
        with Live(self.display_intro(options, idx), screen=True, auto_refresh=False) as live:
            with input_obj.raw_mode():
                while True:
                    live.update(self.display_intro(options, idx)); live.refresh()
                    keys = input_obj.read_keys()
                    if not keys:
                        if os.getenv("NARRAT_TEST_MODE") != "1":
                            time.sleep(0.05)
                        continue
                    
                    choice = None
                    for key in keys:
                        if key.key == Keys.Up: idx = (idx - 1) % len(options)
                        elif key.key == Keys.Down: idx = (idx + 1) % len(options)
                        elif key.key == Keys.Enter or key.key == Keys.ControlM:
                            choice = options[idx]
                        elif key.key == Keys.Escape: return
                        elif key.key == Keys.ControlC: sys.exit()
                    
                    if choice:
                        if choice == "Exit": sys.exit()
                        elif choice == "Create Game":
                            live.stop(); self.create_game_flow(); live.start()
                        elif choice == "Select Game":
                            self.select_game_flow_shared(live, input_obj)
                        elif choice == "Options":
                            self.global_options_flow_shared(live, input_obj)

    def create_game_flow(self):
        """Interactive game scaffolding flow (AI or Manual)."""
        console.clear()
        console.print(Panel("[bold yellow]Create New Game[/bold yellow]", border_style="yellow"))
        
        method = questionary.select(
            "Choose Creation Method",
            choices=["AI Assisted", "Manual", "Back"]
        ).ask()
        
        if method == "Back" or method is None: return

        title = questionary.text("Game Title").ask()
        if not title: return

        # Auto-generate Game ID
        words = re.findall(r'\w+', title.lower())
        base_id = "_".join(words[:2]) if words else "new_game"
        
        # Check for existence and unique ID
        res = requests.get(f"{self.base_url}/games")
        existing_ids = [g["id"] for g in res.json().get("games", [])]
        
        game_id = base_id
        counter = 2
        while game_id in existing_ids:
            game_id = f"{base_id}_{counter}"
            counter += 1

        res_config = requests.get(f"{self.base_url}/config")
        editor = res_config.json().get("editor")
        use_external = editor and editor != "None"

        if method == "AI Assisted":
            console.print("\n[bold cyan]AI Guidance:[/bold cyan]")
            console.print("Describe your game idea. Include [italic]Genre, Setting, Characters, and Plot hooks.[/italic]")
            
            if use_external:
                console.print("\n[yellow]Opening external editor for your prompt...[/yellow]")
                time.sleep(0.3)
                from src.terminal_client.utils import edit_text_in_external_editor
                prompt = edit_text_in_external_editor("")
            else:
                prompt = questionary.text("Enter your prompt").ask()

            if not prompt: return
            
            while True:
                with console.status(f"[bold green]AI is scaffolding '{game_id}'...[/bold green]"):
                    res = requests.post(f"{self.base_url}/games/create", json={"name": game_id, "prompt": prompt})
                
                if res.status_code == 200:
                    console.print(f"[green]Game '{game_id}' created successfully![/green]")
                    from src.terminal_client.screens.hub import GameHub
                    hub = GameHub(self.console, self.base_url)
                    hub.run(game_id)
                    return
                else:
                    error_detail = res.json().get('detail', 'Unknown error')
                    console.print(Panel(f"[red]Error:[/red] {error_detail}", title="Generation Failed", border_style="red"))
                    action = questionary.select("Action", choices=["Retry", "Edit prompt", "Back"]).ask()
                    if action == "Back" or action is None: return
                    if action == "Edit prompt":
                        if use_external:
                            console.print("\n[yellow]Opening external editor...[/yellow]")
                            time.sleep(0.3)
                            prompt = edit_text_in_external_editor(prompt)
                        else:
                            prompt = questionary.text("Prompt", default=prompt).ask()
        else:
            if use_external:
                console.print("\n[yellow]Opening external editor for game summary...[/yellow]")
                time.sleep(0.3)
                from src.terminal_client.utils import edit_text_in_external_editor
                summary = edit_text_in_external_editor("")
            else:
                summary = questionary.text("Game Summary").ask()
            
            if summary is None: return
            
            with console.status(f"[bold green]Creating '{game_id}'...[/bold green]"):
                res = requests.post(f"{self.base_url}/games/create", json={"name": game_id, "manual_data": {"title": title, "summary": summary, "genre": "Custom"}})
            
            if res.status_code == 200:
                console.print(f"[green]Game '{game_id}' created successfully![/green]")
                from src.terminal_client.screens.hub import GameHub
                hub = GameHub(self.console, self.base_url)
                hub.run(game_id)
            else:
                console.print(f"[red]Error: {res.json().get('detail', 'Unknown error')}[/red]")
                questionary.press_any_key_to_continue().ask()

    def select_game_flow(self):
        # Compatibility wrapper
        with Live(None, screen=True, auto_refresh=False) as live:
            self.select_game_flow_shared(live, create_input())

    def select_game_flow_shared(self, live, input_obj):
        """Interactive game selection flow with live preview using shared Live context."""
        res = requests.get(f"{self.base_url}/games")
        games = res.json()["games"]
        if not games:
            live.stop()
            questionary.text("No games found. [Enter] to continue").ask()
            live.start(); return
        
        def render_select(options, idx, games=games):
            layout = make_intro_layout()
            if idx < len(games):
                g = games[idx]
                info = f"[bold cyan]{g['title']}[/bold cyan]\n\n"
                info += f"{g['summary']}\n\n"
                info += f"[bold white]Genre:[/bold white] {g.get('genre', 'Unknown')}\n"
                chars = g.get('characters', [])
                cap_chars = [c.capitalize() for c in chars]
                info += f"[bold white]Characters:[/bold white] {', '.join(cap_chars) if cap_chars else 'None'}\n\n"
                plot = g.get('plot_outline', '')
                if plot: info += f"[bold white]Plot Outline:[/bold white]\n{plot[:300]}{'...' if len(plot) > 300 else ''}"
            else: info = "[dim italic]Back to main menu.[/dim italic]"
            layout["left"].update(Panel(Align.left(info, vertical="middle"), border_style="cyan", padding=(1, 3)))
            
            menu_text = ""
            for i, opt in enumerate(options):
                if i == idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Select Game", border_style="yellow"))
            return layout

        menu_options = [g["title"] for g in games] + ["Back"]
        title_to_id = {g["title"]: g["id"] for g in games}
        idx = 0
        
        while True:
            live.update(render_select(menu_options, idx)); live.refresh()
            keys = input_obj.read_keys()
            if not keys:
                time.sleep(0.05); continue
            
            choice = None
            for key in keys:
                if key.key == Keys.Up: idx = (idx - 1) % len(menu_options)
                elif key.key == Keys.Down: idx = (idx + 1) % len(menu_options)
                elif key.key == Keys.Enter or key.key == Keys.ControlM: choice = menu_options[idx]
                elif key.key == Keys.Escape: return
            
            if choice:
                if choice == "Back": return
                game_id = title_to_id[choice]
                live.stop()
                from src.terminal_client.screens.hub import GameHub
                hub = GameHub(self.console, self.base_url)
                hub.run(game_id)
                live.start(); return

    def global_options_flow(self):
        # Compatibility wrapper
        with Live(None, screen=True, auto_refresh=False) as live:
            self.global_options_flow_shared(live, create_input())

    def global_options_flow_shared(self, live, input_obj):
        """Settings menu for application-wide configuration using shared Live context."""
        state = {"mode": "view", "field": None, "sub_options": [], "sub_idx": 0, "input_val": "", "main_idx": 0}
        main_options = ["Edit API Settings", "Select Model", "Change Mode", "Select Editor", "Edit Prompt Prefix", "Back"]

        def render_options(config, state):
            layout = make_intro_layout()
            if state["mode"] == "view":
                info = f"[bold cyan]Global Configuration[/bold cyan]\n\n"
                info += f"[bold white]API URL:[/bold white] {config.get('api_url')}\n"
                info += f"[bold white]Model:[/bold white] {config.get('model')}\n"
                info += f"[bold white]Mode:[/bold white] {config.get('narrat_mode')}\n"
                info += f"[bold white]Editor:[/bold white] {config.get('editor') or 'None'}\n"
                info += f"[bold white]Prompt Prefix:[/bold white] {config.get('global_prompt_prefix', 'None')}\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Settings Preview", border_style="cyan"))
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
            elif state["mode"] == "testing":
                info = f"[bold blue]Testing API Connection...[/bold blue]\n\n"
                info += f"[dim]Contacting {config.get('api_url')}...[/dim]\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="API Test", border_style="blue"))
            elif state["mode"] == "loading":
                info = f"[bold yellow]Loading {state['field']}...[/bold yellow]\n\n"
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Please Wait", border_style="yellow"))

            menu_text = ""
            for i, opt in enumerate(main_options):
                if i == state["main_idx"]: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Global Options", border_style="yellow"))
            return layout

        while True:
            res = requests.get(f"{self.base_url}/config"); config = res.json()
            live.update(render_options(config, state)); live.refresh()
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
                        elif choice == "Edit API Settings":
                            live.stop(); self.edit_api_flow_inline(config, state, render_options); live.start()
                        elif choice == "Select Model":
                            state["mode"], state["field"] = "loading", "Models"
                            live.update(render_options(config, state)); live.refresh()
                            m_res = requests.get(f"{self.base_url}/config/models")
                            models = m_res.json().get("models", [])
                            if not models:
                                state["mode"] = "view"; live.stop()
                                if questionary.confirm("Manual entry?").ask():
                                    nm = questionary.text("Model ID").ask()
                                    if nm: requests.post(f"{self.base_url}/config", json={"model": nm})
                                live.start()
                            else: state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", "Model", models + ["Back"], 0
                        elif choice == "Change Mode": state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", "Mode", ["play", "writer", "developer", "Back"], 0
                        elif choice == "Select Editor": state["mode"], state["field"], state["sub_options"], state["sub_idx"] = "select", "Editor", ["vim", "nano", "code", "subl", "None", "Back"], 0
                        elif choice == "Edit Prompt Prefix":
                            editor = config.get("editor", "")
                            live.stop()
                            if editor and editor != "None":
                                nv = edit_text_in_external_editor(config.get("global_prompt_prefix", ""))
                            else: nv = questionary.text("New Prefix", default=config.get("global_prompt_prefix", "")).ask()
                            if nv is not None: requests.post(f"{self.base_url}/config", json={"global_prompt_prefix": nv})
                            live.start()
                    elif state["mode"] == "select":
                        selection = state["sub_options"][state["sub_idx"]]
                        field = state["field"]; state["mode"] = "view"
                        if selection != "Back":
                            payload = {}
                            if field == "Model": payload["model"] = selection
                            elif field == "Mode": payload["narrat_mode"] = selection
                            elif field == "Editor":
                                if selection != "None" and not shutil.which(selection):
                                    live.stop(); console.print(f"[red]Error: {selection} not found.[/red]"); time.sleep(2); live.start()
                                    state["mode"] = "select" # Stay
                                else: payload["editor"] = "" if selection == "None" else selection
                            if payload: requests.post(f"{self.base_url}/config", json=payload)
                elif key.key == Keys.Escape:
                    if state["mode"] != "view": state["mode"] = "view"
                    else: return

    def edit_api_flow_inline(self, config, state, render_options):
        url, key = config.get("api_url", ""), config.get("api_key", "")
        while True:
            state["mode"], state["field"], state["input_val"] = "input", "API URL", url
            console.clear(); console.print(render_options(config=config, state=state))
            url = questionary.text("API URL", default=url).ask()
            if not url: break
            
            state["field"], state["input_val"] = "API Key", "********"
            console.clear(); console.print(render_options(config=config, state=state))
            key = questionary.password("API Key", default=key).ask()
            if not key: break
            
            state["mode"] = "testing"
            console.clear(); console.print(render_options(config=config, state=state))
            try:
                res = requests.post(f"{self.base_url}/config/test", json={"api_url": url, "api_key": key})
                if res.status_code == 200:
                    data = res.json()
                    console.print("[green]✓ API Connection Succeeded![/green]")
                    models = data.get("models", [])
                    update_payload = {"api_url": url, "api_key": key}
                    if models: update_payload["model"] = models[0]
                    requests.post(f"{self.base_url}/config", json=update_payload)
                    time.sleep(1); break
                else: raise Exception(res.json().get("detail", "Unknown Error"))
            except Exception as e:
                console.print(f"[red]✗ API Test Failed: {e}[/red]")
                if not questionary.confirm("Retry?").ask(): break
        state["mode"] = "view"
