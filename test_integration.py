import asyncio
import os
import subprocess
import time
import httpx
from hydra_bridge import HydraBridge
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TEST_FIREBASE_URL = "http://localhost:8889" # Change port to avoid conflict

async def run_integration_test():
    # 1. Start Mock Firebase
    firebase_proc = subprocess.Popen(["python", "mock_firebase.py"])
    # Need to update port in mock_firebase too if I change it here, but I will just kill existing.
    subprocess.run(["pkill", "-f", "mock_firebase.py"])
    firebase_proc = subprocess.Popen(["python", "mock_firebase.py"])

    time.sleep(2)

    try:
        received_events = []
        async def on_event(type, sid, data):
            print(f"Hydra received: {type} | {sid} | {data}")
            received_events.append((type, sid, data))

        bridge = HydraBridge()

        async def mock_get(path):
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:8888/{path}.json")
                return resp.json()
        async def mock_put(path, data):
            async with httpx.AsyncClient() as client:
                resp = await client.put(f"http://localhost:8888/{path}.json", json=data)
                return resp.json()

        bridge._firebase_get = mock_get
        bridge._firebase_put = mock_put

        listener_task = asyncio.create_task(bridge.listen_for_sessions(on_event))

        with open("bridge_daemon.py", "r") as f:
            daemon_code = f.read().replace(
                'FIREBASE_URL = "https://channel1-2792f-default-rtdb.firebaseio.com"',
                'FIREBASE_URL = "http://localhost:8888"'
            ).replace('await asyncio.sleep(2)', 'await asyncio.sleep(0.5)')

        with open("bridge_daemon_test.py", "w") as f:
            f.write(daemon_code)

        server_params = StdioServerParameters(
            command="python",
            args=["bridge_daemon_test.py"],
            env={**os.environ, "JULES_SESSION_ID": "integration-test-sid"}
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                print("--- Step 1: Initialize ---")
                await session.call_tool("initialize_session", {"repo": "acme/corp", "branch": "main"})

                print("--- Step 2: Report Plan ---")
                await session.call_tool("report_event", {"event_type": "PLAN_CREATED", "payload": {"plan": "Do work"}})

                await asyncio.sleep(4)

                print("--- Step 3: Send Command from Hydra ---")
                await bridge.send_command("integration-test-sid", "CONTINUE", message="Good job")

                print("--- Step 4: Jules receives command ---")
                cmd_resp = await session.call_tool("wait_for_instruction", {})
                print(f"Jules received: {cmd_resp}")

        print("--- Finalizing ---")
        listener_task.cancel()

        cmd_text = str(cmd_resp)
        success = any(e[0] == "NEW_SESSION" for e in received_events) and \
                  any(e[0] == "EVENT" and e[2].get("event") == "PLAN_CREATED" for e in received_events) and \
                  "CONTINUE" in cmd_text

        if success:
            print("\nSUCCESS: Integration test passed!")
        else:
            print("\nFAILURE: Integration test failed.")

    finally:
        firebase_proc.terminate()
        subprocess.run(["pkill", "-f", "mock_firebase.py"])

if __name__ == "__main__":
    asyncio.run(run_integration_test())
