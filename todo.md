# Headless Narrat: Development TODO - [x] Phase 1-3 Completed

## Phase 1: Foundation - [x] Done
- [x] **Parser**: Core `.narrat` syntax parser (labels, talk, set, if).
- [x] **State API**: FastAPI session state management (load/save to JSON).
- [x] **Terminal Client**: `rich`-based CLI to interact with the API.
- [x] **Live Reload**: Support 'R' to re-parse and reset to the current label.

## Phase 2: Dynamic Features - [x] Done
- [x] **Back/Undo Logic**: Support 'B' to backtrack one state.
- [x] **Placeholder Fetching**: Load character/background info from `/reference`.
- [x] **AI-Append Logic**: Prompt for AI generation if a choice leads to a missing label.

## Phase 3: Launcher & Game Creator - [x] Done
- [x] **Multi-Game Support**: Games stored in `/games/{id}`.
- [x] **Launcher UI**: Nice 70/30 intro screen.
- [x] **Game Creator**: AI and Manual game scaffolding.
- [x] **Metadata Hub**: UI to view/edit `metadata.json`.
- [x] **AI-Regen**: Ability to regenerate metadata fields via AI.

## Phase 4: Polish & Advanced Logic
- [x] **Save Management**: List and delete saves from the Launcher.
- [x] **Variable Evaluation**: Robust expression parsing for `if` statements.
- [x] **Animation/Scene Triggers**: Basic handling for placeholders in the terminal.
- [ ] **Shortcut Standardization**: Ensure consistent controls across all screens.
- [ ] **Direct Launch**: Allow bypassing the launcher for power users.
