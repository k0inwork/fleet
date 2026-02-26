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
    def __init__(self, proxy_url: Optional[str] = None, state_path: str = "state.json", log_callback=None, credentials: Optional[Dict] = None):
        self.proxy_url = proxy_url
        self.state_path = state_path
        self.log = log_callback or logger.info
        self.controller = HydraController(proxy_url, state_path, credentials=credentials)
        self.ui_map = {}

    async def explore(self, repo_full_name: Optional[str] = None, max_pages: int = 10):
        await self.controller.start(headless=True)
        page = await self.controller.context.new_page()

        self.ui_map = {} # Explicitly clear current map
        visited = set()
        to_visit = ["https://jules.google.com"]
        pages_mapped = 0

        try:
            while to_visit and pages_mapped < max_pages:
                url = to_visit.pop(0)
                if url in visited or "logout" in url.lower():
                    continue

                self.log(f"Crawling ({pages_mapped+1}/{max_pages}): {url}")
                try:
                    # Try to dismiss any blocking modals from previous page
                    try:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                    except: pass

                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2) # Wait for dynamic content

                    # Ensure authenticated for EVERY page crawl
                    await self.controller.ensure_logged_in(page)

                    # If we got redirected to a visited URL, skip
                    if page.url != url and page.url in visited:
                        self.log(f"Redirected to already visited URL: {page.url}")
                        continue

                    page_name = await page.title() or url.split("/")[-1] or "Home"
                    await self._map_current_page(page, page_name)
                    visited.add(url)
                    pages_mapped += 1

                    # Extract internal links
                    links = await page.eval_on_selector_all(
                        "a[href]",
                        "elements => elements.map(el => el.href)"
                    )
                    for link in links:
                        if "jules.google.com" in link and link not in visited and link not in to_visit:
                            if not any(x in link.lower() for x in ["logout", "signout", "delete"]):
                                to_visit.append(link)
                except Exception as e:
                    self.log(f"Failed to crawl {url}: {e}")

            # Active Exploration if repo is provided
            if repo_full_name:
                await self.active_explore(page, repo_full_name)

            # Save map and refined selectors
            with open("jules_ui_map.json", "w") as f:
                json.dump(self.ui_map, f, indent=2)
            self.log(f"UI Map with {pages_mapped} pages saved to jules_ui_map.json")

            self._generate_refined_selectors()

        except Exception as e:
            self.log(f"Exploration failed: {e}")
        finally:
            await self.controller.stop()

    async def active_explore(self, page: Page, repo_full_name: str):
        self.log(f"Starting active exploration for repo: {repo_full_name}")

        try:
            # 1. Create Session
            self.log("Creating session for active test...")
            session_id = await self.controller.create_session(repo_full_name, "explorer-test-branch")
            if not session_id:
                self.log("Failed to create session for active exploration")
                return

            await self._map_current_page(page, "Session View")

            # 2. Send command and observe activity
            self.log("Sending simple command to observe activity...")
            await self.controller.send_message(session_id, "Please create a dummy test file named 'explorer_test.txt' with content 'hello world'. Then wait.")
            await asyncio.sleep(5)
            await self._map_current_page(page, "Session Activity Observed")

            # 3. Discover management buttons (Pause, Stop, etc.)
            self.log("Discovering session management buttons...")
            management_selectors = [
                "button:has-text('Pause')", "button:has-text('Stop')",
                "button:has-text('Restart')", "button:has-text('Resume')",
                "[aria-label*='options']", "[aria-label*='menu']"
            ]

            for selector in management_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=1000):
                        self.log(f"Detected management element: {selector}")
                except:
                    continue

            # 4. Mind Wipe test
            self.log("Performing mind wipe discovery...")
            await self.controller.mind_wipe(session_id)
            await asyncio.sleep(3)
            await self._map_current_page(page, "Post Mind Wipe")

            # 5. Archive and Cleanup
            self.log("Finishing active exploration and archiving session...")
            # Logic for archiving is often in a menu
            try:
                await page.locator("button:has-text('Session options')").click()
                await asyncio.sleep(1)
                await page.locator("text='Archive'").click()
                self.log("Session archived.")
            except:
                self.log("Could not find Archive button via default path.")

        except Exception as e:
            self.log(f"Active exploration failed: {e}")

    def _generate_refined_selectors(self):
        """Analyzes the ui_map and generates refined_selectors.json."""
        refined = {}

        # Heuristic: Look for elements that match our desired actions
        # We'll look across all mapped pages for the best identifiers
        for page_name, data in self.ui_map.items():
            for el in data["elements"]:
                text = el["text"].lower()
                aria = (el["aria_label"] or "").lower()
                testid = (el["data_testid"] or "").lower()
                name = (el["name"] or "").lower()
                title = (el["title"] or "").lower()

                # New Session
                if any(x in text or x in aria or x in testid for x in ["new session", "create session"]):
                    refined["new_session_btn"] = self._build_selector(el)

                # Repo Search
                if any(x in el["placeholder"].lower() or x in aria or x in testid for x in ["search", "repository"]):
                    refined["repo_search_input"] = self._build_selector(el)

                # Ask Jules
                if any(x in el["placeholder"].lower() or x in aria or x in testid for x in ["ask jules", "message"]):
                    refined["ask_jules_input"] = self._build_selector(el)

                # Management
                if "pause" in text or "pause" in aria: refined["pause_btn"] = self._build_selector(el)
                if any(x in text or x in aria for x in ["resume", "restart", "play"]): refined["resume_btn"] = self._build_selector(el)
                if "archive" in text or "archive" in aria: refined["archive_btn"] = self._build_selector(el)

        if refined:
            with open("refined_selectors.json", "w") as f:
                json.dump(refined, f, indent=2)
            logger.info(f"Generated {len(refined)} refined selectors in refined_selectors.json")

    def _build_selector(self, el: Dict) -> str:
        """Builds a robust CSS selector from element metadata, prioritizing stable attributes."""
        if el["data_testid"]:
            return f"[data-testid='{el['data_testid']}']"

        if el["id"] and not any(char.isdigit() for char in el["id"][-4:]): # Avoid dynamic IDs
            return f"#{el['id']}"

        if el["name"]:
            return f"[name='{el['name']}']"

        if el["aria_label"]:
            return f"[aria-label='{el['aria_label']}']"

        if el["title"]:
            return f"[title='{el['title']}']"

        tag = el["tag"].lower()
        if el["placeholder"]:
            return f"{tag}[placeholder='{el['placeholder']}']"

        if el["classes"]:
            # Avoid classes that look like Tailwind or random hashes
            classes = [c for c in el["classes"].split() if len(c) > 3 and not any(char.isdigit() for char in c)]
            if classes:
                return f"{tag}.{'.'.join(classes[:2])}"

        return tag

    async def _map_current_page(self, page: Page, page_name: str):
        # Wait for page to be ready
        try:
            await page.wait_for_selector("body", timeout=10000)
            # Try to wait for at least one interactive element to appear
            await page.wait_for_selector("button, a, input, textarea", timeout=5000)
        except:
            pass

        # Additional wait for dynamic SPAs
        await asyncio.sleep(3)

        # Ensure unique page name if title is duplicate
        orig_name = page_name
        counter = 1
        while page_name in self.ui_map:
            page_name = f"{orig_name} ({counter})"
            counter += 1

        self.log(f"Mapping page: {page_name}")
        safe_name = page_name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_').lower()

        # 1. Scrape interactive elements with extended metadata
        interactives = []
        for retry in range(2):
            interactives = await page.eval_on_selector_all(
                "button, a, input, textarea, [role='button'], [data-testid]",
                """
            elements => elements.map(el => {
                return {
                    tag: el.tagName,
                    text: (el.innerText || el.value || '').trim(),
                    placeholder: el.placeholder || '',
                    id: el.id,
                    classes: el.className,
                    aria_label: el.getAttribute('aria-label'),
                    data_testid: el.getAttribute('data-testid'),
                    name: el.getAttribute('name'),
                    role: el.getAttribute('role'),
                    title: el.getAttribute('title'),
                    href: el.getAttribute('href'),
                    type: el.getAttribute('type'),
                    isVisible: el.offsetWidth > 0 && el.offsetHeight > 0
                }
            })
            """
            )
            if len(interactives) > 0:
                break
            if retry == 0:
                self.log(f"No interactive elements found on {page_name}, retrying in 3s...")
                await asyncio.sleep(3)

        self.log(f"Found {len(interactives)} interactive elements on {page_name}")

        # 2. Capture Accessibility Tree (Optional, might not be supported in all environments)
        ax_tree = None
        try:
            ax_tree = await page.accessibility.snapshot()
        except:
            pass

        # 3. Dump DOM Snapshot
        dom_path = f"dom_{safe_name}.html"
        content = await page.content()
        with open(dom_path, "w") as f:
            f.write(content)

        self.ui_map[page_name] = {
            "url": page.url,
            "title": await page.title(),
            "elements": interactives,
            "ax_tree": ax_tree,
            "dom_snapshot": dom_path
        }

        # 4. Take a screenshot
        screenshot_path = f"explore_{safe_name}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        self.log(f"Deep Scrape artifacts for {page_name}: {screenshot_path}, {dom_path}")

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
