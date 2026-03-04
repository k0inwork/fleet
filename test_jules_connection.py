import pytest
import os
from hydra_controller import HydraController

@pytest.mark.asyncio
async def test_jules_connection_and_spawn():
    """
    Tests the connection to Jules by:
    1. Creating a minimal session.
    2. Looking for it in the list of sessions.
    3. Sending a cancel message to effectively close/abort it.
    """
    api_key = os.getenv("JULES_API_KEY")
    if not api_key:
        pytest.skip("JULES_API_KEY environment variable not set. Skipping connection test.")

    test_repo = "test/dummy_repo"
    credentials = {"jules_api_key": api_key}
    controller = HydraController(credentials=credentials)

    try:
        # Start client
        await controller.start()

        # 1. Create session directly
        session_id = await controller.create_session(test_repo, branch="test-connection-branch")
        assert session_id is not None, "Failed to create a session."

        # 2. See it in the list of sessions
        sessions = await controller.list_all_sessions()
        found = False
        for s in sessions:
            name = s.get("name") if isinstance(s, dict) else getattr(s, "name", None)
            if name == session_id:
                found = True
                break

        assert found, f"Session {session_id} was not found in the list of recent sessions."

        # 3. Cancel it
        await controller.send_message(session_id, "Cancel task. I no longer need this.")

        # If we reached here without exception, the test workflow is complete.
        assert True

    finally:
        await controller.stop()
