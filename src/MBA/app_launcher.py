"""
Application launcher for Streamlit UI.

This module provides a command-line entry point for launching the
Streamlit web interface through the project's CLI tools.

Module Input:
    - Command-line invocation via setuptools entry point
    
Module Output:
    - Launches Streamlit server with configured application
    - Exits with Streamlit's exit code

Usage:
    $ mba-app
    
    Or directly:
    $ python -m MBA.app_launcher
"""

import sys
from pathlib import Path


def main():
    """
    Launch the Streamlit application.
    
    Command-line entry point that locates the Streamlit app module
    and launches it using Streamlit's CLI interface.
    
    Side Effects:
        - Modifies sys.argv for Streamlit CLI
        - Starts Streamlit server (blocking)
        - Exits with Streamlit's return code
        
    Raises:
        SystemExit: If Streamlit app not found or launch fails
    """
    import streamlit.web.cli as stcli
    
    # Get the path to the streamlit app
    app_path = Path(__file__).parent / "ui" / "streamlit_app.py"
    
    if not app_path.exists():
        print(f"Error: Streamlit app not found at {app_path}", file=sys.stderr)
        print("Expected location: src/MBA/ui/streamlit_app.py", file=sys.stderr)
        sys.exit(1)
    
    print(f"Launching MBA Upload Service UI from {app_path}")
    
    # Prepare Streamlit CLI arguments
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.port=8501",
        "--server.headless=true"
    ]
    
    # Launch Streamlit
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()