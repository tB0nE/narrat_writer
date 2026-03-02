# Plan: CLI & UI Testing Strategy

This document outlines how we will verify the "UI" (interactive CLI) layer of NARRATapi, complementing our existing API and engine logic tests.

## 1. Testing Objectives
- **Navigation Flow**: Ensure that selecting "Select Game" -> "ID" -> "Start" actually enters the game engine.
- **Input Robustness**: Verify that invalid inputs or early exits (Ctrl+C) are handled gracefully.
- **Visual Integrity**: Ensure `rich` layouts (70/30 split, panels, tables) render correctly without overlapping or crashing.
- **AI Integration**: Verify that the "missing label" and "generate more" UI prompts trigger the correct API calls.

## 2. Tools & Libraries
- **`pexpect`**: For End-to-End (E2E) testing. It allows us to simulate a user sitting at a terminal, waiting for specific text, and sending keystrokes.
- **`unittest.mock`**: To mock `questionary` and `requests` for fast, isolated testing of the `Launcher` and `GameEngine` classes.
- **`rich.console.Console(record=True)`**: To capture "snapshots" of the UI as text/HTML to detect visual regressions.

## 3. Implementation Phases

### Phase 1: Unit Testing with Mocked Input
- Refactor `client.py` to allow passing a custom `Console` and `BaseURL`.
- Write tests that mock `questionary.select(...).ask()` to return specific strings (e.g., "Exit").
- **Goal**: Verify that the `run()` loops terminate correctly and call the right internal methods.

### Phase 2: E2E Interaction Tests (`pexpect`)
- Create a `tests/test_cli_interaction.py`.
- Spawn the full `narrat_writer` script.
- Wait for the "Main Menu" regex.
- Send `\x1b[B` (Down Arrow) and `` (Enter).
- Verify that the next screen (e.g., "Available Games") appears.

### Phase 3: Visual Snapshots
- Create a test fixture that runs a screen (like the Game Hub) and saves the `rich` output to a file in `tests/snapshots/`.
- Future test runs compare current output against these "golden" files.

## 4. Integration with CI
- All CLI tests should run in a headless environment (using a virtual terminal).
- Add `pexpect` to `requirements.txt`.

## 5. Next Steps
1. Add `pexpect` to dependencies.
2. Implement a "Smoke Test" that simply starts the launcher and exits immediately via arrow keys to prove the setup works.
