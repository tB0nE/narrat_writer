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
        Layout(name="upper", ratio=35),    # 35%
        Layout(name="dialogue", ratio=35), # 35%
        Layout(name="lower", ratio=30)     # 30%
    )
    layout["upper"].split_row(
        Layout(name="descriptions", ratio=1),
        Layout(name="state", ratio=1)
    )
    return layout

def get_descriptions_panel(data):
    anim = data.get("active_animation")
    scene = data.get("active_scene")
    
    if anim:
        content = f"[bold magenta]ANIMATION: {anim['name']}[/bold magenta]\n\n{anim['content']}"
        return Panel(content, title="[bold]Active Animation[/bold]", border_style="magenta")
    
    if scene:
        content = f"[bold green]SCENE: {scene['name']}[/bold green]\n\n{scene['content']}"
        return Panel(content, title="[bold]Active Scene[/bold]", border_style="green")

    table = Table(show_header=False, box=None, padding=(0, 1))
    bg_name = data.get("background", "None")
    bg_desc = data.get("background_desc", "No background set.")
    table.add_row("[bold cyan]BG:[/bold cyan]", f"[italic]{bg_name}[/italic]")
    table.add_row("", f"[dim]{bg_desc}[/dim]")
    
    if data.get("character"):
        char = data["character"]
        meta = data.get("meta", {})
        emotion = meta.get("emotion", "Neutral")
        table.add_row("[bold yellow]CHAR:[/bold yellow]", f"[bold]{char}[/bold] [italic]({emotion})[/italic]")
        table.add_row("", f"[dim]{meta.get('description', 'No description.')}[/dim]")

    return Panel(table, title="[bold]Descriptions[/bold]", border_style="blue")

def get_state_panel(data):
    table = Table(show_header=False, box=None, padding=(0, 1))
    label = data.get("current_label", "Unknown")
    table.add_row("[bold green]Label:[/bold green]", label)
    
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
    
    layout["descriptions"].update(get_descriptions_panel(data))
    layout["state"].update(get_state_panel(data))
    
    log = data.get("dialogue_log", [])
    dialogue_lines = []
    reversed_log = list(reversed(log))
    
    styles = [
        "[bold yellow]{char}[/bold yellow]: [bold white]{text}[/bold white]",
        "[dim yellow]{char}[/dim yellow]: [grey42]{text}[/grey42]",
        "[grey30]{char}: {text}[/grey30]",
        "[grey15]{char}: {text}[/grey15]",
        "[grey11]{char}: {text}[/grey11]",
        "[grey3]{char}: {text}[/grey3]"
    ]

    for i in range(min(len(reversed_log), 6)):
        entry = reversed_log[i]
        style = styles[i]
        line = style.format(char=entry['character'], text=entry['text'])
        dialogue_lines.insert(0, line)
        
    # Fixed height calculation for the 35% dialogue area
    render_height = console.height - 3
    dialogue_box_height = int(render_height * 0.35) - 2
    total_text_lines = sum(len(line.split("\n")) + 1 for line in dialogue_lines)
    num_newlines = max(0, dialogue_box_height - total_text_lines - 1)
    
    content = ("\n" * num_newlines) + "\n\n".join(dialogue_lines)
    layout["dialogue"].update(Panel(content, title="Dialogue", border_style="cyan"))

    sys_content = ""
    if data["type"] == "missing_label":
        sys_content = f"\n[bold red]System: Label '{data['meta']['target']}' is missing![/bold red]"
    elif data["type"] == "choice":
        options_text = ["[bold yellow]Available Choices:[/bold yellow]"]
        for idx, opt in data["options"].items():
            options_text.append(f"  {idx}. {opt['text']}")
        sys_content = "\n" + "\n".join(options_text)
    elif data["type"] == "end":
        sys_content = f"\n[bold red]{data['text']}[/bold red]"
    
    layout["lower"].update(Panel(sys_content, title="System / Choices", border_style="yellow"))

    console.clear()
    console.print("\n") # Top Gap
    console.print(layout, height=render_height)

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
