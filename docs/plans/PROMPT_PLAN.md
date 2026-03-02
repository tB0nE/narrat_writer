# NARRATapi Prompt Strategy Plan - [x] All Prompts Implemented

This document outlines the required LLM prompts to be centralized in `prompts.py`. The goal is to provide consistent, high-quality generation across the application.

## 1. Game Scaffolding (`CONCEPT_GENERATOR`) - [x] Done
Used when creating a new game from a high-level description.

## 2. Dynamic Story Continuation (`STORY_CONTINUATION`) - [x] Done
Used when the player reaches a "Missing Label" or chooses to generate more content.

## 3. Metadata Refinement (`METADATA_REGENERATOR`) - [x] Done
Used to update or "level up" the game's metadata based on new ideas.

## 4. Asset Description Generation (`ASSET_DESCRIBER`) - [x] Done
Used to generate "Reference" text for characters or backgrounds.

## 5. Script Surgical Edit (`SCRIPT_ASSISTANT`) - [x] Done
Used to help the user rewrite a specific line or choice within the script editor.

---

## Implementation Strategy
1. **Centralization**: All prompt templates move to `prompts.py`. [x] Done
2. **Context Helpers**: Gather dialogue history and metadata into a clean string for the LLM. [x] Done
3. **Robust Parsing**: unified helper to strip Markdown and ensure valid JSON/Narrat. [x] Done
