import logging
import requests
from github import Github, GithubException
from typing import Optional, List, Tuple
import socks
import socket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GitHubVerifier")

class GitHubVerifier:
    def __init__(self, token: str, repo_full_name: str, proxy_url: Optional[str] = None):
        self.repo_full_name = repo_full_name
        self.token = token

        # Setup Proxy if provided
        self.session = requests.Session()
        if proxy_url:
            # Example: socks5://localhost:9050
            self.session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }

        self.gh = Github(auth=None, base_url="https://api.github.com", login_or_token=token)
        # Note: PyGithub doesn't easily take a custom session for its internal calls without some work.
        # However, for our purposes, we can use the Github object and hope it respects environment variables
        # or we can use requests directly for what we need.
        # Actually, PyGithub uses 'requests' internally. We can try setting env vars.

    def verify_pr(self, branch_name: str) -> Tuple[bool, bool]:
        """Returns (is_submitted, has_conflict)."""
        try:
            repo = self.gh.get_repo(self.repo_full_name)
            pulls = repo.get_pulls(state='open', head=f"{repo.owner.login}:{branch_name}")

            if pulls.totalCount > 0:
                pr = pulls[0]
                # Check mergeable state
                # Note: mergeable can be None if GitHub is still calculating it
                mergeable = pr.mergeable
                has_conflict = False
                if mergeable is False:
                    has_conflict = True

                return True, has_conflict

            return False, False
        except Exception as e:
            logger.error(f"Error verifying PR for branch {branch_name}: {e}")
            return False, False

    def create_pr(self, branch_name: str, title: str, body: str, base: str = "main"):
        try:
            repo = self.gh.get_repo(self.repo_full_name)
            pr = repo.create_pull(title=title, body=body, head=branch_name, base=base)
            return pr
        except Exception as e:
            logger.error(f"Error creating PR for branch {branch_name}: {e}")
            return None
