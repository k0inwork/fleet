import asyncio
import os
import pytest
from hydra_controller import HydraController
from utils import setup_global_proxy, is_jules_installed, install_jules_cli

# Test configuration
TEST_REPO = "k0inwork/chntpw"
# Ensure PROXY_URL is set in the environment or passed here
PROXY_URL = os.getenv("PROXY_URL")

@pytest.fixture(scope="session", autouse=True)
def setup_proxy():
    if PROXY_URL:
        setup_global_proxy(PROXY_URL)

@pytest.mark.asyncio
async def test_jules_cli_installed():
    """Verify that Jules CLI is installed or can be installed."""
    if not is_jules_installed():
        success, msg = await install_jules_cli(PROXY_URL)
        assert success, f"Failed to install Jules CLI: {msg}"
    assert is_jules_installed()

@pytest.mark.asyncio
async def test_jules_session_lifecycle():
    """
    Verify the full lifecycle of a Jules session:
    1. Create a session
    2. Track activities/status
    (Note: This requires authentication to be already completed via 'jules login')
    """
    controller = HydraController(proxy_url=PROXY_URL)
    await controller.start()

    # Create a task
    instruction = "Analyze the project structure and summarize its purpose."
    session_id = await controller.create_session(TEST_REPO, instruction=instruction)

    assert session_id is not None, "Failed to create Jules session"
    print(f"Created session: {session_id}")

    # Poll for activities
    max_retries = 10
    found_activity = False
    for _ in range(max_retries):
        activities = await controller.get_activities(session_id)
        if activities:
            found_activity = True
            print(f"Activities for {session_id}: {activities}")
            break
        await asyncio.sleep(10)

    assert found_activity, f"No activities found for session {session_id}"

    # Verify session appears in 'remote list'
    # This is implicitly tested by get_activities in the CLI controller

    await controller.stop()

if __name__ == "__main__":
    # If running manually, ensure PROXY_URL is provided
    if not PROXY_URL:
        print("Warning: PROXY_URL not set. Tests might fail if Jules is not reachable.")
    asyncio.run(test_jules_session_lifecycle())
