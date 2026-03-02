import requests
import sys
import time
import questionary
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.console import Group
from src.terminal_client.utils import (
    console, BASE_URL, make_intro_layout, get_menu_choice
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
        """Primary Launcher loop handling top-level navigation."""
        options = ["Create Game", "Select Game", "Options", "Exit"]
        while True:
            choice = get_menu_choice(options, self.display_intro)
            if choice == "Exit" or choice is None: sys.exit()
            elif choice == "Create Game": self.create_game_flow()
            elif choice == "Select Game": self.select_game_flow()
            elif choice == "Options": self.global_options_flow()

    def create_game_flow(self):
        """Interactive game scaffolding flow (AI or Manual)."""
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

        game_id = questionary.text("Enter unique Game ID (no spaces)").ask()
        if not game_id: return
        
        if method == "AI Assisted":
            console.print("\n[bold cyan]AI Guidance:[/bold cyan]")
            console.print("Describe your game idea. Include [italic]Genre, Setting, Characters, and Plot hooks.[/italic]")

            prompt_method = questionary.select("How to enter prompt?", choices=["Inline", "External Editor", "Back"]).ask()
            if prompt_method == "Back" or prompt_method is None: return

            if prompt_method == "Inline":
                prompt = questionary.text("Enter your prompt").ask()
            else:
                from src.terminal_client.utils import edit_text_in_external_editor
                prompt = edit_text_in_external_editor("")

            if not prompt: return
            
            while True:
                with console.status("[bold green]AI is scaffolding your game...[/bold green]"):
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
                    
                    action = questionary.select(
                        "What would you like to do?",
                        choices=["Retry same prompt", "Edit prompt", "Back to menu"]
                    ).ask()
                    
                    if action == "Back to menu" or action is None: return
                    if action == "Edit prompt":
                        prompt = questionary.text("Enter new prompt").ask()
        else:
            title = questionary.text("Game Title").ask()
            summary = questionary.text("Game Summary").ask()
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
        """Interactive game selection flow with live preview."""
        res = requests.get(f"{self.base_url}/games")
        games = res.json()["games"]
        if not games:
            questionary.text("No games found. [Enter] to continue").ask()
            return
        
        def render_select(options, idx, games=games):
            layout = make_intro_layout()
            if idx < len(games):
                g = games[idx]
                info = f"[bold cyan]{g['title']}[/bold cyan]\n\n{g['summary']}"
            else: info = "[dim]Back to main menu.[/dim]"
            layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Game Preview", border_style="cyan"))
            menu_text = ""
            for i, opt in enumerate(options):
                if i == idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                else: menu_text += f"  {opt}\n"
            layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Select Game", border_style="yellow"))
            return layout

        options = [g["id"] for g in games] + ["Back"]
        choice = get_menu_choice(options, render_select)
        if choice and choice != "Back":
            from src.terminal_client.screens.hub import GameHub
            hub = GameHub(self.console, self.base_url)
            hub.run(choice)

    def global_options_flow(self):
        """Settings menu for application-wide configuration."""
        while True:
            res = requests.get(f"{self.base_url}/config")
            config = res.json()
            
            def render_options(opts, idx, config=config):
                layout = make_intro_layout()
                info = f"[bold cyan]Global Configuration[/bold cyan]\n\n"
                info += f"[bold white]API URL:[/bold white] {config.get('api_url')}\n"
                info += f"[bold white]Model:[/bold white] {config.get('model')}\n"
                info += f"[bold white]Mode:[/bold white] {config.get('narrat_mode')}\n"
                info += f"[bold white]Editor:[/bold white] {config.get('editor', 'vim')}\n"
                info += f"[bold white]Prompt Prefix:[/bold white] {config.get('global_prompt_prefix', 'None')}\n"
                
                layout["left"].update(Panel(Align.center(info, vertical="middle"), title="Settings Preview", border_style="cyan"))
                
                menu_text = ""
                for i, opt in enumerate(opts):
                    if i == idx: menu_text += f"> [bold yellow]{opt}[/bold yellow]\n"
                    else: menu_text += f"  {opt}\n"
                layout["right"].update(Panel(Align.center(menu_text, vertical="middle"), title="Global Options", border_style="yellow"))
                return layout

            options = ["Edit API Settings", "Select Model", "Change Mode", "Select Editor", "Edit Prompt Prefix", "Back"]
            choice = get_menu_choice(options, render_options)
            
            if choice == "Back" or choice is None: break
            
            if choice == "Edit API Settings":
                self.edit_api_flow(config)
            elif choice == "Select Model":
                res = requests.get(f"{self.base_url}/config/models")
                models = res.json().get("models", [])
                if not models:
                    console.print("[yellow]Could not fetch models from API. Enter manually?[/yellow]")
                    if questionary.confirm("Manual entry?").ask():
                        nm = questionary.text("Model ID").ask()
                        if nm: requests.post(f"{self.base_url}/config", json={"model": nm})
                else:
                    nm = questionary.select("Select Model", choices=models + ["Back"]).ask()
                    if nm and nm != "Back":
                        requests.post(f"{self.base_url}/config", json={"model": nm})
            elif choice == "Change Mode":
                nm = questionary.select("Select Mode", choices=["play", "writer", "developer", "Back"]).ask()
                if nm and nm != "Back":
                    requests.post(f"{self.base_url}/config", json={"narrat_mode": nm})
            elif choice == "Select Editor":
                new_editor = questionary.select("Choose your editor", choices=["vim", "nano", "code", "subl", "None", "Back"]).ask()
                if new_editor and new_editor != "Back":
                    requests.post(f"{self.base_url}/config", json={"editor": new_editor})
            elif choice == "Edit Prompt Prefix":
                editor = config.get("editor", "None")
                current_prefix = config.get("global_prompt_prefix", "")
                if editor and editor != "None":
                    from src.terminal_client.utils import edit_text_in_external_editor
                    new_prefix = edit_text_in_external_editor(current_prefix)
                else:
                    new_prefix = questionary.text("Enter new global prompt prefix", default=current_prefix).ask()
                
                if new_prefix is not None:
                    requests.post(f"{self.base_url}/config", json={"global_prompt_prefix": new_prefix})

    def edit_api_flow(self, current_config):
        url = current_config.get("api_url", "")
        key = current_config.get("api_key", "")
        
        while True:
            url = questionary.text("API URL", default=url).ask()
            key = questionary.password("API Key", default=key).ask()
            
            if not url or not key: break
            
            with console.status("[bold green]Testing API Connection...[/bold green]"):
                try:
                    res = requests.post(f"{self.base_url}/config/test", json={"api_url": url, "api_key": key})
                    if res.status_code == 200:
                        data = res.json()
                        console.print("[green]✓ API Connection Succeeded![/green]")
                        models = data.get("models", [])
                        update_payload = {"api_url": url, "api_key": key}
                        if models:
                            update_payload["model"] = models[0]
                            console.print(f"[dim]Defaulted model to: {models[0]}[/dim]")
                        
                        requests.post(f"{self.base_url}/config", json=update_payload)
                        time.sleep(1)
                        break
                    else:
                        raise Exception(res.json().get("detail", "Unknown Error"))
                except Exception as e:
                    console.print(f"[red]✗ API Test Failed: {e}[/red]")
                    if not questionary.confirm("Retry?").ask(): break
