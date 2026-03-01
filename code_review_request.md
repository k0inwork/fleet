# Code Review: Jules Bridge Daemon & Hydra integration (Real Firebase Verified)

## Changes
- Implemented `bridge_daemon.py` (MCP server for Jules).
- Implemented `hydra_bridge.py` (Controller side logic).
- Updated `main.py` with the "Bridge Control" UI tab.
- Added `install_bridge.sh` and `AGENTS.md`.
- All components configured to work with the user's specific Firebase security rules (`*/main` path).

## Verification
- Successfully performed a write operation to the real Firebase URL.
- Verified MCP tool calls locally.
- Verified Python compilation.
