# NARRATapi Frontend Development Plan

## Overview
Create a React-based web interface that mirrors the "Headless Narrat" terminal experience. The frontend will communicate with the existing FastAPI backend, replacing keyboard shortcuts with intuitive button-based interactions and contextual editing.

## Technical Stack
- **Framework:** React (Vite-powered)
- **Language:** TypeScript (for API type safety)
- **Styling:** Vanilla CSS (CSS Modules) to match the "Block" aesthetic of the CLI.
- **API Client:** Fetch API or Axios.

## Phase 1: Infrastructure & API Prep
- [ ] **CORS Implementation:** Update `main.py` to allow cross-origin requests from the React development server.
- [ ] **Project Scaffolding:** Initialize Vite project in `/frontend`.
- [ ] **Type Definitions:** Export TypeScript interfaces matching the backend's `DialogueResponse`, `SessionState`, and `GameMetadata`.

## Phase 2: The Launcher (Home Screen)
- [ ] **Layout:** Recreate the 70/30 split.
    - **Left:** Hero section with NARRATapi logo and description.
    - **Right:** Navigation panel with "Create Game" and "Select Game" buttons.
- [ ] **Game Creation Flow:**
    - Modal/Form for AI Prompt or Manual input.
    - Summary screen with immediate metadata editing capability.
- [ ] **Game Selection:** Grid or list view of existing games fetched from `GET /games`.

## Phase 3: The Engine View (VN Interface)
- [ ] **The "Dashboard" Layout:**
    - **Top Row (35%):** "Descriptions" block (Left) and "Current State" block (Right).
    - **Middle Row (35%):** "Dialogue" block with the bottom-anchored, fading log effect.
    - **Bottom Row (30%):** "Interaction" block for choice buttons and system messages.
- [ ] **Script Viewer (Sidebar):** A togglable 30% width column on the far right showing the `.narrat` file with live line highlighting.

## Phase 4: Contextual Editing (The "Writing Tool" Upgrade)
- [ ] **Edit Icons:** Add a small "pencil" or "gear" icon to the top-right corner of every block (Background, Character, Dialogue line, etc.).
- [ ] **Inline Editing:**
    - Clicking the icon transforms the text into an input/textarea.
    - Display action buttons immediately: **[Save]**, **[Regenerate]**, **[Cancel]**.
- [ ] **Surgical Integration:** Map these actions directly to the `POST /edit` endpoint using the `line_index` provided by the API.

## Phase 5: Interaction & Polish
- [ ] **Choice Buttons:** Replace the number-typing system with large, clickable choice cards.
- [ ] **Fading Logic:** Use CSS transitions/animations to handle the dialogue log "push-up" and text color grading.
- [ ] **Hotkeys:** (Optional) Support the existing terminal hotkeys (R, B, V, X) for power users.

## Phase 6: Unified Startup
- [ ] **Backend Update:** Optionally update `main.py` or `narrat_writer` to serve the production build of the React app as static files.
