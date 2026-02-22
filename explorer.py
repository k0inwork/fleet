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

    async def explore(self):
        await self.controller.start(headless=True)
        page = await self.controller.context.new_page()

        try:
            logger.info("Navigating to jules.google.com for exploration...")
            await page.goto("https://jules.google.com", wait_until="domcontentloaded", timeout=60000)

            # 1. Map Dashboard
            await self._map_current_page(page, "Dashboard")

            # 2. Try to find settings
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

            # 3. Save map
            with open("jules_ui_map.json", "w") as f:
                json.dump(self.ui_map, f, indent=2)
            logger.info("UI Map saved to jules_ui_map.json")

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
        finally:
            await self.controller.stop()

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
