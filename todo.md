# Headless Narrat: Development TODO

## Phase 1: Foundation
- [x] **Parser**: Core `.narrat` syntax parser (labels, talk, set, if).
- [x] **State API**: FastAPI session state management (load/save to JSON).
- [x] **Terminal Client**: `rich`-based CLI to interact with the API.
- [x] **Live Reload**: Support 'R' to re-parse and reset to the current label.

## Phase 2: Dynamic Features
- [x] **Back/Undo Logic**: Support 'B' to backtrack one state.
- [x] **Placeholder Fetching**: Load character/background info from `/reference`.
- [x] **AI-Append Logic**: Prompt for AI generation if a choice leads to a missing label.

## Phase 3: Polish
- [ ] **Variable Evaluation**: Robust expression parsing for `if` statements.
- [ ] **Animation/Scene Triggers**: Basic handling for placeholders in the terminal.
