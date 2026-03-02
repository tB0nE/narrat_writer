import sys
import os
import signal
from src.terminal_client.utils import ensure_server_running, console
from src.terminal_client.screens.launcher import Launcher
from src.terminal_client.screens.engine import GameEngine

def main():
    # Ensure server is up (launches server.py if needed)
    server_proc = ensure_server_running()
    
    try:
        # Support direct launch: python terminal_client.py game_id [session_id]
        if len(sys.argv) > 1:
            game_id = sys.argv[1]
            session_id = sys.argv[2] if len(sys.argv) > 2 else "autosave"
            engine = GameEngine(game_id, session_id)
            engine.run()
        else:
            # Start the main Launcher UI
            launcher = Launcher()
            launcher.run()
    except KeyboardInterrupt:
        pass # Handle clean exit on Ctrl+C
    finally:
        # Cleanup background server if we started it
        if server_proc:
            console.print("[dim]Shutting down background server...[/dim]")
            try:
                os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)
            except:
                pass

if __name__ == "__main__":
    main()
