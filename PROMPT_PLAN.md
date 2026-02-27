# NARRATapi Prompt Strategy Plan

This document outlines the required LLM prompts to be centralized in `prompts.py`. The goal is to provide consistent, high-quality generation across the application.

## 1. Game Scaffolding (`CONCEPT_GENERATOR`) - [x] Done
Used when creating a new game from a high-level description.
- **Trigger**: `POST /games/create`
- **Input**: User's raw idea (e.g., "A cyberpunk detective story in Neo-Tokyo").
- **Output**: JSON containing `title`, `summary`, `genre`, `characters` (list), and `plot_outline`.
- **Constraint**: Must be strictly valid JSON for parsing into `GameMetadata`.

## 2. Dynamic Story Continuation (`STORY_CONTINUATION`) - [x] Done
Used when the player reaches a "Missing Label" and chooses to generate it.
- **Trigger**: `POST /games/{id}/sessions/{sid}/generate`
- **Context Required**:
    - **Metadata**: Current title, summary, and plot outline.
    - **Dialogue History**: The last 10-20 lines of dialogue to maintain tone/flow.
    - **Current State**: The label name being generated and current active background/characters.
- **Output**: Narrat script syntax.
- **Goal**: Generate a meaningful scene that bridges the current situation to a new choice or label.

## 3. Metadata Refinement (`METADATA_REGENERATOR`) - [x] Done
Used to update or "level up" the game's metadata based on new ideas or script changes.
- **Trigger**: `POST /games/{id}/regenerate`
- **Input**: Current `metadata.json` + User instruction (e.g., "Make it more gritty").
- **Output**: Updated JSON metadata.

## 4. Asset Description Generation (`ASSET_DESCRIBER`) - [x] Done
Used to generate "Reference" text for characters or backgrounds that are mentioned in the script but don't have a `.txt` file yet.
- **Trigger**: UI request for a missing description.
- **Input**: Asset ID (e.g., "anya") + Game Context.
- **Output**: A 1-2 paragraph description of the character's appearance and vibe.

## 5. Script Surgical Edit (`SCRIPT_ASSISTANT`) - *Future*
Used to help the user rewrite a specific line or choice within the script editor.
- **Trigger**: A "Magic Wand" button in the edit flow.
- **Input**: The specific line + instruction (e.g., "Make this sound more professional").
- **Output**: The modified Narrat code.

---

## Implementation Strategy
1. **Centralization**: All prompt templates move to `prompts.py`. [x] Done
2. **Context Helpers**: Create a `PromptContextBuilder` in `main.py` that gathers dialogue history and metadata into a clean string for the LLM. [x] Done (Inline logic)
3. **Robust Parsing**: Use a unified helper to strip Markdown backticks and ensure JSON/Narrat content is extracted cleanly from AI responses. [x] Done
