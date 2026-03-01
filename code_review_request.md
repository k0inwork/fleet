# Code Review: Jules Bridge Daemon & Hydra integration

## Summary
Implements a bidirectional communication bridge between Jules (agent) and Hydra (controller) using Firebase Realtime Database as a broker.

## Key Files
- `bridge_daemon.py`: MCP server for the agent side.
- `hydra_bridge.py`: Event listener and command sender for the controller side.
- `main.py`: Updated Hydra UI with a "Bridge Control" tab.
- `install_bridge.sh`: Automation for agent VM setup.
- `AGENTS.md`: Instructions for the agent to use the bridge.

## Verification
- Passed integration test with mock Firebase.
- Verified MCP protocol with `call_bridge.py`.
- Verified compilation of all new/modified files.
