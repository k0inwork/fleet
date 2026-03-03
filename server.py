import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from context_engine import ContextEngine
from scheduler import DAGScheduler, TaskStatus
from brain import Brain, NodeType
from agents_parser import AgentsManifest
from hydra_controller import HydraController
from github_verifier import GitHubVerifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

app = FastAPI(title="Jules Workflow Orchestrator")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class OrchestratorState:
    def __init__(self):
        self.config: dict = {}
        self.scheduler: Optional[DAGScheduler] = None
        self.is_running: bool = False
        self.hydra: Optional[HydraController] = None
        self.verifier: Optional[GitHubVerifier] = None
        self.agents_manifest: Optional[AgentsManifest] = None
        self.brain: Optional[Brain] = None

state = OrchestratorState()

class StartRequest(BaseModel):
    user_goal: str
    gemini_api_key: str
    github_token: str
    repo_full_name: str
    repo_path: str = "."
    proxy_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

class HILDecisionRequest(BaseModel):
    task_id: str
    decision: str # "approve", "reject", "retry"

async def orchestrator_loop():
    logger.info("Starting orchestrator loop...")
    state.is_running = True
    try:
        await state.hydra.start()

        while state.scheduler and not state.scheduler.is_finished() and state.is_running:
            ready_tasks = state.scheduler.get_ready_tasks()

            for task_id in ready_tasks:
                task_node = state.scheduler.nodes[task_id]

                # HIL / APPROVAL Node
                if task_node.task.node_type == NodeType.APPROVAL:
                    logger.info(f"Task {task_id} waiting for Human-in-the-Loop.")
                    state.scheduler.mark_waiting(task_id)
                    continue

                # Fallback Check
                fallback = state.agents_manifest.get_fallback(task_node.task.instruction)
                if fallback == "github_actions":
                    logger.info(f"Task {task_id} falling back to GitHub Actions...")
                    state.scheduler.mark_running(task_id, "GH_ACTION_MOCK")
                    # Mocking github actions completion
                    asyncio.create_task(mock_github_action(task_id))
                    continue

                # Dispatch to Hydra
                if len(state.hydra.sessions) < 3:
                    await dispatch_task_to_hydra(task_id)

            await verify_active_tasks()
            await asyncio.sleep(5) # Poll interval
    except Exception as e:
        logger.error(f"Fatal error in orchestrator: {e}")
    finally:
        if state.hydra:
            await state.hydra.stop()
        state.is_running = False
        logger.info("Orchestrator finished.")

async def mock_github_action(task_id: str):
    await asyncio.sleep(10)
    if state.scheduler:
        state.scheduler.mark_completed(task_id)

async def dispatch_task_to_hydra(task_id: str):
    task_node = state.scheduler.nodes[task_id]
    logger.info(f"Dispatching {task_id} to Hydra...")
    try:
        session_id = await state.hydra.create_session(state.config["repo_full_name"], task_node.task.branch)
        if session_id:
            state.scheduler.mark_running(task_id, session_id)
            await state.hydra.send_message(session_id, task_node.task.instruction)
        else:
            logger.error(f"Failed to create session for {task_id}")
    except Exception as e:
        logger.error(f"Error dispatching {task_id}: {e}")

async def verify_active_tasks():
    for task_id, node in state.scheduler.nodes.items():
        if node.status == TaskStatus.RUNNING and node.session_id != "GH_ACTION_MOCK":
            submitted, conflicted = await asyncio.to_thread(state.verifier.verify_pr, node.task.branch)
            if submitted:
                if conflicted:
                    state.scheduler.mark_conflicted(task_id)
                else:
                    state.scheduler.mark_completed(task_id)

@app.post("/api/start")
async def start_workflow(req: StartRequest, background_tasks: BackgroundTasks):
    if state.is_running:
        raise HTTPException(status_code=400, detail="Orchestrator is already running.")

    state.config = req.dict()
    state.brain = Brain(req.gemini_api_key)
    state.agents_manifest = AgentsManifest(req.repo_path)
    state.hydra = HydraController(req.proxy_url)
    state.verifier = GitHubVerifier(req.github_token, req.repo_full_name, req.proxy_url)

    # Init context and graph
    context_engine = ContextEngine(req.repo_path)
    context = await asyncio.to_thread(context_engine.get_context)

    try:
        task_graph = await asyncio.to_thread(state.brain.generate_task_graph, req.user_goal, context)
        state.scheduler = DAGScheduler(task_graph)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate task graph: {e}")

    background_tasks.add_task(orchestrator_loop)
    return {"status": "started", "tasks_count": len(task_graph.tasks)}

@app.get("/api/status")
async def get_status():
    if not state.scheduler:
        return {"status": "idle", "tasks": []}

    tasks = []
    for tid, node in state.scheduler.nodes.items():
        tasks.append({
            "id": tid,
            "status": node.status,
            "instruction": node.task.instruction,
            "session_id": node.session_id
        })

    return {
        "status": "running" if state.is_running else "finished",
        "tasks": tasks
    }

@app.get("/api/vms")
async def get_vms():
    if not state.hydra:
        return {"vms": []}

    vms = []
    for sid, session in state.hydra.sessions.items():
        vms.append({
            "session_id": sid,
            "branch": session.branch
        })
    return {"vms": vms}

@app.get("/api/vms/{session_id}/logs")
async def get_vm_logs(session_id: str):
    if not state.hydra or session_id not in state.hydra.sessions:
        raise HTTPException(status_code=404, detail="VM session not found.")

    # Since real hydra_controller doesn't expose a tail_logs method cleanly yet,
    # we simulate fetching recent activities/messages.
    activities = await state.hydra.get_activities(session_id)
    # We return the raw text representations of activities for simplicity
    logs = [str(act) for act in activities] if activities else ["No logs available yet."]

    return {"session_id": session_id, "logs": logs}

@app.post("/api/hil/decision")
async def hil_decision(req: HILDecisionRequest):
    if not state.scheduler:
        raise HTTPException(status_code=400, detail="Scheduler not running.")

    if req.task_id not in state.scheduler.nodes:
        raise HTTPException(status_code=404, detail="Task not found.")

    if req.decision == "approve":
        state.scheduler.mark_approved(req.task_id)
    elif req.decision == "reject":
        state.scheduler.mark_rejected(req.task_id)
    elif req.decision == "retry":
        state.scheduler.mark_retry(req.task_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid decision.")

    return {"status": "success", "task_id": req.task_id, "decision": req.decision}

# Serve React Frontend
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve index.html for root and any non-api paths (for react router if added later)
        # We ensure not to intercept /api routes via order of declaration.
        if not full_path.startswith("api/"):
            index_path = os.path.join(FRONTEND_DIST, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Not Found")
else:
    logger.warning("Frontend dist folder not found. Please run 'npm run build' in the frontend directory.")
