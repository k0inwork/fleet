import asyncio
import os
import json
import logging
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional, List, Dict
from pydantic import BaseModel

logger = logging.getLogger("HydraController")

# UI Selectors - Adjust these as the Jules UI evolves
SELECTORS = {
    "new_session_btn": "[data-testid*='new-session'], button:has-text('New session'), :text-is('New session')",
    "repo_search_input": "input[placeholder*='Search'], [placeholder*='Search repositories'], [role='searchbox']",
    "ask_jules_input": "textarea[placeholder*='Ask Jules'], [placeholder*='Ask Jules'], [role='textbox']",
    "message_content": "[data-testid*='message'], .message-content, [class*='message-content']",
    "activity_item": "[data-testid*='activity'], .activity-item, [class*='activity-item']",
    "session_options_btn": "button:has-text('Session options'), [aria-label*='options'], [data-testid*='options']",
    "archive_btn": "text='Archive', :text-is('Archive'), [data-testid*='archive']",
    "settings_btn": "[aria-label*='Settings'], button:has-text('Settings'), a[href*='settings'], [data-testid*='settings']",
    "pause_btn": "button:has-text('Pause'), [aria-label*='Pause'], [data-testid*='pause']",
    "resume_btn": "button:has-text('Resume'), [aria-label*='Resume'], button:has-text('Restart'), [data-testid*='resume']",
    "activity_log": "[data-testid*='activity-log'], .activity-log, [class*='activity-log'], .message-list"
}

REFINED_SELECTORS_PATH = "refined_selectors.json"

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
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json", credentials: Optional[Dict] = None):
        self.proxy_url = proxy_url
        self.state_path = state_path
        self.credentials = credentials or {}
        self._load_refined_selectors()
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
        context_args = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 720},
            "device_scale_factor": 1,
        }

        if os.path.exists(self.state_path):
            self.context = await self.browser.new_context(storage_state=self.state_path, **context_args)
        else:
            self.context = await self.browser.new_context(**context_args)

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

    def _load_refined_selectors(self):
        """Augments the SELECTORS map with discovered data from previous explorations."""
        if os.path.exists(REFINED_SELECTORS_PATH):
            try:
                with open(REFINED_SELECTORS_PATH, "r") as f:
                    refined = json.load(f)
                    for key, selector in refined.items():
                        if key in SELECTORS:
                            # Prepend refined selector to existing ones to give it priority
                            SELECTORS[key] = f"{selector}, {SELECTORS[key]}"
                        else:
                            SELECTORS[key] = selector
                logger.info(f"Augmented {len(refined)} selectors from {REFINED_SELECTORS_PATH}")
            except Exception as e:
                logger.error(f"Failed to load refined selectors: {e}")

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

    async def check_and_perform_autologin(self, page: Page):
        """Detects and performs Google Login if credentials are provided."""
        if "accounts.google.com" not in page.url:
            return

        email = self.credentials.get("google_email") or os.getenv("GOOGLE_EMAIL")
        password = self.credentials.get("google_password") or os.getenv("GOOGLE_PASSWORD")

        if not email or not password:
            logger.warning("Redireted to Google Login but no credentials provided.")
            return

        logger.info(f"Attempting automated Google Login for {email}...")
        try:
            # 1. Fill Email
            await page.locator("input[type='email']").fill(email)
            await page.get_by_role("button", name="Next").click()
            await asyncio.sleep(2)

            # 2. Fill Password
            pw_input = page.locator("input[type='password']")
            await pw_input.wait_for(state="visible", timeout=10000)
            await pw_input.fill(password)
            await page.get_by_role("button", name="Next").click()

            # 3. Handle 'Confirm your recovery email' or other hurdles if they appear
            await asyncio.sleep(5)
            if "recovery" in page.url:
                logger.info("Handling recovery email challenge...")
                recovery_email = self.credentials.get("recovery_email")
                if recovery_email:
                    # Look for the recovery option
                    await page.get_by_text("Confirm your recovery email").click()
                    await page.locator("input[type='email']").fill(recovery_email)
                    await page.get_by_role("button", name="Next").click()

            # 4. Wait for Jules redirect
            logger.info("Waiting for Jules redirect after login...")
            await page.wait_for_url("**/jules.google.com/**", timeout=30000)
            logger.info("Automated login successful.")

            # Save new state
            await self.context.storage_state(path=self.state_path)
        except Exception as e:
            logger.error(f"Automated login failed: {e}")
            await page.screenshot(path="autologin_fail.png")

    async def _log_page_state(self, page: Page, step: str):
        url = page.url
        title = await page.title()
        logger.info(f"[{step}] URL: {url} | Title: {title}")
        try:
            safe_step = step.replace(" ", "_").lower()
            await page.screenshot(path=f"diag_{safe_step}.png")
        except:
            pass

    async def create_session(self, repo_full_name: str, branch: str) -> Optional[str]:
        """Creates a new session for a specific repo and branch."""
        async with self.semaphore:
            page = await self.context.new_page()
            try:
                logger.info(f"Navigating to jules.google.com for repo {repo_full_name}")
                await page.goto("https://jules.google.com", wait_until="domcontentloaded", timeout=60000)
                await self._log_page_state(page, "Navigated to Jules")

                # Check if we are at the login page
                if "accounts.google.com" in page.url:
                    await self.check_and_perform_autologin(page)
                    if "accounts.google.com" in page.url:
                        logger.error("Redirected to Google Login and autologin failed or was skipped.")
                        raise Exception("Authentication required. Please login again.")

                logger.info("Looking for 'New session' button")
                try:
                    btn = page.locator(SELECTORS["new_session_btn"]).first
                    await btn.wait_for(state="visible", timeout=60000)
                    logger.info("'New session' button is visible")
                except Exception as te:
                    await self._log_page_state(page, "Error Waiting For New Session Btn")
                    logger.error(f"Timeout waiting for 'New session' button. URL: {page.url}")
                    raise te

                await asyncio.sleep(1) # Human-like pause
                await btn.click()
                logger.info("Clicked 'New session'")

                # Search for the repo
                logger.info(f"Searching for repository: {repo_full_name}")
                search_input = page.locator(SELECTORS["repo_search_input"]).first
                await search_input.wait_for(state="visible", timeout=60000)
                await search_input.fill(repo_full_name)
                logger.info(f"Filled search input with {repo_full_name}")

                logger.info(f"Selecting repository: {repo_full_name}")
                # Wait a bit for search results to filter
                await asyncio.sleep(2)
                await self._log_page_state(page, "Search Results")

                repo_item = page.get_by_text(repo_full_name).first
                try:
                    await repo_item.wait_for(state="visible", timeout=60000)
                    await repo_item.click()
                    logger.info(f"Clicked on repo item: {repo_full_name}")
                except Exception:
                    logger.warning(f"Repository {repo_full_name} not found in search results.")
                    await self._log_page_state(page, "Repo Not Found In Search")

                    # Try to find 'Connect' or 'Add' buttons
                    connect_btns = page.locator("button:has-text('Connect'), button:has-text('Add'), :text('Connect to GitHub')")
                    count = await connect_btns.count()
                    if count > 0:
                        logger.info(f"Found {count} potential 'Connect' buttons. Repository might need to be authorized.")

                    # Check if there is a settings/config area
                    settings = page.locator(SELECTORS["settings_btn"]).first
                    if await settings.is_visible():
                        logger.info("Settings/Config button found. Repo might be manageable there.")

                    raise Exception(f"Repository '{repo_full_name}' not found or not connected. Please ensure it is authorized in Jules.")

                # Wait for session initialization
                logger.info("Waiting for session URL (this can take up to 2 minutes)...")
                await page.wait_for_url("**/sessions/*", timeout=120000)
                session_id = page.url.split("/")[-1]
                logger.info(f"Session created: {session_id}")
                await self._log_page_state(page, f"Session {session_id} Initialized")

                # Instruct Jules to checkout the branch
                logger.info(f"Instructing Jules to checkout branch: {branch}")
                await self._send_initial_instructions(page, branch)

                session = JulesSession(session_id, branch, page)
                self.sessions[session_id] = session
                return session_id
            except Exception as e:
                logger.error(f"Failed to create session for {repo_full_name}: {e}")
                await self._log_page_state(page, "Session Creation Failure")
                await page.close()
                raise e

    async def _send_initial_instructions(self, page: Page, branch: str):
        prompt = f"Please checkout a new branch named '{branch}' from the latest main/master. Then wait for further instructions."
        input_loc = page.locator(SELECTORS["ask_jules_input"]).first
        await input_loc.wait_for(state="visible", timeout=60000)
        await input_loc.fill(prompt)
        await input_loc.press("Enter")
        logger.info(f"Sent initial instructions for branch {branch}")

        # Wait for response start
        logger.info("Waiting for Jules response (can take up to 2 minutes)...")
        await page.wait_for_selector(SELECTORS["message_content"], timeout=120000)
        logger.info("Jules response detected")
        await self._log_page_state(page, "Initial Instructions Sent")

    async def send_message(self, session_id: str, message: str):
        session = self.sessions.get(session_id)
        if not session:
            return

        try:
            logger.info(f"Sending message to session {session_id}: {message[:50]}...")
            input_loc = session.page.locator(SELECTORS["ask_jules_input"]).first
            await input_loc.wait_for(state="visible", timeout=30000)
            await input_loc.fill(message)
            await input_loc.press("Enter")
            # Wait for any new activity to appear
            await asyncio.sleep(2)
            await self._log_page_state(session.page, f"Sent Message to {session_id}")
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")
            await self._log_page_state(session.page, f"Failed Send Message to {session_id}")

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
