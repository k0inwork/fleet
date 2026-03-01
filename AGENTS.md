# Agent Instructions: Jules Bridge Daemon Integration

You are participating in a managed execution session controlled by a Hydra Orchestrator. To facilitate external visibility and control, you MUST use the provided `JulesBridge` MCP server tools.

## Mandatory Workflow

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
If you need clarification or if the controller sends an `ASK` command:
- If the controller asks a question (returned by `wait_for_instruction`), you can reply using `report_event(event_type="INFO", payload={"response": "..."})` and then call `wait_for_instruction()` again to see the next command.

### 5. Task Completion
When you have finished your task:
- `report_event(event_type="TASK_FINISHED", payload={"status": "Success/Failure", "summary": "..."})`

## Commands from Controller
The `wait_for_instruction()` tool will return a JSON object containing:
- `command`: One of `CONTINUE`, `REJECT`, `PAUSE`, `STOP`, `EDIT_PLAN`, or `ASK`.
- `message`: (Optional) A message or question from the human controller.

You MUST obey these commands. For example, if `REJECT` or `STOP` is received, do not proceed with the current plan.
