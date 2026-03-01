# Code Review Request: Jules Bridge Daemon & Hydra Integration

## Changes
1.  **Bridge Daemon (`bridge_daemon.py`)**: An MCP server for Jules VMs that uses Firebase RTDB as a message broker.
2.  **Hydra Bridge (`hydra_bridge.py`)**: A logic layer for the Hydra Controller to communicate with multiple Jules sessions via Firebase.
3.  **Hydra UI Update (`main.py`)**: Added a "Bridge Control" tab to the Textual UI for real-time monitoring and manual intervention (Continue, Edit Plan, Ask Jules, etc.).
4.  **Installation Script (`install_bridge.sh`)**: Automates deployment on Jules VMs and creates `AGENTS.md`.

## Notes
- Firebase configuration is hardcoded as requested.
- Added error handling for 401 Unauthorized errors in case Firebase rules are restrictive.
- Used polling for Firebase updates for simplicity in the prototype.
