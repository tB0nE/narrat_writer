# Feature Plan: NARRATapi Launcher & Creator - [x] Phase 1-4 Completed

## Phase 1: Data Migration & Backend Refactor - [x] Done
- [x] Create `/games` directory structure.
- [x] Refactor `main.py` to accept `game_id` in every request (e.g., `/game/{game_id}/session/{session_id}/step`).
- [x] Update all file pathing to be relative to `games/{game_id}/`.

## Phase 2: Game Management API - [x] Done
- [x] **Endpoint:** `GET /games` (List all installed games).
- [x] **Endpoint:** `POST /create_game` 
    - Handles prompt -> AI JSON conversion.
    - Scaffolds folder, `phase1.narrat`, and metadata.
- [x] **Endpoint:** `GET /game/{game_id}/metadata` (Fetch title/summary).

## Phase 3: The Launcher (client.py) - [x] Done
- [x] Implement **Intro Screen** (70/30 layout).
- [x] Add **NarratAPI Logo** using Rich and custom ASCII art.
- [x] **Create Flow:**
    - AI: Prompt -> Loading State -> Metadata Summary Edit Page.
    - Manual: Input Name -> Summary -> Metadata Summary Edit Page.
- [x] **Select Flow:**
    - List Games -> Game Hub (Summary + New/Load options).

## Phase 4: Metadata Hub - [x] Done
- [x] Dedicated UI to view/edit `metadata.json` with 70/30 split.
- [x] Buttons to "Regenerate" specific sections using the AI.

## Phase 5: Polish - [x] Completed
- [x] Standardize shortcuts across Launcher and Game Engine. (Replaced by Arrow Menus)
- [x] Ensure `python client.py [game_id]` still bypasses launcher for power users.
