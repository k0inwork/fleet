import os
import socket
import requests
import logging

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
    """Sets environment variables for proxy support."""
    if proxy_url:
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url
        os.environ['all_proxy'] = proxy_url
        # For some libraries
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url

        # For gRPC (Gemini API)
        # Note: gRPC usually uses 'grpc_proxy' or 'https_proxy'
        # For SOCKS5, gRPC support varies.
        os.environ['grpc_proxy'] = proxy_url

        # For git and other tools
        # We need to handle 'socks5://' prefix
        proxy_host_port = proxy_url.split('://')[-1]
        os.environ['GIT_PROXY_COMMAND'] = f"nc -X 5 -x {proxy_host_port} %h %p"
