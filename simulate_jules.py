import asyncio
import os
import sys
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def simulate_jules():
    server_params = StdioServerParameters(
        command="python",
        args=["bridge_daemon.py"],
        env={**os.environ, "JULES_SESSION_ID": "local-test-session"}
    )

    print("\n" + "="*40)
    print("   JULES BRIDGE SIMULATION STARTED")
    print("="*40)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Initialize
            print("\n[Jules] Initializing session...")
            await session.call_tool("initialize_session", {
                "repo": "google/jules-hydra",
                "branch": "feat/local-test"
            })
            print("[Bridge] Session Initialized.")

            # 2. Report Plan
            print("\n[Jules] Reporting initial plan...")
            plan = {
                "tasks": [
                    {"id": "1", "description": "Analyzing codebase", "status": "pending"},
                    {"id": "2", "description": "Applying fixes", "status": "pending"}
                ]
            }
            await session.call_tool("report_event", {
                "event_type": "PLAN_CREATED",
                "payload": {"plan": plan}
            })
            print("[Bridge] Plan Reported. Waiting for approval in Hydra UI...")

            # 3. Main Instruction Loop
            while True:
                print("\n" + "-"*30)
                print("Waiting for instruction from Hydra UI...")
                resp = await session.call_tool("wait_for_instruction", {})

                # The bridge returns a JSON string content or dict
                try:
                    # mcp content is usually a list of TextContent objects
                    content_text = resp.content[0].text
                    data = json.loads(content_text)
                except:
                    # Fallback for different return formats
                    data = resp.content[0].text if hasattr(resp, 'content') else str(resp)
                    if isinstance(data, str) and (data.startswith('{') or data.startswith('[')):
                        try: data = json.loads(data)
                        except: pass

                cmd = data.get("command") if isinstance(data, dict) else str(data)
                msg = data.get("message") if isinstance(data, dict) else ""

                print(f"\n>>> RECEIVED COMMAND: {cmd}")
                if msg: print(f">>> MESSAGE FROM HYDRA: {msg}")

                if cmd == "CONTINUE":
                    print("[Jules] Proceeding with the next step...")
                    await session.call_tool("report_event", {
                        "event_type": "STEP_STARTED",
                        "payload": {"step": "Executing task..."}
                    })
                    await asyncio.sleep(2)
                    await session.call_tool("report_event", {
                        "event_type": "STEP_COMPLETED",
                        "payload": {"result": "Task completed successfully."}
                    })
                    print("[Jules] Step finished. Reporting back.")

                elif cmd == "ASK":
                    print(f"\nHydra asked: {msg}")
                    # In a real agent, Jules would think and reply.
                    # In this simulation, we'll let the LOCAL user type the answer.
                    answer = await asyncio.to_thread(input, "Type your answer to Hydra: ")
                    await session.call_tool("report_event", {
                        "event_type": "INFO",
                        "payload": {"response": answer}
                    })
                    print("[Jules] Answer sent to Hydra.")

                elif cmd == "STOP":
                    print("[Jules] Received STOP command. Shutting down.")
                    await session.call_tool("report_event", {
                        "event_type": "TASK_FINISHED",
                        "payload": {"status": "Stopped by user"}
                    })
                    break

                elif cmd == "REJECT":
                    print("[Jules] Plan REJECTED. Reporting error and waiting for new instructions.")
                    await session.call_tool("report_event", {
                        "event_type": "ERROR",
                        "payload": {"message": "Plan was rejected by controller."}
                    })

if __name__ == "__main__":
    if not os.path.exists("bridge_daemon.py"):
        print("Error: bridge_daemon.py not found.")
        sys.exit(1)

    try:
        asyncio.run(simulate_jules())
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
