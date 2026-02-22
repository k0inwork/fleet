import asyncio
import os
import json
import logging
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional, List, Dict
from hydra_controller import HydraController

# Setup specialized logger for exploration
logger = logging.getLogger("JulesExplorer")

class JulesExplorer:
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json"):
        self.proxy_url = proxy_url
        self.state_path = state_path
        self.controller = HydraController(proxy_url, state_path)
        self.ui_map = {}

    async def explore(self, repo_full_name: Optional[str] = None):
        await self.controller.start(headless=True)
        page = await self.controller.context.new_page()

        try:
            logger.info("Navigating to jules.google.com for exploration...")
            await page.goto("https://jules.google.com", wait_until="domcontentloaded", timeout=60000)

            # 1. Map Dashboard
            await self._map_current_page(page, "Dashboard")

            # 2. Try to find settings
            await self._explore_settings(page)

            # 3. Active Exploration if repo is provided
            if repo_full_name:
                await self.active_explore(page, repo_full_name)

            # 4. Save map and refined selectors
            with open("jules_ui_map.json", "w") as f:
                json.dump(self.ui_map, f, indent=2)
            logger.info("UI Map saved to jules_ui_map.json")

            self._generate_refined_selectors()

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
        finally:
            await self.controller.stop()

    async def _explore_settings(self, page: Page):
        settings_selectors = [
            "[aria-label*='Settings']",
            "button:has-text('Settings')",
            "a[href*='settings']",
            "[class*='settings']"
        ]

        for selector in settings_selectors:
            try:
                settings_btn = page.locator(selector).first
                if await settings_btn.is_visible(timeout=2000):
                    logger.info(f"Found settings via {selector}, clicking...")
                    await settings_btn.click()
                    await asyncio.sleep(2)
                    await self._map_current_page(page, "Settings")
                    await page.go_back()
                    break
            except:
                continue

    async def active_explore(self, page: Page, repo_full_name: str):
        logger.info(f"Starting active exploration for repo: {repo_full_name}")

        try:
            # 1. Create Session
            logger.info("Creating session for active test...")
            session_id = await self.controller.create_session(repo_full_name, "explorer-test-branch")
            if not session_id:
                logger.error("Failed to create session for active exploration")
                return

            await self._map_current_page(page, "Session View")

            # 2. Send command and observe activity
            logger.info("Sending simple command to observe activity...")
            await self.controller.send_message(session_id, "Please create a dummy test file named 'explorer_test.txt' with content 'hello world'. Then wait.")
            await asyncio.sleep(5)
            await self._map_current_page(page, "Session Activity Observed")

            # 3. Discover management buttons (Pause, Stop, etc.)
            logger.info("Discovering session management buttons...")
            management_selectors = [
                "button:has-text('Pause')", "button:has-text('Stop')",
                "button:has-text('Restart')", "button:has-text('Resume')",
                "[aria-label*='options']", "[aria-label*='menu']"
            ]

            for selector in management_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=1000):
                        logger.info(f"Detected management element: {selector}")
                except:
                    continue

            # 4. Mind Wipe test
            logger.info("Performing mind wipe discovery...")
            await self.controller.mind_wipe(session_id)
            await asyncio.sleep(3)
            await self._map_current_page(page, "Post Mind Wipe")

            # 5. Archive and Cleanup
            logger.info("Finishing active exploration and archiving session...")
            # Logic for archiving is often in a menu
            try:
                await page.locator("button:has-text('Session options')").click()
                await asyncio.sleep(1)
                await page.locator("text='Archive'").click()
                logger.info("Session archived.")
            except:
                logger.warning("Could not find Archive button via default path.")

        except Exception as e:
            logger.error(f"Active exploration failed: {e}")

    def _generate_refined_selectors(self):
        """Analyzes the ui_map and generates refined_selectors.json."""
        refined = {}

        # Heuristic: Look for elements that match our desired actions
        # We'll look across all mapped pages for the best identifiers
        for page_name, data in self.ui_map.items():
            for el in data["elements"]:
                text = el["text"].lower()
                aria = (el["aria_label"] or "").lower()

                # New Session
                if "new session" in text or "new session" in aria:
                    refined["new_session_btn"] = self._build_selector(el)

                # Repo Search
                if "search" in el["placeholder"].lower() or "repository" in el["placeholder"].lower():
                    refined["repo_search_input"] = self._build_selector(el)

                # Ask Jules
                if "ask jules" in el["placeholder"].lower():
                    refined["ask_jules_input"] = self._build_selector(el)

                # Management
                if "pause" in text: refined["pause_btn"] = self._build_selector(el)
                if "resume" in text or "restart" in text: refined["resume_btn"] = self._build_selector(el)
                if "archive" in text: refined["archive_btn"] = self._build_selector(el)

        if refined:
            with open("refined_selectors.json", "w") as f:
                json.dump(refined, f, indent=2)
            logger.info(f"Generated {len(refined)} refined selectors in refined_selectors.json")

    def _build_selector(self, el: Dict) -> str:
        """Builds a robust CSS selector from element metadata."""
        if el["id"]:
            return f"#{el['id']}"

        if el["aria_label"]:
            return f"[aria-label='{el['aria_label']}']"

        tag = el["tag"].lower()
        if el["placeholder"]:
            return f"{tag}[placeholder='{el['placeholder']}']"

        if el["classes"]:
            # Use first few classes that aren't too generic
            cls = ".".join(el["classes"].split()[:2])
            if cls: return f"{tag}.{cls}"

        return tag

    async def _map_current_page(self, page: Page, page_name: str):
        logger.info(f"Mapping page: {page_name}")
        elements = []

        # Scrape interactive elements
        interactives = await page.eval_on_selector_all(
            "button, a, input, textarea, [role='button']",
            """
            elements => elements.map(el => {
                return {
                    tag: el.tagName,
                    text: el.innerText || el.value || '',
                    placeholder: el.placeholder || '',
                    id: el.id,
                    classes: el.className,
                    aria_label: el.getAttribute('aria-label'),
                    href: el.getAttribute('href'),
                    type: el.getAttribute('type'),
                    role: el.getAttribute('role')
                }
            })
            """
        )

        self.ui_map[page_name] = {
            "url": page.url,
            "title": await page.title(),
            "elements": interactives
        }

        # Take a screenshot
        screenshot_path = f"explore_{page_name.lower()}.png"
        await page.screenshot(path=screenshot_path)
        logger.info(f"Screenshot for {page_name} saved to {screenshot_path}")

if __name__ == "__main__":
    # Configure logging to console for standalone run
    logging.basicConfig(level=logging.INFO)

    # Try to load proxy from config.json if explorer is run manually
    proxy = None
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            cfg = json.load(f)
            proxy = cfg.get("proxy_url")

    explorer = JulesExplorer(proxy_url=proxy)
    asyncio.run(explorer.explore())
