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

## Phase 3: Launcher & Game Creator
- [x] **Multi-Game Support**: Games stored in `/games/{id}`.
- [x] **Launcher UI**: Nice 70/30 intro screen.
- [x] **Game Creator**: AI and Manual game scaffolding.
- [ ] **Metadata Hub**: UI to view/edit `metadata.json`.
- [ ] **AI-Regen**: Ability to regenerate metadata fields via AI.

## Phase 4: Polish
- [ ] **Save Management**: List and delete saves from the Launcher.
- [ ] **Variable Evaluation**: Robust expression parsing for `if` statements. (Already mostly done)
- [ ] **Animation/Scene Triggers**: Basic handling for placeholders in the terminal. (Already mostly done)
