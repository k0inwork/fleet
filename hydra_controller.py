import asyncio
import json
import logging
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional, List, Dict
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HydraController")

# UI Selectors - Adjust these as the Jules UI evolves
SELECTORS = {
    "new_session_btn": "button:has-text('New session')",
    "repo_search_input": "placeholder='Search repositories'",
    "ask_jules_input": "placeholder='Ask Jules'",
    "message_content": ".message-content",
    "activity_item": ".activity-item",
    "session_options_btn": "button:has-text('Session options')",
    "archive_btn": "text='Archive'"
}

class JulesActivity(BaseModel):
    description: str
    status: str

class JulesSession:
    def __init__(self, session_id: str, branch: str, page: Page):
        self.session_id = session_id
        self.branch = branch
        self.page = page
        self.status = "idle"
        self.current_task_id: Optional[str] = None

class HydraController:
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json"):
        self.proxy_url = proxy_url
        self.state_path = state_path
        self.playwright = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.sessions: Dict[str, JulesSession] = {}
        self.semaphore = asyncio.Semaphore(3)

    async def start(self, headless: bool = True):
        self.playwright = await async_playwright().start()
        browser_args = [
            "--disable-blink-features=AutomationControlled",
        ]
        if self.proxy_url:
            browser_args.append(f"--proxy-server={self.proxy_url}")

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args,
        )

        # Load state if exists
        if os.path.exists(self.state_path):
            self.context = await self.browser.new_context(storage_state=self.state_path)
        else:
            self.context = await self.browser.new_context()

    async def login(self):
        """Open a browser for the user to log in manually."""
        page = await self.context.new_page()
        # Add some basic stealth scripts
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        await page.goto("https://jules.google.com")

        # Wait for user to finish - we poll for the "New session" button
        while True:
            try:
                if "jules.google.com" in page.url and await page.locator(SELECTORS["new_session_btn"]).is_visible():
                    break
            except:
                pass
            await asyncio.sleep(2)

        await self.context.storage_state(path=self.state_path)
        logger.info("Login state saved.")
        await page.close()

    async def stop(self):
        try:
            if hasattr(self, "context") and self.context:
                await self.context.storage_state(path=self.state_path)
                await self.context.close()
            if hasattr(self, "browser") and self.browser:
                await self.browser.close()
            if hasattr(self, "playwright") and self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping HydraController: {e}")

    async def create_session(self, repo_full_name: str, branch: str) -> Optional[str]:
        """Creates a new session for a specific repo and branch."""
        async with self.semaphore:
            page = await self.context.new_page()
            try:
                await page.goto("https://jules.google.com")
                await page.locator(SELECTORS["new_session_btn"]).click()

                # Search for the repo
                await page.locator(SELECTORS["repo_search_input"]).fill(repo_full_name)
                await page.get_by_text(repo_full_name).first.click()

                # Wait for session initialization
                await page.wait_for_url("**/sessions/*")
                session_id = page.url.split("/")[-1]

                # Instruct Jules to checkout the branch
                await self._send_initial_instructions(page, branch)

                session = JulesSession(session_id, branch, page)
                self.sessions[session_id] = session
                return session_id
            except Exception as e:
                logger.error(f"Failed to create session: {e}")
                await page.close()
                return None

    async def _send_initial_instructions(self, page: Page, branch: str):
        prompt = f"Please checkout a new branch named '{branch}' from the latest main/master. Then wait for further instructions."
        await page.locator(SELECTORS["ask_jules_input"]).fill(prompt)
        await page.locator(SELECTORS["ask_jules_input"]).press("Enter")
        # Wait for response start
        await page.wait_for_selector(SELECTORS["message_content"])

    async def send_message(self, session_id: str, message: str):
        session = self.sessions.get(session_id)
        if not session:
            return

        try:
            await session.page.locator(SELECTORS["ask_jules_input"]).fill(message)
            await session.page.locator(SELECTORS["ask_jules_input"]).press("Enter")
            # Wait for any new activity to appear
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")

    async def get_activities(self, session_id: str) -> List[JulesActivity]:
        session = self.sessions.get(session_id)
        if not session: return []

        # Scrape activities from the UI
        try:
            activities = []
            locators = await session.page.locator(SELECTORS["activity_item"]).all()
            for loc in locators:
                text = await loc.inner_text()
                status = "Done" if "check" in (await loc.get_attribute("class") or "") else "Running"
                activities.append(JulesActivity(description=text, status=status))
            return activities
        except:
            return []

    async def mind_wipe(self, session_id: str):
        session = self.sessions.get(session_id)
        if not session: return

        try:
            # 1. Try to Archive/Pause
            await session.page.locator(SELECTORS["session_options_btn"]).click()
            await session.page.locator(SELECTORS["archive_btn"]).click()
            await asyncio.sleep(1)

            # 2. Reactivate (maybe by going back to the session URL)
            await session.page.goto(f"https://jules.google.com/sessions/{session_id}")

            # 3. Send reset message
            reset_msg = "FORGET all what has been done. Clear your context and focus on a new task. I will provide new instructions shortly."
            await self.send_message(session_id, reset_msg)
            logger.info(f"Mind wipe performed on session {session_id}")
        except Exception as e:
            logger.error(f"Failed to mind wipe session {session_id}: {e}")

    async def hard_scrub(self, session_id: str):
        # Delete workspace if Jules supports it via command
        await self.send_message(session_id, "Delete all files in the current workspace and reset environment.")
        pass
