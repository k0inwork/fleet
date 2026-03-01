import asyncio
import os
import json
import logging
import subprocess
import httpx
from typing import Optional, List, Dict
from pydantic import BaseModel

logger = logging.getLogger("JulesCLIController")

class JulesActivity(BaseModel):
    description: str
    status: str
    originator: Optional[str] = None
    create_time: Optional[str] = None

class JulesSession:
    def __init__(self, session_id: str, repo: str, status: str = "idle"):
        self.session_id = session_id
        self.repo = repo
        self.status = status

class HydraController:
    """
    Controller that uses both the 'jules' CLI and REST API to manage sessions.
    """
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json", credentials: Optional[Dict] = None):
        self.proxy_url = proxy_url
        self.state_path = state_path
        self.credentials = credentials or {}
        self.sessions: Dict[str, JulesSession] = {}
        self.jules_api_key = os.getenv("JULES_API_KEY")
        self.api_base = "https://jules.googleapis.com/v1alpha"

    def _get_env(self):
        env = os.environ.copy()
        if self.proxy_url:
            env['HTTP_PROXY'] = self.proxy_url
            env['HTTPS_PROXY'] = self.proxy_url
            env['all_proxy'] = self.proxy_url
        return env

    def _get_httpx_client(self) -> httpx.AsyncClient:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        proxy = self.proxy_url if self.proxy_url else None
        return httpx.AsyncClient(proxy=proxy, limits=limits, timeout=30.0)

    async def _api_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        if not self.jules_api_key:
            raise Exception("Jules API Key is not set.")

        headers = {
            "X-Goog-Api-Key": self.jules_api_key,
            "Content-Type": "application/json"
        }
        url = f"{self.api_base}/{endpoint}"

        async with self._get_httpx_client() as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code not in [200, 201]:
                logger.error(f"API Error ({response.status_code}): {response.text}")
                response.raise_for_status()

            return response.json()

    async def list_sources(self) -> List[Dict]:
        """Lists available sources via REST API."""
        try:
            data = await self._api_request("GET", "sources")
            return data.get("sources", [])
        except Exception as e:
            logger.error(f"Failed to list sources: {e}")
            raise

    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    env=self._get_env(),
                    capture_output=True,
                    text=True
                )
            )
        except Exception as e:
            logger.error(f"Command failed: {cmd}. Error: {e}")
            raise

    async def start(self, headless: bool = True):
        logger.info("HydraController (Hybrid) started.")

    async def stop(self):
        logger.info("HydraController (Hybrid) stopped.")

    async def login(self):
        """
        Triggers 'jules login'.
        """
        logger.info("Triggering 'jules login'...")
        # jules login usually opens a browser.
        # We run it without capturing output to avoid hanging on potential interactive prompts
        # or at least not block the process if it expects a TTY.
        try:
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["jules", "login"],
                    env=self._get_env(),
                    # Not capturing output to avoid hanging on potential interactive prompts
                )
            )
            if process.returncode == 0:
                logger.info("Login command finished.")
            else:
                logger.error(f"Login command returned non-zero code: {process.returncode}")
        except Exception as e:
            logger.error(f"Failed to execute jules login: {e}")

    async def create_session(self, repo_full_name: str, branch: str = "main", instruction: str = "") -> Optional[str]:
        """Creates a new session for a specific repo using Jules CLI (or API if key available)."""

        # If we have an API key, we prefer the API for creation to get immediate ID
        if self.jules_api_key:
            try:
                # Need to find source name first
                sources = await self.list_sources()
                source_name = next((s["name"] for s in sources if repo_full_name in s["name"]), None)

                if not source_name:
                    logger.warning(f"Source for {repo_full_name} not found via API. Falling back to CLI.")
                else:
                    data = {
                        "prompt": instruction,
                        "sourceContext": {
                            "source": source_name,
                            "githubRepoContext": {
                                "startingBranch": branch
                            }
                        },
                        "title": f"Task: {repo_full_name}"
                    }
                    resp = await self._api_request("POST", "sessions", data)
                    session_id = resp.get("id")
                    if session_id:
                        logger.info(f"Session created via API: {session_id}")
                        self.sessions[session_id] = JulesSession(session_id, repo_full_name, "running")
                        return session_id
            except Exception as e:
                logger.error(f"API session creation failed: {e}. Falling back to CLI.")

        # CLI Fallback
        cmd = ["jules", "remote", "new", "--repo", repo_full_name, "--session", instruction]
        try:
            result = await self._run_command(cmd)
            if result.returncode == 0:
                output = result.stdout.strip()
                import re
                match = re.search(r'session:\s*([\w\-/]+)', output, re.IGNORECASE)
                if not match:
                    match = re.search(r'ID:\s*([\w\-/]+)', output, re.IGNORECASE)

                if match:
                    session_id = match.group(1)
                    self.sessions[session_id] = JulesSession(session_id, repo_full_name, "running")
                    return session_id
            return None
        except Exception as e:
            logger.error(f"Error creating session via CLI: {e}")
            return None

    async def get_activities(self, session_id: str) -> List[JulesActivity]:
        """Fetch detailed activities via REST API or fallback to CLI listing."""
        if self.jules_api_key:
            try:
                # The session ID might be just the number, but API might expect sessions/ID
                # If it's a UUID/number, we prepend sessions/
                name = session_id if "/" in session_id else f"sessions/{session_id}"
                endpoint = f"{name}/activities"
                resp = await self._api_request("GET", endpoint)
                api_activities = resp.get("activities", [])

                activities = []
                for act in api_activities:
                    # Determine a friendly description
                    desc = "Activity"
                    if "planGenerated" in act: desc = "Plan generated"
                    elif "progressUpdated" in act: desc = act["progressUpdated"].get("title", "Progress update")
                    elif "sessionCompleted" in act: desc = "Session completed"

                    status = "Running"
                    if "sessionCompleted" in act: status = "Done"

                    activities.append(JulesActivity(
                        description=desc,
                        status=status,
                        originator=act.get("originator"),
                        create_time=act.get("createTime")
                    ))
                return activities
            except Exception as e:
                logger.error(f"Failed to get activities via API: {e}")

        # CLI Fallback (Already implemented logic)
        cmd = ["jules", "remote", "list", "--session"]
        try:
            result = await self._run_command(cmd)
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                for line in lines:
                    if session_id in line:
                        status = "Running"
                        lower_line = line.lower()
                        if any(term in lower_line for term in ["completed", "finished", "done"]):
                            status = "Done"
                        elif "failed" in lower_line or "error" in lower_line:
                            status = "Failed"
                        return [JulesActivity(description=f"Status: {status}", status=status)]
            return []
        except Exception as e:
            return []

    async def send_message(self, session_id: str, message: str):
        """Send a message to an existing session via REST API."""
        if not self.jules_api_key:
            logger.warning("send_message requires API Key.")
            return

        try:
            name = session_id if "/" in session_id else f"sessions/{session_id}"
            endpoint = f"{name}:sendMessage"
            data = {"prompt": message}
            await self._api_request("POST", endpoint, data)
            logger.info(f"Message sent to session {session_id}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def approve_plan(self, session_id: str):
        """Approve the latest plan via REST API."""
        if not self.jules_api_key: return
        try:
            name = session_id if "/" in session_id else f"sessions/{session_id}"
            endpoint = f"{name}:approvePlan"
            await self._api_request("POST", endpoint)
            logger.info(f"Plan approved for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to approve plan: {e}")

    async def archive_session(self, session_id: str):
        """
        Since Jules CLI/API (v1alpha) doesn't explicitly have a 'delete' or 'archive' command,
        we 'close' it by pulling results (if applicable) and marking it as inactive in our local state.
        In the future, this can be updated with an actual delete/archive API call.
        """
        logger.info(f"Closing/Archiving session {session_id} (Local state cleanup)")
        if session_id in self.sessions:
            self.sessions[session_id].status = "archived"

        # Try a 'remote pull' as a way to finalize/fetch results
        try:
            await self._run_command(["jules", "remote", "pull", "--session", session_id])
        except:
            pass
