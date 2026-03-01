#!/bin/bash

# Jules Bridge Installation Script
# This script installs the bridge daemon as a systemd service and configures AGENTS.md

set -e

echo "Installing Jules Bridge..."

# 1. Install dependencies
pip install mcp httpx

# 2. Create the bridge daemon script
cat << 'INNER_EOF' > /home/jules/bridge_daemon.py
import asyncio
import os
import json
import uuid
import time
import httpx
from mcp.server.fastmcp import FastMCP

# Firebase Config (Hardcoded as requested)
FIREBASE_URL = "https://channel1-2792f-default-rtdb.firebaseio.com"

# Session ID
SESSION_ID = os.getenv("JULES_SESSION_ID", str(uuid.uuid4()))

mcp = FastMCP("JulesBridge")

async def firebase_put(path, data):
    async with httpx.AsyncClient() as client:
        url = f"{FIREBASE_URL}/{path}.json"
        response = await client.put(url, json=data)
        if response.status_code == 401: return {"error": "Unauthorized"}; response.raise_for_status()
        return response.json()

async def firebase_post(path, data):
    async with httpx.AsyncClient() as client:
        url = f"{FIREBASE_URL}/{path}.json"
        response = await client.post(url, json=data)
        if response.status_code == 401: return {"error": "Unauthorized"}; response.raise_for_status()
        return response.json()

async def firebase_get(path):
    async with httpx.AsyncClient() as client:
        url = f"{FIREBASE_URL}/{path}.json"
        response = await client.get(url)
        if response.status_code == 401: return {"error": "Unauthorized"}; response.raise_for_status()
        return response.json()

@mcp.tool()
async def report_event(event_type: str, payload: dict) -> str:
    """
    Report an event to the Hydra controller.
    event_type: SESSION_STARTED, PLAN_CREATED, STEP_STARTED, STEP_COMPLETED, TASK_FINISHED, ERROR, INFO
    """
    event_data = {
        "timestamp": time.time(),
        "event": event_type,
        "payload": payload,
        "session_id": SESSION_ID
    }
    await firebase_post(f"sessions/{SESSION_ID}/events", event_data)
    await firebase_put(f"sessions/{SESSION_ID}/last_event", event_type)
    return f"Event {event_type} reported."

@mcp.tool()
async def wait_for_instruction() -> dict:
    """
    Wait for an instruction from the Hydra controller.
    """
    print(f"Waiting for instruction for session {SESSION_ID}...")
    await firebase_put(f"sessions/{SESSION_ID}/command", None)

    while True:
        command = await firebase_get(f"sessions/{SESSION_ID}/command")
        if command:
            await firebase_put(f"sessions/{SESSION_ID}/command", None)
            return command
        await asyncio.sleep(2)

@mcp.tool()
async def initialize_session(repo: str, branch: str) -> str:
    """
    Initialize the session in the bridge.
    """
    data = {
        "session_id": SESSION_ID,
        "repo": repo,
        "branch": branch,
        "start_time": time.time(),
        "status": "online"
    }
    await firebase_put(f"sessions/{SESSION_ID}/metadata", data)
    return f"Session {SESSION_ID} initialized."

if __name__ == "__main__":
    mcp.run()
INNER_EOF

# 3. Setup systemd service (if running as root or with sudo)
if [ "$EUID" -ne 0 ]; then
  echo "Not running as root, skipping systemd setup. You can start the bridge manually with: python /home/jules/bridge_daemon.py"
else
  cat << 'INNER_EOF' > /etc/systemd/system/jules-bridge.service
[Unit]
Description=Jules Bridge Daemon
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/jules/bridge_daemon.py
Restart=always
User=jules
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
INNER_EOF
  systemctl daemon-reload
  systemctl enable jules-bridge
  systemctl start jules-bridge
  echo "Systemd service 'jules-bridge' started."
fi

# 4. Create AGENTS.md
cat << 'INNER_EOF' > AGENTS.md
# Agent Instructions: Jules Bridge

You are connected to a Hydra Controller via the Jules Bridge MCP server.
Before starting any task, you MUST:
1. Call `initialize_session` with the current repository and branch.
2. Call `report_event` with `PLAN_CREATED` and your proposed plan.
3. Call `wait_for_instruction` and wait for the controller to approve or modify your plan.

During execution:
- Report major steps using `report_event` with `STEP_STARTED` and `STEP_COMPLETED`.
- If you need clarification, use `report_event` with `INFO` (asking a question in the payload) and then call `wait_for_instruction`.
- Upon finishing, call `report_event` with `TASK_FINISHED`.

The bridge daemon is running locally and provides these tools.
INNER_EOF

echo "Installation complete!"
