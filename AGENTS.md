# Agent Instructions: Jules Bridge Daemon Integration

You are participating in a managed execution session controlled by a Hydra Orchestrator. To facilitate external visibility and control, you MUST use the provided `JulesBridge` MCP server tools.

## Mandatory Workflow

### 0. Daemon Check
The bridge daemon should be running in the background. If you cannot connect to the `JulesBridge` MCP server, you MUST start it manually before proceeding:
`nohup python3 ~/bridge_daemon.py > ~/bridge_daemon.log 2>&1 &`

### 1. Initialization
At the very beginning of your session, you MUST call:
- `initialize_session(repo, branch)`: Provide the repository name and the branch you are working on.

### 2. Planning and Approval
Before executing any major tasks or code changes:
- `report_event(event_type="PLAN_CREATED", payload={"plan": [...]})`: Report your proposed plan.
- `wait_for_instruction()`: This tool will block your execution. You MUST wait for it to return a command from the controller.

### 3. Execution Reporting
During your work, keep the controller informed:
- `report_event(event_type="STEP_STARTED", payload={"step": "..."})`
- `report_event(event_type="STEP_COMPLETED", payload={"result": "..."})`

### 4. Interactive Feedback
If you receive an `ASK` command (returned by `wait_for_instruction`), you can reply using `report_event(event_type="INFO", payload={"response": "..."})` and then call `wait_for_instruction()` again.

### 5. Task Completion
When you have finished your task:
- `report_event(event_type="TASK_FINISHED", payload={"status": "Success/Failure", "summary": "..."})`

The bridge daemon provides these tools via MCP.
