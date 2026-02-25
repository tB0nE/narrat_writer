# Feature Plan: NARRATapi Launcher & Creator

## Phase 1: Data Migration & Backend Refactor
- [x] Create `/games` directory structure.
- [x] Refactor `main.py` to accept `game_id` in every request (e.g., `/game/{game_id}/session/{session_id}/step`).
- [x] Update all file pathing to be relative to `games/{game_id}/`.

## Phase 2: Game Management API
- [x] **Endpoint:** `GET /games` (List all installed games).
- [x] **Endpoint:** `POST /create_game` 
    - Handles prompt -> AI JSON conversion.
    - Scaffolds folder, `phase1.narrat`, and metadata.
- [x] **Endpoint:** `GET /game/{game_id}/metadata` (Fetch title/summary).

## Phase 3: The Launcher (client.py)
- [x] Implement **Intro Screen** (70/30 layout).
- [ ] Add **NarratAPI Logo** using Rich `Panel` and `Figlet` style text. (Logo added but could be improved)
- [x] **Create Flow:**
    - AI: Prompt -> Loading State -> Metadata Summary Edit Page.
    - Manual: Input Name -> Summary -> Metadata Summary Edit Page.
- [x] **Select Flow:**
    - List Games -> Game Hub (Summary + New/Load options).

## Phase 4: Metadata Hub
- [ ] Dedicated UI to view/edit `metadata.json`.
- [ ] Buttons to "Regenerate" specific sections using the AI.

## Phase 5: Polish
- [ ] Standardize shortcuts across Launcher and Game Engine.
- [ ] Ensure `python client.py [game_id]` still bypasses launcher for power users.
