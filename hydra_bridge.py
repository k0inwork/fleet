import asyncio
import httpx
import time
from typing import Callable, Dict, Optional

FIREBASE_URL = "https://channel1-2792f-default-rtdb.firebaseio.com"

class HydraBridge:
    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.active_sessions = {}
        self.running = False

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[HydraBridge] {message}")

    async def _firebase_get(self, path):
        async with httpx.AsyncClient() as client:
            url = f"{FIREBASE_URL}/{path}.json"
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _firebase_put(self, path, data):
        async with httpx.AsyncClient() as client:
            url = f"{FIREBASE_URL}/{path}.json"
            response = await client.put(url, json=data)
            response.raise_for_status()
            return response.json()

    async def send_command(self, session_id: str, command: str, modified_plan: Optional[list] = None, message: Optional[str] = None):
        data = {
            "command": command,
            "modified_plan": modified_plan,
            "message": message,
            "timestamp": time.time()
        }
        await self._firebase_put(f"sessions/{session_id}/command", data)
        self.log(f"Sent command {command} to session {session_id}")

    async def listen_for_sessions(self, callback: Callable):
        """
        Polls Firebase for new sessions and events.
        In a real app, SSE would be better, but polling is simpler for a prototype.
        """
        self.running = True
        seen_events = {} # session_id -> set of event_keys

        while self.running:
            try:
                data = await self._firebase_get("sessions")
                if data:
                    for session_id, session_data in data.items():
                        # Handle metadata
                        metadata = session_data.get("metadata")
                        if metadata and session_id not in self.active_sessions:
                            self.active_sessions[session_id] = metadata
                            await callback("NEW_SESSION", session_id, metadata)

                        # Handle events
                        events = session_data.get("events", {})
                        if session_id not in seen_events:
                            seen_events[session_id] = set()

                        for event_key, event_val in events.items():
                            if event_key not in seen_events[session_id]:
                                seen_events[session_id].add(event_key)
                                await callback("EVENT", session_id, event_val)
            except Exception as e:
                self.log(f"Error polling Firebase: {e}")

            await asyncio.sleep(3)

    def stop(self):
        self.running = False

if __name__ == "__main__":
    # Test script
    async def test_callback(type, sid, data):
        print(f"Callback: {type} | {sid} | {data}")

    bridge = HydraBridge()
    asyncio.run(bridge.listen_for_sessions(test_callback))
