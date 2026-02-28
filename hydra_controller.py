import asyncio
import os
import json
import logging
import subprocess
from typing import Optional, List, Dict
from pydantic import BaseModel

logger = logging.getLogger("JulesCLIController")

class JulesActivity(BaseModel):
    description: str
    status: str

class JulesSession:
    def __init__(self, session_id: str, repo: str, status: str = "idle"):
        self.session_id = session_id
        self.repo = repo
        self.status = status

class HydraController:
    """
    Controller that uses the 'jules' CLI to manage sessions.
    Replaces the previous Playwright-based implementation.
    """
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json", credentials: Optional[Dict] = None):
        self.proxy_url = proxy_url
        self.state_path = state_path
        self.credentials = credentials or {}
        self.sessions: Dict[str, JulesSession] = {}

    def _get_env(self):
        env = os.environ.copy()
        if self.proxy_url:
            env['HTTP_PROXY'] = self.proxy_url
            env['HTTPS_PROXY'] = self.proxy_url
            env['all_proxy'] = self.proxy_url
        return env

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
        """No-op for CLI controller as it doesn't need a browser background process."""
        logger.info("JulesCLIController started.")

    async def stop(self):
        """No-op for CLI controller."""
        logger.info("JulesCLIController stopped.")

    async def login(self):
        """
        Triggers 'jules login'.
        In a TUI environment, this might need to be handled carefully if it's interactive.
        """
        logger.info("Triggering 'jules login'...")
        # jules login usually opens a browser.
        # Since we are in a sub-process, it should still work if the environment has a browser.
        try:
            process = await self._run_command(["jules", "login"])
            if process.returncode == 0:
                logger.info("Login command finished.")
            else:
                logger.error(f"Login failed: {process.stderr}")
        except Exception as e:
            logger.error(f"Failed to execute jules login: {e}")

    async def create_session(self, repo_full_name: str, branch: str = "main", instruction: str = "") -> Optional[str]:
        """Creates a new session for a specific repo using Jules CLI."""
        logger.info(f"Creating session for {repo_full_name} with instruction: {instruction[:50]}...")

        # Note: Jules CLI 'new' command doesn't explicitly take a branch,
        # it usually works on the repo's default or current branch if local.
        # But for remote new, it uses the repo name.
        cmd = ["jules", "remote", "new", "--repo", repo_full_name, "--session", instruction]

        try:
            result = await self._run_command(cmd)
            if result.returncode == 0:
                # Parse session ID from output.
                # Typical output: "Successfully created session: <session_id>" or similar.
                # We need to be robust here.
                output = result.stdout.strip()
                logger.info(f"CLI Output: {output}")

                # Simple extraction - this might need refinement based on exact CLI output format
                import re
                # Match alphanumeric, underscores, hyphens, and slashes
                match = re.search(r'session:\s*([\w\-/]+)', output, re.IGNORECASE)
                if not match:
                    # Fallback: maybe it just prints the ID?
                    match = re.search(r'ID:\s*([\w\-/]+)', output, re.IGNORECASE)

                if match:
                    session_id = match.group(1)
                    logger.info(f"Session created via CLI: {session_id}")
                    self.sessions[session_id] = JulesSession(session_id, repo_full_name, "running")
                    return session_id
                else:
                    logger.warning(f"Could not parse session ID from CLI output. Full output: {output}")
                    return None
            else:
                logger.error(f"Failed to create session: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None

    async def get_activities(self, session_id: str) -> List[JulesActivity]:
        """
        Polls the status of a session by parsing the output of 'jules remote list --session'.
        """
        cmd = ["jules", "remote", "list", "--session"]
        try:
            result = await self._run_command(cmd)
            if result.returncode == 0:
                # Parse the output line by line to find the specific session
                lines = result.stdout.splitlines()
                for line in lines:
                    if session_id in line:
                        # Check status for THIS specific line
                        status = "Running"
                        lower_line = line.lower()
                        if any(term in lower_line for term in ["completed", "finished", "done"]):
                            status = "Done"
                        elif "failed" in lower_line or "error" in lower_line:
                            status = "Failed"

                        return [JulesActivity(description=f"Session status: {status}", status=status)]

                logger.warning(f"Session {session_id} not found in 'jules remote list --session'.")
            return []
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
            return []

    async def send_message(self, session_id: str, message: str):
        """
        Jules CLI 'remote new' is the primary way to send instructions.
        Sending follow-up messages to an EXISTING remote session might not be directly supported via CLI
        in the same way 'remote new' works (which creates a NEW session).
        If the CLI supports continuing a session, we should use that.
        According to docs, 'remote new' creates a session.
        """
        logger.warning(f"send_message to session {session_id} called. CLI might not support follow-ups to remote sessions yet. Message: {message[:50]}...")
        # For now, we might just have to create a new session if tasks are discrete,
        # or wait for CLI updates.
        pass

    async def archive_session(self, session_id: str):
        """
        Jules CLI doesn't explicitly list an archive command in the help.
        We might need to check if 'logout' or some other command handles cleanup,
        or if it's not supported yet.
        """
        logger.warning(f"archive_session {session_id} called but not supported by CLI.")
        pass

    async def mind_wipe(self, session_id: str):
        """Not supported via CLI directly."""
        pass

    async def hard_scrub(self, session_id: str):
        """Not supported via CLI directly."""
        pass
