# Plan: Interactive CLI Menus with Questionary - [x] Completed

This plan outlines the migration from manual text input (typing numbers/letters) to an interactive, arrow-key and Enter-based navigation system using the `questionary` library.

## 1. Objectives
- Improve UX by removing the need to remember or type specific keys. [x] Done
- Reduce input errors (invalid choices). [x] Done
- Standardize the "Back" and "Exit" flow across all screens. [x] Done
- Maintain visual compatibility with existing `rich` panels. [x] Done

## 2. Dependencies
- Add `questionary` to `requirements.txt`. [x] Done

## 3. Implementation Strategy

### Phase 1: Dependency & Core Helper
- Install `questionary`. [x] Done
- Use `questionary.select` for consistent menu styling. [x] Done

### Phase 2: Launcher Migration
- Refactor the **Main Menu**. [x] Done
- Refactor the **Game Selection list**. [x] Done
- Refactor the **Create Game method** choice. [x] Done

### Phase 3: Game Hub & Asset Manager
- Refactor the **Game Hub**. [x] Done
- Refactor the **Asset Manager categories** and **Asset lists**. [x] Done
- Refactor the **Asset Edit actions**. [x] Done

### Phase 4: In-Game Engine
- Refactor the **In-Game Edit menu**. [x] Done
- Refactor the **End of Script choices**. [x] Done
- Refactor **In-Game Player Choices** to use arrow keys. [x] Done

## 4. Design Considerations
- **Rich vs Questionary:** Screen is cleared, Rich layout is printed, then Questionary prompt appears below. [x] Done
- **Shortcuts:** Standardized choice labels for clear navigation. [x] Done
