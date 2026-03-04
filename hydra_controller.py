import asyncio
import os
import logging
from typing import Optional, List, Dict
from pydantic import BaseModel
from fastmcp import Client
from jules_mcp import mcp

logger = logging.getLogger("HydraController")

class JulesActivity(BaseModel):
    description: str
    status: str

class JulesSession:
    def __init__(self, session_id: str, branch: str):
        self.session_id = session_id
        self.branch = branch
        self.status = "idle"
        self.current_task_id: Optional[str] = None

class HydraController:
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json", credentials: Optional[Dict] = None):
        self.credentials = credentials or {}
        self.sessions: Dict[str, JulesSession] = {}
        self.semaphore = asyncio.Semaphore(3)
        self.client: Optional[Client] = None
        self._sources_cache = None

        # Ensure JULES_API_KEY is available if passed in credentials
        # FastMCP/Jules SDK reads it from environment automatically
        api_key = self.credentials.get("jules_api_key") or self.credentials.get("gemini_api_key")
        if api_key:
            os.environ["JULES_API_KEY"] = api_key

    async def start(self, headless: bool = True):
        # We start the FastMCP client context
        logger.info("Starting Jules MCP Client...")
        self.client = Client(mcp)
        # Manually enter async context without causing errors in 3.13 fastmcp implementation
        self._client_cm = self.client.__aenter__()
        await self._client_cm

    async def stop(self):
        logger.info("Stopping Jules MCP Client...")
        if self.client and hasattr(self, '_client_cm'):
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error stopping client: {e}")
            finally:
                self.client = None

    async def _get_source_id(self, repo_full_name: str) -> Optional[str]:
        if not self._sources_cache:
            try:
                # Use MCP tool to get all sources
                res = await self.client.call_tool("get_all_sources")
                self._sources_cache = res
            except Exception as e:
                logger.error(f"Failed to fetch sources: {e}")
                return None

        for source in self._sources_cache:
            # Assuming source dictionary has 'name' or 'display_name'
            if repo_full_name.lower() in str(source).lower():
                # Extract the source id. Usually it's in a 'name' field like 'sources/123'
                if isinstance(source, dict) and 'name' in source:
                    return source['name']
        return None

    async def create_session(self, repo_full_name: str, branch: str) -> Optional[str]:
        """Creates a new session for a specific repo and branch via MCP."""
        async with self.semaphore:
            try:
                logger.info(f"Finding source ID for {repo_full_name}")
                source_id = await self._get_source_id(repo_full_name)

                if not source_id:
                    # Fallback to creating a synthetic source string if not found, though Jules API usually requires a real one.
                    # We will log a warning.
                    logger.warning(f"Could not find exact source for {repo_full_name}, attempting default resolution.")
                    source_id = f"sources/{repo_full_name.replace('/', '_')}"

                prompt = f"Please checkout a new branch named '{branch}' from the latest main/master. Then wait for further instructions."

                logger.info(f"Creating Jules session for {source_id} on branch {branch}")
                session_data = await self.client.call_tool(
                    "create_session",
                    {
                        "prompt": prompt,
                        "source": source_id,
                        "starting_branch": "main", # Default starting branch
                        "require_plan_approval": False
                    }
                )

                session_id = session_data.get("name")
                if not session_id:
                    raise ValueError(f"Invalid session data returned: {session_data}")

                logger.info(f"Session created: {session_id}")
                session = JulesSession(session_id, branch)
                self.sessions[session_id] = session
                return session_id

            except Exception as e:
                logger.error(f"Failed to create session for {repo_full_name}: {e}")
                return None

    async def send_message(self, session_id: str, message: str):
        session = self.sessions.get(session_id)
        if not session:
            return

        try:
            logger.info(f"Sending message to session {session_id}: {message[:50]}...")
            await self.client.call_tool(
                "send_session_message",
                {"session_id": session_id, "prompt": message}
            )
            logger.info(f"Sent Message to {session_id}")
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")

    async def get_activities(self, session_id: str) -> List[JulesActivity]:
        session = self.sessions.get(session_id)
        if not session: return []

        try:
            acts = await self.client.call_tool(
                "list_all_activities",
                {"session_id": session_id}
            )

            activities = []
            for act in acts:
                # Based on Jules API, activities have states and descriptions
                desc = act.get("description", str(act))
                state = act.get("state", "UNKNOWN")
                status_mapped = "Done" if state == "SUCCEEDED" else ("Running" if state == "RUNNING" else state)
                activities.append(JulesActivity(description=desc, status=status_mapped))
            return activities
        except Exception as e:
            logger.error(f"Failed to fetch activities for {session_id}: {e}")
            return []

    async def mind_wipe(self, session_id: str):
        # Programmatic equivalent of a mind wipe might just be sending a reset message
        reset_msg = "FORGET all what has been done. Clear your context and focus on a new task. I will provide new instructions shortly."
        await self.send_message(session_id, reset_msg)

    async def hard_scrub(self, session_id: str):
        await self.send_message(session_id, "Delete all files in the current workspace and reset environment.")
