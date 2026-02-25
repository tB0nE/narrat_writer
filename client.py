import sys
import requests
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.layout import Layout
from rich.table import Table
from rich.text import Text

console = Console()
BASE_URL = "http://localhost:8045"
SHOW_SCRIPT = False

def make_layout(show_script=False) -> Layout:
    layout = Layout()
    if show_script:
        layout.split_row(
            Layout(name="main_col", ratio=7),
            Layout(name="script_col", ratio=3)
        )
        layout["main_col"].split_column(
            Layout(name="upper", ratio=35),
            Layout(name="dialogue", ratio=35),
            Layout(name="lower", ratio=30)
        )
    else:
        layout.split_column(
            Layout(name="upper", ratio=35),
            Layout(name="dialogue", ratio=35),
            Layout(name="lower", ratio=30)
        )
    
    target = layout["main_col"] if show_script else layout
    target["upper"].split_row(
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

def get_script_panel(data):
    try:
        with open("phase1.narrat", "r") as f:
            lines = f.readlines()
    except:
        return Panel("Script file not found.", title="Script Viewer", border_style="red")

    current_label = data.get("current_label", "")
    target_line_idx = -1
    
    # Find the global line index
    for i, line in enumerate(lines):
        if line.strip().startswith(f"label {current_label}:"):
            target_line_idx = i + data.get("line_index", 0)
            break

    # Extract window of lines
    # We leave room for the panel borders
    render_height = console.height - 8
    start = max(0, target_line_idx - (render_height // 2))
    end = min(len(lines), start + render_height)
    
    table = Table(show_header=False, box=None, padding=(0, 1), collapse_padding=True)
    table.add_column("num", justify="right", style="dim cyan", width=4)
    table.add_column("content")

    for i in range(start, end):
        line_num = str(i + 1)
        line_content = lines[i].rstrip()
        
        # Highlight current line
        if i == target_line_idx:
            table.add_row(
                f"[bold cyan]{line_num}[/bold cyan]", 
                Text(f"> {line_content}", style="bold white on grey15")
            )
        else:
            table.add_row(line_num, line_content)

    return Panel(table, title=f"Script: phase1.narrat", border_style="white", padding=(1, 1))

def display_game(data, show_script=False):
    layout = make_layout(show_script)
    
    # Resolve target columns
    if show_script:
        layout["script_col"].update(get_script_panel(data))
        main = layout["main_col"]
    else:
        main = layout

    main["descriptions"].update(get_descriptions_panel(data))
    main["state"].update(get_state_panel(data))
    
    log = data.get("dialogue_log") or []
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
        
    render_height = console.height - 3
    dialogue_box_height = int(render_height * 0.35) - 2
    total_text_lines = sum(len(line.split("\n")) + 1 for line in dialogue_lines)
    num_newlines = max(0, dialogue_box_height - total_text_lines - 1)
    
    content = ("\n" * num_newlines) + "\n\n".join(dialogue_lines)
    main["dialogue"].update(Panel(content, title="Dialogue", border_style="cyan"))

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
    
    main["lower"].update(Panel(sys_content, title="System / Choices", border_style="yellow"))

    console.clear()
    console.print("\n")
    console.print(layout, height=render_height)

def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    show_script = True
    
    try:
        response = requests.post(f"{BASE_URL}/session/{session_id}/step", json={"command": "R"})
        data = response.json()
    except Exception as e:
        console.print(f"[bold red]Error connecting to API: {e}[/bold red]")
        return
    
    while True:
        display_game(data, show_script)
        
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
            prompt_text = "\n[bold green][Enter] Next | [V]iew Script | [R]eload | [B]ack | [E]xit[/bold green]"
            if data["type"] == "choice":
                prompt_text = "\n[bold green][Number] Choose | [V]iew Script | [R]eload | [B]ack | [E]xit[/bold green]"
            
            cmd = Prompt.ask(prompt_text)
        
        if cmd.upper() == "E":
            break
        if cmd.upper() == "V":
            show_script = not show_script
            continue # Re-render with new toggle
        
        try:
            response = requests.post(f"{BASE_URL}/session/{session_id}/step", json={"command": cmd.upper() if cmd else " "})
            data = response.json()
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            break

if __name__ == "__main__":
    main()
