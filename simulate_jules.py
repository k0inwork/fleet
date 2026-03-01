import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def simulate_jules():
    # Configuration for the bridge daemon
    # It assumes bridge_daemon.py is in the current directory
    server_params = StdioServerParameters(
        command="python",
        args=["bridge_daemon.py"],
        env={**os.environ, "JULES_SESSION_ID": "local-test-session"}
    )

    print("--- Starting Jules Simulation ---")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Initialize
            print("[Jules] Initializing session...")
            resp = await session.call_tool("initialize_session", {
                "repo": "google/jules-hydra",
                "branch": "feat/local-test"
            })
            print(f"[Bridge] {resp.content[0].text}")

            # 2. Report Plan
            print("[Jules] Reporting plan...")
            plan = {
                "tasks": [
                    {"id": "1", "description": "Set up simulation", "status": "pending"},
                    {"id": "2", "description": "Verify connection", "status": "pending"}
                ]
            }
            resp = await session.call_tool("report_event", {
                "event_type": "PLAN_CREATED",
                "payload": {"plan": plan}
            })
            print(f"[Bridge] {resp.content[0].text}")

            # 3. Wait for instruction (This will block until you click a button in Hydra UI)
            print("[Jules] Waiting for instruction from Hydra UI...")
            print("(Go to the 'Bridge Control' tab in Hydra, select the session, and click CONTINUE)")

            resp = await session.call_tool("wait_for_instruction", {})
            print(f"\n[Jules] RECEIVED INSTRUCTION: {resp.content[0].text}")

if __name__ == "__main__":
    if not os.path.exists("bridge_daemon.py"):
        print("Error: bridge_daemon.py not found in current directory.")
        sys.exit(1)

    try:
        asyncio.run(simulate_jules())
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
