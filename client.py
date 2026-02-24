import sys
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.layout import Layout
from rich.table import Table

console = Console()
BASE_URL = "http://localhost:8045"

def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="upper", ratio=1),
        Layout(name="lower", ratio=1)
    )
    layout["upper"].split_row(
        Layout(name="descriptions", ratio=1),
        Layout(name="state", ratio=1)
    )
    return layout

def get_descriptions_panel(data):
    # Check for Animation or Scene first
    anim = data.get("active_animation")
    scene = data.get("active_scene")
    
    if anim:
        content = f"[bold magenta]ANIMATION: {anim['name']}[/bold magenta]\n\n{anim['content']}"
        return Panel(content, title="[bold]Active Animation[/bold]", border_style="magenta")
    
    if scene:
        content = f"[bold green]SCENE: {scene['name']}[/bold green]\n\n{scene['content']}"
        return Panel(content, title="[bold]Active Scene[/bold]", border_style="green")

    # Fallback to BG/Character table
    table = Table(show_header=False, box=None, padding=(0, 1))
    
    # Background
    bg_name = data.get("background", "None")
    bg_desc = data.get("background_desc", "No background set.")
    table.add_row("[bold cyan]BG:[/bold cyan]", f"[italic]{bg_name}[/italic]")
    table.add_row("", f"[dim]{bg_desc}[/dim]")
    
    # Character
    if data.get("character"):
        char = data["character"]
        meta = data.get("meta", {})
        emotion = meta.get("emotion", "Neutral")
        
        table.add_row("[bold yellow]CHAR:[/bold yellow]", f"[bold]{char}[/bold] [italic]({emotion})[/italic]")
        table.add_row("", f"[dim]{meta.get('description', 'No description.')}[/dim]")

    return Panel(table, title="[bold]Descriptions[/bold]", border_style="blue")

def get_state_panel(data):
    table = Table(show_header=False, box=None, padding=(0, 1))
    
    # Label
    label = data.get("current_label", "Unknown")
    table.add_row("[bold green]Label:[/bold green]", label)
    
    # Variables
    vars_dict = data.get("variables", {})
    updated_vars = vars_dict.get("__updated_vars", [])
    
    table.add_row("", "")
    table.add_row("[bold]Recent Variables:[/bold]", "")
    
    if not updated_vars:
        table.add_row("", "[dim]No variables updated yet.[/dim]")
    else:
        for var in reversed(updated_vars):
            val = vars_dict.get(var)
            table.add_row(f"  {var}:", str(val))

    return Panel(table, title="[bold]Current State[/bold]", border_style="green")

def display_game(data):
    layout = make_layout()
    
    # Fill Upper Blocks
    layout["descriptions"].update(get_descriptions_panel(data))
    layout["state"].update(get_state_panel(data))
    
    # Fill Lower Block (Dialogue)
    if data["type"] == "talk":
        char = data.get("character", "Narrator")
        text = data.get("text", "")
        dialogue_content = f"\n[bold yellow]{char}[/bold yellow]: {text}"
        layout["lower"].update(Panel(dialogue_content, title="Dialogue", border_style="cyan"))
    elif data["type"] == "choice":
        layout["lower"].update(Panel("\n[bold yellow]System:[/bold yellow] Waiting for choice...", title="Dialogue", border_style="cyan"))
    elif data["type"] == "missing_label":
        layout["lower"].update(Panel(f"\n[bold red]System:[/bold red] Label '{data['meta']['target']}' is missing!", title="Dialogue", border_style="red"))
    elif data["type"] == "end":
        layout["lower"].update(Panel(f"\n[bold red]{data['text']}[/bold red]", title="End", border_style="red"))

    console.clear()
    
    # Constrain height to leave room for choices (approx 6-8 lines)
    # This prevents the top blocks from being pushed off-screen
    display_height = max(10, console.height - 8)
    if data["type"] == "choice":
        display_height = max(10, console.height - (len(data["options"]) + 6))
        
    console.print(layout, height=display_height)
    
    # Choices (Outside layout for easier interaction)
    if data["type"] == "choice":
        console.print("\n[bold]Choices:[/bold]")
        for idx, opt in data["options"].items():
            console.print(f"  {idx}. {opt['text']}")

def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    
    try:
        response = requests.post(f"{BASE_URL}/session/{session_id}/step", json={"command": "R"})
        data = response.json()
    except Exception as e:
        console.print(f"[bold red]Error connecting to API: {e}[/bold red]")
        return
    
    while True:
        display_game(data)
        
        if data["type"] == "end":
            break
            
        if data["type"] == "missing_label":
            target = data["meta"]["target"]
            gen = Prompt.ask("\n[bold yellow]Generate this label with AI?[/bold yellow] (Y/N)", choices=["Y", "N", "y", "n"])
            if gen.upper() == "Y":
                with console.status("[bold green]Generating story branch...[/bold green]"):
                    requests.post(f"{BASE_URL}/session/{session_id}/generate", json={"target": target})
                cmd = "R"
            else:
                cmd = "B"
        else:
            prompt_text = "\n[bold green][Enter] Next | [R]eload | [B]ack | [E]xit[/bold green]"
            if data["type"] == "choice":
                prompt_text = "\n[bold green][Number] Choose | [R]eload | [B]ack | [E]xit[/bold green]"
            
            cmd = Prompt.ask(prompt_text)
        
        if cmd.upper() == "E":
            break
        
        try:
            response = requests.post(f"{BASE_URL}/session/{session_id}/step", json={"command": cmd.upper() if cmd else " "})
            data = response.json()
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            break

if __name__ == "__main__":
    main()
