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

# --- UI COMPONENTS ---

def make_layout(show_script=False) -> Layout:
    layout = Layout()
    if show_script:
        layout.split_row(Layout(name="main_col", ratio=7), Layout(name="script_col", ratio=3))
        layout["main_col"].split_column(Layout(name="upper", ratio=35), Layout(name="dialogue", ratio=35), Layout(name="lower", ratio=30))
    else:
        layout.split_column(Layout(name="upper", ratio=35), Layout(name="dialogue", ratio=35), Layout(name="lower", ratio=30))
    
    target = layout["main_col"] if show_script else layout
    target["upper"].split_row(Layout(name="descriptions", ratio=1), Layout(name="state", ratio=1))
    return layout

def get_descriptions_panel(data):
    anim = data.get("active_animation")
    scene = data.get("active_scene")
    if anim:
        return Panel(f"[bold magenta]ANIMATION: {anim['name']}[/bold magenta]\n\n{anim['content']}", title="Active Animation", border_style="magenta")
    if scene:
        return Panel(f"[bold green]SCENE: {scene['name']}[/bold green]\n\n{scene['content']}", title="Active Scene", border_style="green")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold cyan]BG:[/bold cyan]", f"[italic]{data.get('background', 'None')}[/italic]")
    table.add_row("", f"[dim]{data.get('background_desc', 'No description.')}[/dim]")
    if data.get("character"):
        char = data["character"]
        meta = data.get("meta", {})
        table.add_row("[bold yellow]CHAR:[/bold yellow]", f"[bold]{char}[/bold] [italic]({meta.get('emotion', 'Neutral')})[/italic]")
        table.add_row("", f"[dim]{meta.get('description', 'No description.')}[/dim]")
    return Panel(table, title="Descriptions", border_style="blue")

def get_state_panel(data):
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold green]Label:[/bold green]", data.get("current_label", "Unknown"))
    vars_dict = data.get("variables", {})
    updated_vars = vars_dict.get("__updated_vars", [])
    table.add_row("", "")
    table.add_row("[bold]Recent Variables:[/bold]", "")
    if not updated_vars:
        table.add_row("", "[dim]No variables updated yet.[/dim]")
    else:
        for var in reversed(updated_vars):
            table.add_row(f"  {var}:", str(vars_dict.get(var)))
    return Panel(table, title="Current State", border_style="green")

def get_script_panel(data):
    try:
        with open("phase1.narrat", "r") as f:
            lines = f.readlines()
    except: return Panel("Script file not found.", title="Script Viewer", border_style="red")

    current_label = data.get("current_label", "")
    target_line_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(f"label {current_label}:"):
            target_line_idx = i + data.get("line_index", 0)
            break

    render_height = console.height - 8
    start = max(0, target_line_idx - (render_height // 2))
    end = min(len(lines), start + render_height)
    table = Table(show_header=False, box=None, padding=(0, 1), collapse_padding=True)
    table.add_column("num", justify="right", style="dim cyan", width=4)
    table.add_column("content")
    for i in range(start, end):
        line_num = str(i + 1)
        line_content = lines[i].rstrip()
        if i == target_line_idx:
            table.add_row(f"[bold cyan]{line_num}[/bold cyan]", Text(f"> {line_content}", style="bold white on grey15"))
        else: table.add_row(line_num, line_content)
    return Panel(table, title=f"Script: phase1.narrat", border_style="white", padding=(1, 1))

def display_game(data, show_script=False):
    layout = make_layout(show_script)
    main_view = layout["main_col"] if show_script else layout
    if show_script: layout["script_col"].update(get_script_panel(data))
    
    main_view["descriptions"].update(get_descriptions_panel(data))
    main_view["state"].update(get_state_panel(data))
    
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
        line = styles[i].format(char=entry['character'], text=entry['text'])
        dialogue_lines.insert(0, line)
        
    render_height = console.height - 3
    dialogue_box_height = int(render_height * 0.35) - 2
    total_text_lines = sum(len(line.split("\n")) + 1 for line in dialogue_lines)
    num_newlines = max(0, dialogue_box_height - total_text_lines - 1)
    
    main_view["dialogue"].update(Panel(("\n" * num_newlines) + "\n\n".join(dialogue_lines), title="Dialogue", border_style="cyan"))

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
    
    main_view["lower"].update(Panel(sys_content, title="System / Choices", border_style="yellow"))

    console.clear()
    console.print("\n")
    console.print(layout, height=render_height)

# --- EDIT LOGIC ---

def get_current_line_idx(data):
    with open("phase1.narrat", "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(f"label {data['current_label']}:"):
            return i + data.get("line_index", 0)
    return None

def handle_edit(session_id, data):
    line_idx = get_current_line_idx(data)
    if line_idx is None:
        console.print("[red]Could not determine current script position.[/red]")
        return
    
    edit_type = Prompt.ask("\n[bold blue]Edit:[/bold blue] [1] Background | [2] Character | [3] Dialogue | [4] Choice | [5] Scene | [B]ack", choices=["1", "2", "3", "4", "5", "B", "b"])
    if edit_type.upper() == "B": return

    if edit_type == "1": # Background
        # Select what to edit: Name or Description
        bg_part = Prompt.ask("  Edit [1] BG Name/ID | [2] BG Description", choices=["1", "2", "B", "b"])
        if bg_part == "1":
            opt = Prompt.ask("  [bold]BG Name:[/bold] [C]lear | C[H]oose | [R]egenerate | [S]ave | [A]dd | [B]ack", choices=["C", "H", "R", "S", "A", "B", "c", "h", "r", "s", "a", "b"])
            if opt.upper() == "B": return
            if opt.upper() == "H": # Choose
                assets = requests.get(f"{BASE_URL}/assets/backgrounds").json()["assets"]
                choice = Prompt.ask("  Select BG", choices=assets + ["B"])
                if choice != "B":
                    requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx), "content": f"background {choice}"})
            elif opt.upper() == "A": # Add
                name = Prompt.ask("  New BG ID")
                desc = Prompt.ask("  New BG Description")
                requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "background", "target": name, "content": desc})
                requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx), "content": f"background {name}"})
        elif bg_part == "2":
            bg_id = data.get("background", "None")
            new_desc = Prompt.ask(f"  New Description for {bg_id}")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "background", "target": bg_id, "content": new_desc})

    elif edit_type == "3": # Dialogue
        opt = Prompt.ask("  [bold]Dialogue:[/bold] [C]lear | [R]egenerate | C[H]aracter | [I]nsert | [S]ave | [B]ack", choices=["C", "R", "H", "I", "S", "B", "c", "r", "h", "i", "s", "b"])
        if opt.upper() == "B": return
        if opt.upper() == "S": # Save (Manual Edit)
            new_text = Prompt.ask("  New Dialogue Text")
            char = data.get("character", "narrator")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx), "content": f"talk {char} \"{new_text}\""})
        elif opt.upper() == "I": # Insert
            new_text = Prompt.ask("  Insert Dialogue Text After")
            char = data.get("character", "narrator")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "insert", "target": str(line_idx), "content": f"talk {char} \"{new_text}\""})
        elif opt.upper() == "H": # Change Character
            assets = requests.get(f"{BASE_URL}/assets/characters").json()["assets"]
            choice = Prompt.ask("  Select Character", choices=assets + ["B"])
            if choice != "B":
                old_text = data.get("text", "")
                requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx), "content": f"talk {choice} \"{old_text}\""})

    elif edit_type == "2": # Character
        char_part = Prompt.ask("  Edit [1] Profile | [2] Description | [3] Emotion | [4] Switch/Add Character", choices=["1", "2", "3", "4", "B", "b"])
        char_id = data.get("character")
        if char_part == "1":
            new_prof = Prompt.ask(f"  New Profile for {char_id}")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "character", "target": char_id, "content": new_prof, "meta": {"type": "profile"}})
        elif char_part == "2":
            new_desc = Prompt.ask(f"  New Description for {char_id}")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "character", "target": char_id, "content": new_desc, "meta": {"type": "description"}})
        elif char_part == "3":
            new_emo = Prompt.ask("  New Emotion/Expression name")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "insert", "target": str(line_idx-1), "content": f"set_expression {char_id} {new_emo}"})
        elif char_part == "4":
            assets = requests.get(f"{BASE_URL}/assets/characters").json()["assets"]
            choice = Prompt.ask("  Select Character to switch to (or type new ID)", choices=assets + ["B"])
            if choice != "B":
                requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx), "content": f"talk {choice} \"{data.get('text', '')}\""})

    elif edit_type == "4": # Choice
        if data["type"] != "choice":
            console.print("[red]Not currently on a choice line.[/red]")
            return
        opt = Prompt.ask("  [1] Add Choice | [2] Edit Existing | [3] Remove Choice", choices=["1", "2", "3", "B", "b"])
        if opt == "1":
            txt = Prompt.ask("  Option Text")
            tgt = Prompt.ask("  Target Label")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "insert", "target": str(line_idx), "content": f'label: "{txt}" -> {tgt}'})
        elif opt == "2":
            idx_list = [str(k) for k in data["options"].keys()]
            c_idx = int(Prompt.ask("  Choice Number to Edit", choices=idx_list))
            new_txt = Prompt.ask("  New Option Text", default=data["options"][c_idx]["text"])
            new_tgt = Prompt.ask("  New Target Label", default=data["options"][c_idx]["target"])
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx + c_idx), "content": f'label: "{new_txt}" -> {new_tgt}'})

    elif edit_type == "5": # Scene
        scene_part = Prompt.ask("  Edit [1] Scene Name | [2] Scene Description", choices=["1", "2", "B", "b"])
        if scene_part == "1":
            assets = requests.get(f"{BASE_URL}/assets/scenes").json()["assets"]
            choice = Prompt.ask("  Select Scene", choices=assets + ["B"])
            if choice != "B":
                requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "script", "action": "update", "target": str(line_idx), "content": f"scene {choice}"})
        elif scene_part == "2":
            scene_id = data.get("active_scene", {}).get("name", "None")
            if scene_id == "None":
                scene_id = Prompt.ask("  No active scene. Enter Scene ID to edit")
            new_desc = Prompt.ask(f"  New Description for {scene_id}")
            requests.post(f"{BASE_URL}/session/{session_id}/edit", json={"category": "reference", "action": "update", "sub_category": "scene", "target": scene_id, "content": new_desc})

    console.print("[green]Action committed. Reload [R] to see changes.[/green]")
        

# --- MAIN LOOP ---

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
        if data["type"] == "end": break
            
        if data["type"] == "missing_label":
            target = data["meta"]["target"]
            gen = Prompt.ask("\n[bold yellow]Generate this label with AI?[/bold yellow] (Y/N)", choices=["Y", "N", "y", "n"])
            if gen.upper() == "Y":
                with console.status("[bold green]Generating...[/bold green]"):
                    requests.post(f"{BASE_URL}/session/{session_id}/generate", json={"target": target})
                cmd = "R"
            else: cmd = "B"
        else:
            prompt_text = "\n[bold green][Enter] Next | [V]iew Script | [R]eload | [B]ack | [E]dit | E[X]it[/bold green]"
            if data["type"] == "choice":
                prompt_text = "\n[bold green][Number] Choose | [V]iew Script | [R]eload | [B]ack | [E]dit | E[X]it[/bold green]"
            cmd = Prompt.ask(prompt_text)
        
        if cmd.upper() == "X": break
        if cmd.upper() == "V":
            show_script = not show_script
            continue
        if cmd.upper() == "E":
            handle_edit(session_id, data)
            # Immediately refresh the view
            response = requests.post(f"{BASE_URL}/session/{session_id}/step", json={"command": "REFRESH"})
            data = response.json()
            continue
        
        try:
            response = requests.post(f"{BASE_URL}/session/{session_id}/step", json={"command": cmd.upper() if cmd else " "})
            data = response.json()
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            break

if __name__ == "__main__":
    main()
