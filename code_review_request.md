# Final Code Review: Jules Bridge Integration (Permission Resilient)

## Changes
1.  **`install_bridge.sh`**: Updated to handle environments without root access. It now defaults to a `.bashrc` startup entry and manual `nohup` execution if `systemd` is unavailable.
2.  **`AGENTS.md`**: Updated with instructions for the agent to start the daemon manually if the MCP connection is lost.
3.  **`bridge_daemon.py`**: MCP server for Jules VM communication via Firebase RTDB.
4.  **`hydra_bridge.py`**: Controller-side logic for the local Hydra app.
5.  **`main.py`**: Updated Hydra UI with "Bridge Control" and fixed CSS/legacy code.

## Verification
- Verified Firebase read/write access using the verified path prefix.
- Verified MCP tool calls.
- Verified Python compilation.
- Verified that `install_bridge.sh` correctly handles both root and non-root scenarios.
