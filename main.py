import asyncio
import os
import json
import traceback
import logging
from datetime import datetime
from typing import Optional, List, Dict

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer, Static, Log, Label, Input, Button, TabbedContent, TabPane, TextArea
from textual.screen import Screen

from hydra_controller import HydraController
from brain import Brain
from scheduler import DAGScheduler
from context_engine import ContextEngine

# Set up logging to file
logging.basicConfig(filename="hydra.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("HydraApp")

class Orchestrator:
    def __init__(self, config: Dict, log_callback: callable):
        self.config = config
        self.log_callback = log_callback
        self.brain = Brain(config["gemini_api_key"])
        self.hydra = HydraController(config.get("proxy_url"))
        self.context_engine = ContextEngine(config.get("repo_path", "."))
        self.scheduler: Optional[DAGScheduler] = None
        self.is_running = False

    def log(self, message: str):
        self.log_callback(message)

    async def run(self, user_goal: str):
        self.is_running = True
        self.log(f"Starting orchestration for goal: {user_goal}")

        try:
            self.log("Gathering codebase context...")
            context = self.context_engine.get_context()

            self.log("Generating task graph via Gemini...")
            task_graph = self.brain.generate_task_graph(user_goal, context)
            self.log(f"Generated {len(task_graph.tasks)} tasks.")

            self.scheduler = DAGScheduler(task_graph)

            self.log("Launching Hydra Controller...")
            await self.hydra.start(headless=True)

            while not self.scheduler.is_finished():
                ready_tasks = self.scheduler.get_ready_tasks()
                for task_id in ready_tasks:
                    task_node = self.scheduler.nodes[task_id]
                    self.log(f"Starting task: {task_id} on branch {task_node.task.branch}")

                    session_id = await self.hydra.create_session(
                        self.config["repo_full_name"],
                        task_node.task.branch
                    )

                    if session_id:
                        self.scheduler.mark_running(task_id, session_id)
                        await self.hydra.send_message(session_id, task_node.task.instruction)
                        self.log(f"Task {task_id} is now running in session {session_id}")
                    else:
                        self.log(f"Failed to create session for task {task_id}")
                        self.scheduler.mark_failed(task_id)

                await asyncio.sleep(10)
                await asyncio.sleep(5)

            self.log("All tasks processed.")
        except Exception as e:
            self.log(f"Orchestration failed: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.is_running = False
            await self.hydra.stop()

class HydraApp(App):
    CSS = """
    #main-container { height: 1fr; }
    #left-panel { width: 30%; border-right: solid $primary; padding: 1; }
    #center-panel { width: 70%; padding: 1; }
    #config-form { padding: 1; border: solid $accent; margin: 1; }
    #goal-header { background: $boost; padding: 1; margin-bottom: 1; }
    .panel-title { text-align: center; background: $primary; color: white; margin-bottom: 1; }
    #task-list { height: 1fr; border: solid $accent; }
    #fleet-status { height: 1fr; border: solid $accent; }
    #global-logs { height: 15; border-top: solid $primary; }
    .collapsed { display: none; }
    #bridge-sessions { width: 30%; border-right: solid $primary; padding: 1; }
    #bridge-controls { width: 70%; padding: 1; }
    #bridge-log { height: 1fr; border: solid $accent; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            with TabbedContent():
                with TabPane("Config", id="config-tab"):
                    with Vertical(id="config-form"):
                        yield Label("Configuration")
                        with Horizontal():
                            yield Input(placeholder="Gemini API Key", id="api-key", password=True)
                        with Horizontal():
                            yield Input(placeholder="GitHub Token", id="gh-token", password=True)
                        with Horizontal():
                            yield Input(placeholder="Repo (owner/repo)", id="repo-name")
                        with Horizontal():
                            yield Input(placeholder="Proxy URL (socks5://...)", id="proxy-url")
                with TabPane("Monitor", id="monitor-tab"):
                    with Vertical(id="goal-header"):
                        with Vertical(id="goal-container", classes="collapsed"):
                            with Horizontal():
                                yield Label("SYSTEM GOAL")
                                yield Button("Toggle Size", id="toggle-goal-btn")
                            yield TextArea(id="user-goal")
                            yield Button("START HYDRA FLEET", variant="success", id="start-btn")
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
                with TabPane("Bridge Control", id="bridge-tab"):
                    with Horizontal():
                        with Vertical(id="bridge-sessions"):
                            yield Label("Active Bridge Sessions", classes="panel-title")
                            yield Container(id="bridge-session-list")
                        with Vertical(id="bridge-controls"):
                            yield Label("Session Controls", classes="panel-title")
                            yield Label("Select a session to control", id="selected-session-label")
                            with Horizontal():
                                yield Button("CONTINUE", variant="success", id="cmd-continue")
                                yield Button("PAUSE", variant="warning", id="cmd-pause")
                                yield Button("STOP", variant="error", id="cmd-stop")
                            with Horizontal():
                                yield Button("REJECT", variant="error", id="cmd-reject")
                                yield Button("EDIT PLAN", id="cmd-edit")
                            yield Label("Ask Jules:")
                            yield Input(placeholder="Your question...", id="ask-input")
                            yield Button("SEND ASK", variant="primary", id="cmd-ask")
                            yield Log(id="bridge-log")
            with Vertical(id="global-logs"):
                yield Label("Global Logs (also in hydra.log)", classes="panel-title")
                yield Log(id="main-log")
                yield Button("Clear UI Logs", id="clear-logs-btn")
        yield Footer()

    async def on_mount(self):
        self.set_interval(2, self.update_ui)
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    config = json.load(f)
                    self.query_one("#api-key").value = config.get("gemini_api_key", "")
                    self.query_one("#gh-token").value = config.get("github_token", "")
                    self.query_one("#repo-name").value = config.get("repo_full_name", "")
                    self.query_one("#proxy-url").value = config.get("proxy_url", "")
            except: pass

        from hydra_bridge import HydraBridge
        self.bridge = HydraBridge(log_callback=self.log_to_bridge)
        asyncio.create_task(self.bridge.listen_for_sessions(self.on_bridge_event))

    def update_ui(self):
        if hasattr(self, "bridge"):
            session_container = self.query_one("#bridge-session-list")
            existing_widgets = {child.id: child for child in session_container.walk_children() if child.id}
            for sid, metadata in self.bridge.active_sessions.items():
                widget_id = f"bridge-sid-{sid[:8]}"
                if widget_id not in existing_widgets:
                    btn = Button(f"{sid[:8]} ({metadata.get('branch', 'unknown')})", id=widget_id)
                    btn.session_id = sid
                    session_container.mount(btn)

        if hasattr(self, "orchestrator") and self.orchestrator.scheduler:
            task_container = self.query_one("#task-list")
            status_map = self.orchestrator.scheduler.get_all_status()
            existing_tasks = {child.id: child for child in task_container.walk_children() if child.id}
            for task_id, status in status_map.items():
                widget_id = f"task-{task_id}"
                if widget_id in existing_tasks:
                    existing_tasks[widget_id].update(f"{task_id}: {status}")
                else:
                    task_container.mount(Label(f"{task_id}: {status}", id=widget_id))

    def log_to_ui(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        try: self.query_one("#main-log").write_line(formatted_msg)
        except: pass
        with open("hydra.log", "a") as f: f.write(formatted_msg + "\n")

    def log_to_bridge(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        try: self.query_one("#bridge-log").write_line(f"[{timestamp}] {message}")
        except: pass

    async def on_bridge_event(self, type, sid, data):
        if type == "NEW_SESSION":
            self.log_to_bridge(f"New session: {sid}")
            self.notify(f"New Bridge Session: {sid[:8]}")
        elif type == "EVENT":
            event_name = data.get("event")
            self.log_to_bridge(f"[{sid[:8]}] {event_name}: {json.dumps(data.get('payload'))}")

    def save_current_config(self):
        config = {
            "gemini_api_key": self.query_one("#api-key").value,
            "github_token": self.query_one("#gh-token").value,
            "repo_full_name": self.query_one("#repo-name").value,
            "proxy_url": self.query_one("#proxy-url").value,
            "repo_path": "."
        }
        with open("config.json", "w") as f: json.dump(config, f)
        self.log_to_ui("Configuration saved.")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "toggle-goal-btn":
            container = self.query_one("#goal-container")
            if container.has_class("collapsed"): container.remove_class("collapsed")
            else: container.add_class("collapsed")
        elif event.button.id == "start-btn":
            self.save_current_config()
            asyncio.create_task(self.handle_start())
        elif event.button.id and event.button.id.startswith("bridge-sid-"):
            self.selected_bridge_session = event.button.session_id
            self.query_one("#selected-session-label").update(f"Selected: {self.selected_bridge_session}")
        elif event.button.id and event.button.id.startswith("cmd-"):
            if not hasattr(self, "selected_bridge_session"):
                self.notify("No bridge session selected", severity="error")
                return
            cmd = event.button.id.replace("cmd-", "").upper()
            msg = self.query_one("#ask-input").value if cmd == "ASK" else None
            await self.bridge.send_command(self.selected_bridge_session, cmd, message=msg)
            self.log_to_bridge(f"Command {cmd} sent to {self.selected_bridge_session}")
            if cmd == "ASK": self.query_one("#ask-input").value = ""

    async def handle_start(self):
        try:
            config = {
                "gemini_api_key": self.query_one("#api-key").value or os.getenv("GEMINI_API_KEY"),
                "github_token": self.query_one("#gh-token").value or os.getenv("GITHUB_TOKEN"),
                "repo_full_name": self.query_one("#repo-name").value or os.getenv("REPO_NAME"),
                "proxy_url": self.query_one("#proxy-url").value or os.getenv("PROXY_URL"),
                "repo_path": "."
            }
            goal = self.query_one("#user-goal").text
            if not all([config["gemini_api_key"], config["github_token"], config["repo_full_name"], goal]):
                self.log_to_ui("Missing configuration or goal!")
                return
            with open("config.json", "w") as f: json.dump(config, f)
            self.query_one(TabbedContent).active = "monitor-tab"
            self.orchestrator = Orchestrator(config, self.log_to_ui)
            asyncio.create_task(self.orchestrator.run(goal))
        except Exception as e:
            self.log_to_ui(f"Failed to start: {e}")

if __name__ == "__main__":
    app = HydraApp()
    app.run()
