# Plan: Modular Multi-File Script Architecture

## Overview
Transition from a monolithic script structure (`phase1.narrat`) to a modular system where content is organized into multiple files. This improves scalability, organization, and AI context precision.

## 1. Directory Structure
Each game will move from a single file to a `scripts/` folder:
- `games/{game_id}/scripts/main.narrat` (Entry point, orchestration)
- `games/{game_id}/scripts/chapters/` (Main story arc files)
- `games/{game_id}/scripts/quests/` (Side quests and optional content)
- `games/{game_id}/scripts/interactions/` (Character-specific scenes)

## 2. Server-Side Changes
- **Parser Update:** `NarratParser` must recursively scan the `scripts/` directory and build a global map of all labels.
- **Label Validation:** Ensure no duplicate labels exist across different files.
- **New Endpoints:**
    - `GET /games/{game_id}/scripts` - List all script files with metadata (type, size).
    - `POST /games/{game_id}/scripts` - Create a new script file from template.
    - `DELETE /games/{game_id}/scripts/{path}` - Delete a script file (with safety check).
    - `GET /games/{game_id}/scripts/{path}` - Fetch content of a specific file.

## 3. Terminal Client: Script Manager
Add a "Manage Scripts" section to the Game Hub:
- **File Browser:** A list of all files in the `scripts/` directory.
- **Categorized View:** Filter by Chapters, Quests, or Interactions.
- **Quick Actions:**
    - **Add New:** Select type -> Input ID -> Scaffold file with header.
    - **Edit:** Open in configured external editor.
    - **Rename:** Rename the file and update internal references (optional).
    - **Scan:** Detect labels and cross-file jumps.

## 4. AI Optimization
- **Localized Context:** When generating content for a specific file, the AI is only fed relevant context (e.g., character profiles + the current script file, rather than the entire game).
- **Orchestration Prompts:** New prompt types to help the AI write "jump" commands between different script files.

## 5. Migration Strategy
- Develop a utility to detect games using the legacy `phase1.narrat` and automatically move them to `scripts/main.narrat`.
- Update `Create Game` flow to scaffold the new directory structure by default.
