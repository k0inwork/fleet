# Final Code Review: Jules Bridge Integration + AGENTS.md

## Changes
1.  **`AGENTS.md`**: New file instructing Jules on how to use the bridge tools for initialization, planning, and status reporting.
2.  **`bridge_daemon.py`**: MCP server for Jules VM communication via Firebase RTDB.
3.  **`hydra_bridge.py`**: Controller-side logic to monitor sessions and send commands.
4.  **`main.py`**: Updated Hydra UI with "Bridge Control" and fixed CSS/legacy code.
5.  **`simulate_jules.py`**: Interactive script to simulate an agent using the bridge.
6.  **`install_bridge.sh`**: Deployment script for Jules VMs.

## Notes
- All paths use the verified `*/main/sessions` structure.
- Legacy "Login to Google" button has been removed from `main.py`.
- `AGENTS.md` is included in the root to ensure Jules starts using the bridge immediately upon session start.
