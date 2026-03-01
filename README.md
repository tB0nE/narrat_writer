# Narrat Writer (v0.2.0)

Narrat Writer is a modular, CLI-based development environment designed for writing, playing, and managing visual novels using the Narrat script syntax. It features deep AI integration for scaffolding games, continuing stories, and refactoring assets.

## 🚀 Key Features

- **Interactive CLI**: Arrow-key navigation and dual-focus gameplay UI.
- **AI-Powered Scaffolding**: Generate entire game concepts (metadata + initial script) from a single prompt.
- **Modular Architecture**: Clean separation between the FastAPI backend and Terminal client.
- **Asset Manager**: Globally refactor characters, backgrounds, and scenes with case-preservation.
- **Surgical AI Edit**: Use the "Magic Wand" to have AI rewrite specific dialogue lines or choices.
- **Save Management**: Comprehensive browser to list, preview, and manage game sessions.
- **Robust Testing**: 100% pass rate across API, Logic, and Visual regression suites.

## 🛠 Project Structure

- `server.py`: Root entry point for the FastAPI backend.
- `terminal_client.py`: Root entry point for the interactive CLI.
- `src/server/`: Core backend logic (API, Parser, AI, Utils).
- `src/terminal_client/`: CLI implementation (Interactive Screens, UI Utils).
- `prompts.py`: Centralized LLM prompt templates.
- `games/`: Directory where game scripts, metadata, and saves are stored.
- `docs/`: Comprehensive project plans and syntax references.

## 🚦 Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and add your API key:
   ```bash
   cp .env.example .env
   ```

3. **Launch Narrat Writer**:
   ```bash
   ./narrat_writer
   # OR
   python terminal_client.py
   ```

## 🧪 Testing

Run the full verification suite:
```bash
pytest tests/
```

## 📜 Documentation
See the `docs/` folder for:
- `narrat_syntax.md`: Script writing guide.
- `plans/`: Historical development roadmaps and future plans.
