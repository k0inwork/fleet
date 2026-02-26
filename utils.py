import os
import socket
import requests
import logging
import json
import socks
from typing import Dict, List, Optional

logger = logging.getLogger("ProxyGuard")

def check_proxy(proxy_url: str) -> bool:
    """Verifies that the proxy is working and returning a valid response."""
    if not proxy_url:
        return False

    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    try:
        # Use a simple IP check service
        response = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
        if response.status_code == 200:
            logger.info(f"Proxy is working. Public IP: {response.text}")
            return True
    except Exception as e:
        logger.error(f"Proxy check failed: {e}")

    return False

def setup_global_proxy(proxy_url: str):
    """Sets environment variables and global socket proxy for SOCKS5 support."""
    if proxy_url:
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url
        os.environ['all_proxy'] = proxy_url
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url

        os.environ['grpc_proxy'] = proxy_url

        if "socks5" in proxy_url:
            try:
                # Parse host and port
                host_port = proxy_url.split("://")[-1].split("@")[-1] # Handle auth if present
                host = host_port.split(":")[0]
                port = int(host_port.split(":")[1])

                # Global monkey-patch for SOCKS5
                socks.set_default_proxy(socks.SOCKS5, host, port)
                socket.socket = socks.socksocket
                logger.info(f"Global SOCKS5 proxy set to {host}:{port} via socket.socket override")
            except Exception as e:
                logger.error(f"Failed to set global SOCKS5 proxy: {e}")

        # For git and other tools
        proxy_host_port = proxy_url.split('://')[-1]
        os.environ['GIT_PROXY_COMMAND'] = f"nc -X 5 -x {proxy_host_port} %h %p"

def check_jules_login_status(state_path: str = "state.json", proxy_url: Optional[str] = None) -> bool:
    """Uses cookies from state.json to verify authentication via lightweight requests."""
    if not os.path.exists(state_path) or os.path.getsize(state_path) == 0:
        return False

    try:
        with open(state_path, "r") as f:
            state = json.load(f)

        session = requests.Session()
        if proxy_url:
            session.proxies = {"http": proxy_url, "https": proxy_url}

        # Convert Playwright cookies to requests-compatible cookies
        for cookie in state.get("cookies", []):
            session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"])

        # Check if we can reach an authenticated endpoint
        # The Jules main page often redirects or contains different content when logged in
        # Alternatively, we can check for a common API endpoint or specific text in the HTML
        response = session.get("https://jules.google.com", timeout=10)

        # Simple heuristic: If we are redirected to accounts.google.com, we are not logged in
        if "accounts.google.com" in response.url:
            return False

        # Check for presence of 'New session' text or other authenticated markers
        if "New session" in response.text or "Sign out" in response.text:
            return True

        return False
    except Exception as e:
        logger.error(f"Failed to check login status: {e}")
        return False
