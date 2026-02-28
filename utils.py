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

def is_jules_installed() -> bool:
    """Checks if the jules CLI is installed and available in the PATH."""
    import subprocess
    try:
        subprocess.run(["jules", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

async def install_jules_cli(proxy_url: Optional[str] = None):
    """Installs the Jules CLI globally using npm with proxy configuration."""
    import asyncio
    env = os.environ.copy()

    if proxy_url:
        # Use npm config to set proxy temporarily or via environment variables
        # npm respects HTTP_PROXY and HTTPS_PROXY which are set in setup_global_proxy
        # But we can also pass them explicitly to the subprocess
        env['HTTP_PROXY'] = proxy_url
        env['HTTPS_PROXY'] = proxy_url
        env['npm_config_proxy'] = proxy_url
        env['npm_config_https_proxy'] = proxy_url

    logger.info("Installing @google/jules CLI...")
    cmd = ["npm", "install", "-g", "@google/jules"]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        logger.info("Jules CLI installed successfully.")
        return True, stdout.decode()
    else:
        logger.error(f"Jules CLI installation failed: {stderr.decode()}")
        return False, stderr.decode()
