import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["bridge_daemon.py"],
        env={**os.environ, "JULES_SESSION_ID": "current-jules-session"}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Calling initialize_session...")
            resp = await session.call_tool("initialize_session", {"repo": "google/jules-hydra", "branch": "feat/bridge"})
            print(f"Response: {resp}")

            print("Reporting PLAN_CREATED...")
            resp = await session.call_tool("report_event", {"event_type": "PLAN_CREATED", "payload": {"plan": "Implementing bridge daemon"}})
            print(f"Response: {resp}")

if __name__ == "__main__":
    asyncio.run(main())
