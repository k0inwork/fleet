import asyncio
import os
import json
import uuid
import time
import httpx
from mcp.server.fastmcp import FastMCP

# Firebase Config
FIREBASE_URL = "https://channel1-2792f-default-rtdb.firebaseio.com"

# Session ID
SESSION_ID = os.getenv("JULES_SESSION_ID", str(uuid.uuid4()))

mcp = FastMCP("JulesBridge")

async def firebase_put(path, data):
    async with httpx.AsyncClient() as client:
        # Note: In production, you would append ?auth=TOKEN
        url = f"{FIREBASE_URL}/{path}.json"
        response = await client.put(url, json=data)
        if response.status_code == 401:
            print(f"Warning: 401 Unauthorized for {url}. Check Firebase rules.")
            return {"error": "Unauthorized", "url": url}
        response.raise_for_status()
        return response.json()

async def firebase_post(path, data):
    async with httpx.AsyncClient() as client:
        url = f"{FIREBASE_URL}/{path}.json"
        response = await client.post(url, json=data)
        if response.status_code == 401:
            print(f"Warning: 401 Unauthorized for {url}. Check Firebase rules.")
            return {"error": "Unauthorized", "url": url}
        response.raise_for_status()
        return response.json()

async def firebase_get(path):
    async with httpx.AsyncClient() as client:
        url = f"{FIREBASE_URL}/{path}.json"
        response = await client.get(url)
        if response.status_code == 401:
            print(f"Warning: 401 Unauthorized for {url}. Check Firebase rules.")
            return None
        response.raise_for_status()
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
    return f"Event {event_type} reported (Note: Check logs for potential 401 errors)."

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
    return f"Session {SESSION_ID} initialized (Note: Check logs for potential 401 errors)."

if __name__ == "__main__":
    mcp.run()
