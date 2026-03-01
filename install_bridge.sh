#!/bin/bash
set -e
echo "Installing Jules Bridge..."
pip install mcp httpx
cat << 'INNER_EOF' > /home/jules/bridge_daemon.py
import asyncio
import os
import json
import uuid
import time
import httpx
from mcp.server.fastmcp import FastMCP

FIREBASE_URL = "https://channel1-2792f-default-rtdb.firebaseio.com/*/main"
SESSION_ID = os.getenv("JULES_SESSION_ID", str(uuid.uuid4()))

mcp = FastMCP("JulesBridge")

async def firebase_request(method, path, data=None):
    url = f"{FIREBASE_URL}/{path}.json"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(method, url, json=data)
            return resp.json()
        except:
            return None

@mcp.tool()
async def report_event(event_type: str, payload: dict) -> str:
    """Report an event to the Hydra controller."""
    event_data = {
        "timestamp": time.time(),
        "event": event_type,
        "payload": payload,
        "session_id": SESSION_ID
    }
    await firebase_request("POST", f"sessions/{SESSION_ID}/events", event_data)
    await firebase_request("PUT", f"sessions/{SESSION_ID}/last_event", event_type)
    return f"Event {event_type} reported."

@mcp.tool()
async def wait_for_instruction() -> dict:
    """Wait for an instruction from the Hydra controller."""
    while True:
        command = await firebase_request("GET", f"sessions/{SESSION_ID}/command")
        if command:
            return command
        await asyncio.sleep(1)

@mcp.tool()
async def initialize_session(repo: str, branch: str) -> str:
    """Initialize the session in the bridge."""
    data = {
        "session_id": SESSION_ID,
        "repo": repo,
        "branch": branch,
        "start_time": time.time(),
        "status": "online"
    }
    await firebase_request("PUT", f"sessions/{SESSION_ID}/metadata", data)
    return f"Session {SESSION_ID} initialized."

if __name__ == "__main__":
    mcp.run()
INNER_EOF

if [ "$EUID" -eq 0 ]; then
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
fi

cat << 'INNER_EOF' > AGENTS.md
# Agent Instructions: Jules Bridge
You are connected to a Hydra Controller via the Jules Bridge MCP server.
Before starting any task, you MUST:
1. Call `initialize_session`.
2. Call `report_event` with `PLAN_CREATED`.
3. Call `wait_for_instruction`.
INNER_EOF
echo "Installation complete!"
