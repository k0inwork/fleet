import asyncio
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Log, Label, Input, Button, TabbedContent, TabPane
from textual.reactive import reactive

from brain import Brain, TaskGraph
from context_engine import ContextEngine
from hydra_controller import HydraController
from scheduler import DAGScheduler, TaskStatus
from github_verifier import GitHubVerifier
from utils import setup_global_proxy, check_proxy

class Orchestrator:
    def __init__(self, config: dict, log_callback):
        self.config = config
        self.log = log_callback
        self.context_engine = ContextEngine(config.get("repo_path", "."))
        self.brain = Brain(config["gemini_api_key"])
        self.hydra = HydraController(config.get("proxy_url"))
        self.verifier = GitHubVerifier(config["github_token"], config["repo_full_name"], config.get("proxy_url"))
        self.scheduler = None
        self.is_running = False

    async def run(self, user_goal: str):
        self.log(f"Starting orchestration for goal: {user_goal}")

        # 1. Check & Setup Proxy
        if self.config.get("proxy_url"):
            setup_global_proxy(self.config["proxy_url"])
            if not check_proxy(self.config["proxy_url"]):
                self.log("Proxy check failed! Aborting.")
                return

        # 2. Context Indexing
        context = self.context_engine.get_context()
        self.log(f"Context indexed: {len(context.file_tree)} files.")

        # 3. Task Graph Generation
        self.log("Generating Task Graph via Gemini...")
        try:
            task_graph = self.brain.generate_task_graph(user_goal, context)
            self.scheduler = DAGScheduler(task_graph)
            self.log(f"Task Graph generated with {len(task_graph.tasks)} tasks.")
        except Exception as e:
            self.log(f"Error generating Task Graph: {e}")
            return

        # 4. Hydra Start
        await self.hydra.start()

        # 5. Execution Loop
        self.is_running = True
        try:
            while not self.scheduler.is_finished() and self.is_running:
                # Dispatch tasks
                ready_tasks = self.scheduler.get_ready_tasks()
                for task_id in ready_tasks:
                    if len(self.hydra.sessions) < 3: # Concurrency limit
                        await self.dispatch_task(task_id)

                # Verify PRs
                await self.verify_active_tasks()

                await asyncio.sleep(10) # Poll interval
        finally:
            await self.hydra.stop()
            self.log("Orchestration finished.")

    async def dispatch_task(self, task_id: str):
        task_node = self.scheduler.nodes[task_id]
        self.log(f"Dispatching task {task_id} to Hydra...")

        # Create or Reuse Session
        session_id = await self.hydra.create_session(self.config["repo_full_name"], task_node.task.branch)
        if session_id:
            self.scheduler.mark_running(task_id, session_id)
            await self.hydra.send_message(session_id, task_node.task.instruction)
            self.log(f"Task {task_id} is now running in session {session_id}")
        else:
            self.log(f"Failed to create session for task {task_id}")

    async def verify_active_tasks(self):
        for task_id, node in self.scheduler.nodes.items():
            if node.status == TaskStatus.RUNNING:
                submitted, conflicted = self.verifier.verify_pr(node.task.branch)
                if submitted:
                    if conflicted:
                        self.log(f"Task {task_id} has merge conflicts!")
                        self.scheduler.mark_conflicted(task_id)
                        # Here we would assign an Integration Specialist
                    else:
                        self.log(f"Task {task_id} PR detected and healthy. Marking COMPLETED.")
                        self.scheduler.mark_completed(task_id)
                        # Session is now idle - could be recycled
                else:
                    # Check for "confusion" markers in activities (simplified)
                    activities = await self.hydra.get_activities(node.session_id)
                    # if activities... log or handle

class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Please log in to your Google account in the opened browser window."),
            Label("Once you are at the Jules dashboard and see 'New session', return here and press 'Done'."),
            Button("Done", id="login-done-btn"),
            id="login-dialog"
        )

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "login-done-btn":
            if hasattr(self.app, "temp_hydra"):
                await self.app.temp_hydra.stop()
            self.app.pop_screen()

class HydraApp(App):
    CSS = """
    Screen { layout: vertical; }
    #main-container { height: 1fr; }
    #left-panel { width: 30%; border: solid green; }
    #center-panel { width: 40%; border: solid blue; }
    #right-panel { width: 30%; border: solid white; }
    .panel-title { text-align: center; background: $accent; color: white; margin: 1; }
    #main-log { height: 1fr; }
    #config-form { padding: 2; border: double red; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Config", id="config-tab"):
                with Vertical(id="config-form"):
                    yield Label("Configuration")
                    yield Input(placeholder="Gemini API Key", id="api-key", password=True)
                    yield Input(placeholder="GitHub Token", id="gh-token", password=True)
                    yield Input(placeholder="Repo (owner/repo)", id="repo-name")
                    yield Input(placeholder="Proxy URL (socks5://...)", id="proxy-url")
                    yield Input(placeholder="User Goal", id="user-goal")
                    yield Horizontal(
                        Button("Login to Google", id="login-btn"),
                        Button("Start Hydra", variant="success", id="start-btn")
                    )
            with TabPane("Monitor", id="monitor-tab"):
                with Horizontal(id="main-container"):
                    with Vertical(id="left-panel"):
                        yield Label("Tasks", classes="panel-title")
                        yield Container(id="task-list")
                    with Vertical(id="center-panel"):
                        yield Label("Hydra Fleet", classes="panel-title")
                        with Vertical(id="fleet-status"):
                            yield Static("Slot 1: Idle", id="slot-1")
                            yield Static("Slot 2: Idle", id="slot-2")
                            yield Static("Slot 3: Idle", id="slot-3")
                    with Vertical(id="right-panel"):
                        yield Label("Logs", classes="panel-title")
                        yield Log(id="main-log")
        yield Footer()

    async def on_mount(self):
        self.set_interval(2, self.update_ui)

    def update_ui(self):
        if hasattr(self, "orchestrator") and self.orchestrator.scheduler:
            # Update Task List
            task_container = self.query_one("#task-list")
            status_map = self.orchestrator.scheduler.get_all_status()

            # Simple diff-based update to avoid flickering
            existing_tasks = {child.id: child for child in task_container.walk_children() if child.id}

            for task_id, status in status_map.items():
                widget_id = f"task-{task_id}"
                if widget_id in existing_tasks:
                    existing_tasks[widget_id].update(f"{task_id}: {status}")
                else:
                    task_container.mount(Label(f"{task_id}: {status}", id=widget_id))

            # Update Fleet Status
            for i, (sid, session) in enumerate(self.orchestrator.hydra.sessions.items(), 1):
                if i <= 3:
                    self.query_one(f"#slot-{i}").update(f"Slot {i}: {sid} ({session.branch})")

    def log_to_ui(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            self.query_one("#main-log").write_line(f"[{timestamp}] {message}")
        except:
            pass # App might not be fully mounted

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "login-btn":
            # Start hydra in non-headless mode for login
            proxy_url = self.query_one("#proxy-url").value or os.getenv("PROXY_URL")
            self.temp_hydra = HydraController(proxy_url)
            await self.temp_hydra.start(headless=False)
            asyncio.create_task(self.temp_hydra.login()) # This will wait for login
            self.push_screen(LoginScreen())

        elif event.button.id == "start-btn":
            config = {
                "gemini_api_key": self.query_one("#api-key").value or os.getenv("GEMINI_API_KEY"),
                "github_token": self.query_one("#gh-token").value or os.getenv("GITHUB_TOKEN"),
                "repo_full_name": self.query_one("#repo-name").value or os.getenv("REPO_NAME"),
                "proxy_url": self.query_one("#proxy-url").value or os.getenv("PROXY_URL"),
                "repo_path": "."
            }
            goal = self.query_one("#user-goal").value

            if not all([config["gemini_api_key"], config["github_token"], config["repo_full_name"], goal]):
                self.log_to_ui("Missing required configuration or goal!")
                return

            self.query_one(TabbedContent).active = "monitor-tab"
            self.orchestrator = Orchestrator(config, self.log_to_ui)
            asyncio.create_task(self.orchestrator.run(goal))

if __name__ == "__main__":
    app = HydraApp()
    app.run()
