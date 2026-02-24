# Headless Narrat

A CLI-based development and writing environment for [Narrat](https://narrat.dev/) visual novels. 

This project provides a FastAPI backend and a `rich`-powered Python client that allows you to write, test, and dynamically expand `.narrat` scripts directly from your terminal.

## Key Features

- **Live Parser & Player:** Play your `.narrat` scripts in a stylized terminal dashboard.
- **Session State Management:** Automatically saves progress to session-specific JSON files. Supports **Undo/Back (B)** and **Live Reload (R)** to instantly test script changes.
- **AI-Powered Story Expansion:** If a choice leads to a missing label, the system uses the **GLM-4.7 API** to autonomously generate and append new story branches, including metadata for new backgrounds and characters.
- **Dynamic Reference Library:** Context-aware UI that pulls character profiles, physical descriptions, and background details from a structured `/reference` folder.
- **Rich Terminal UI:** A multi-block layout displaying:
    - **Descriptions:** Background and character lore + active scene/animation events.
    - **Current State:** Active label and recent variable updates.
    - **Dialogue:** Immersive character speech with emotion tracking (`set_expression`).
- **Narrat Expression Support:** Evaluate complex logic like `if (> $data.security_level 50):`.

## Project Structure

- `main.py`: FastAPI backend handling parsing, state, and AI logic.
- `client.py`: `rich` CLI client for playing the game.
- `narrat_syntax.md`: Reference file for supported Narrat syntax.
- `/reference`: Folder for story assets (backgrounds, characters, scenes, animations).
- `phase1.narrat`: The entry point for your script.
- `config.json`: API configuration for AI generation.

## Getting Started

1. **Install Dependencies:**
   ```bash
   pip install fastapi uvicorn rich requests
   ```

2. **Configure AI (Optional):**
   Update `config.json` with your GLM API key to enable autonomous story generation.

3. **Start the API:**
   ```bash
   python main.py
   ```

4. **Start the Client:**
   ```bash
   python client.py my_session_name
   ```

## Narrat Syntax Support
- `label [name]:`
- `talk [character_id] "[text]"`
- `choice:` blocks with `label: "Text" -> target`
- `set [var] [value]`
- `if (operator operand1 operand2):`
- `background [bg_id]`, `scene [scene_id]`, `play_animation [anim_id]`
- `set_expression [char_id] [emotion]`
