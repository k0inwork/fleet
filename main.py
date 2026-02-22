import asyncio
import os
import json
import traceback
import socket

import logging

# Configure logging to file to avoid messing up TUI
logging.basicConfig(
    level=logging.INFO,
    filename='hydra.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Try to setup proxy as early as possible before any other imports
if os.path.exists("config.json"):
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
            p_url = cfg.get("proxy_url")
            if p_url and "socks5" in p_url:
                import socks
                host_port = p_url.split("://")[-1].split("@")[-1]
                host = host_port.split(":")[0]
                port = int(host_port.split(":")[1])
                socks.set_default_proxy(socks.SOCKS5, host, port)
                socket.socket = socks.socksocket
                os.environ['http_proxy'] = p_url
                os.environ['https_proxy'] = p_url
                os.environ['all_proxy'] = p_url
                os.environ['grpc_proxy'] = p_url
    except:
        pass

from datetime import datetime
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Log, Label, Input, Button, TabbedContent, TabPane, TextArea, Tree
from textual.reactive import reactive

from context_engine import ContextEngine
from scheduler import DAGScheduler, TaskStatus
from utils import setup_global_proxy, check_proxy

class Orchestrator:
    def __init__(self, config: dict, log_callback):
        from brain import Brain
        from hydra_controller import HydraController
        from github_verifier import GitHubVerifier

        self.config = config
        self.log = log_callback
        self.context_engine = ContextEngine(config.get("repo_path", "."))
        self.brain = Brain(config["gemini_api_key"])

        # If manual session state is provided, write it to state.json
        if config.get("session_state"):
            try:
                state_data = json.loads(config["session_state"])
                with open("state.json", "w") as f:
                    json.dump(state_data, f)
                self.log("Manual session state JSON loaded into state.json")
            except Exception as e:
                self.log(f"Failed to parse manual session state JSON: {e}")

        self.hydra = HydraController(config.get("proxy_url"))
        self.verifier = GitHubVerifier(config["github_token"], config["repo_full_name"], config.get("proxy_url"))
        self.scheduler = None
        self.is_running = False

    async def run(self, user_goal: str):
        try:
            # 1. Check & Setup Proxy - must be FIRST
            if self.config.get("proxy_url"):
                setup_global_proxy(self.config["proxy_url"])
                if not check_proxy(self.config["proxy_url"]):
                    self.log("Proxy check failed! Aborting.")
                    return

            self.log(f"Starting orchestration for goal: {user_goal}")

            # 2. Context Indexing
            context = await asyncio.to_thread(self.context_engine.get_context)
            self.log(f"Context indexed: {len(context.file_tree)} files.")

            # 3. Task Graph Generation
            self.log("Generating Task Graph via Gemini...")
            try:
                task_graph = await asyncio.to_thread(self.brain.generate_task_graph, user_goal, context)
                self.scheduler = DAGScheduler(task_graph)
                self.log(f"Task Graph generated with {len(task_graph.tasks)} tasks.")
            except Exception as e:
                self.log(f"Error generating Task Graph: {e}")
                return

            # 4. Hydra Start
            await self.hydra.start()

            # 5. Execution Loop
            self.is_running = True
            while not self.scheduler.is_finished() and self.is_running:
                # Dispatch tasks
                ready_tasks = self.scheduler.get_ready_tasks()
                for task_id in ready_tasks:
                    if len(self.hydra.sessions) < 3: # Concurrency limit
                        await self.dispatch_task(task_id)

                # Verify PRs
                await self.verify_active_tasks()

                await asyncio.sleep(10) # Poll interval
        except Exception as e:
            self.log(f"FATAL ERROR in orchestrator: {e}")
        finally:
            await self.hydra.stop()
            self.is_running = False
            self.log("Orchestration finished.")

    async def dispatch_task(self, task_id: str):
        task_node = self.scheduler.nodes[task_id]
        self.log(f"Dispatching task {task_id} to Hydra...")

        try:
            # Create or Reuse Session
            session_id = await self.hydra.create_session(self.config["repo_full_name"], task_node.task.branch)
            if session_id:
                self.scheduler.mark_running(task_id, session_id)
                await self.hydra.send_message(session_id, task_node.task.instruction)
                self.log(f"Task {task_id} is now running in session {session_id}")
            else:
                self.log(f"Failed to create session for task {task_id}: Unknown error")
        except Exception as e:
            self.log(f"Failed to create session for task {task_id}: {e}")

    async def verify_active_tasks(self):
        for task_id, node in self.scheduler.nodes.items():
            if node.status == TaskStatus.RUNNING:
                submitted, conflicted = await asyncio.to_thread(self.verifier.verify_pr, node.task.branch)
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
    #left-panel { width: 40%; border: solid green; }
    #center-panel { width: 60%; border: solid blue; }
    #screen-split { height: 1fr; }
    #app-content { width: 65%; }
    #global-logs { width: 35%; border: solid white; }
    .panel-title { text-align: center; background: $accent; color: white; margin: 1; }
    #main-log { height: 1fr; }
    #config-form { padding: 1; border: double red; height: auto; }
    #config-form Horizontal {
        height: 3;
        margin-bottom: 1;
    }
    #config-form Input {
        width: 1fr;
    }
    #config-form Button {
        width: 15;
        min-width: 15;
    }
    #goal-container {
        border: solid yellow;
        height: 15;
        padding: 0 1;
        transition: height 200ms;
    }
    #goal-container.collapsed {
        height: 4;
    }
    #goal-container.expanded {
        height: 25;
    }
    #dag-tree {
        display: none;
        height: 1fr;
        border: blue;
        margin: 1 0;
    }
    .show-tree #dag-tree {
        display: block;
    }
    .show-tree #user-goal {
        display: none;
    }
    #goal-header {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="screen-split"):
            with Vertical(id="app-content"):
                with TabbedContent():
                    with TabPane("Config", id="config-tab"):
                        with Vertical(id="config-form"):
                            yield Label("Configuration")
                            with Horizontal():
                                yield Input(placeholder="Gemini API Key", id="api-key", password=True)
                                yield Button("Test Key", variant="primary", id="test-api-btn")
                            with Horizontal():
                                yield Input(placeholder="GitHub Token", id="gh-token", password=True)
                                yield Button("Test Token", variant="primary", id="test-gh-btn")
                            with Horizontal():
                                yield Input(placeholder="Repo (owner/repo)", id="repo-name")
                                yield Button("Test Repo", variant="primary", id="test-repo-btn")
                            with Horizontal():
                                yield Input(placeholder="Proxy URL (socks5://...)", id="proxy-url")
                                yield Button("Test Proxy", variant="primary", id="test-proxy-btn")

                            yield Label("Playwright Session State (JSON)")
                            yield Label("This stores your login cookies. It is filled automatically after 'Login to Google'.", variant="dim")
                            yield TextArea(id="session-state", classes="collapsed")

                            with Horizontal():
                                yield Button("Login to Google", id="login-btn")
                    with TabPane("Monitor", id="monitor-tab"):
                        with Vertical(id="goal-header"):
                            with Vertical(id="goal-container", classes="collapsed"):
                                with Horizontal():
                                    yield Label("SYSTEM GOAL / DAG")
                                    yield Button("Toggle Size", id="toggle-goal-btn")
                                yield TextArea(id="user-goal")
                                yield Tree("Task Graph", id="dag-tree")
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
            with Vertical(id="global-logs"):
                yield Label("Global Logs (also in hydra.log)", classes="panel-title")
                yield Log(id="main-log")
                yield Button("Clear UI Logs", id="clear-logs-btn")
        yield Footer()

    async def on_mount(self):
        self.set_interval(2, self.update_ui)
        # Load saved config
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    config = json.load(f)
                    self.query_one("#api-key").value = config.get("gemini_api_key", "")
                    self.query_one("#gh-token").value = config.get("github_token", "")
                    self.query_one("#repo-name").value = config.get("repo_full_name", "")
                    self.query_one("#proxy-url").value = config.get("proxy_url", "")
                    if "session_state" in config:
                        self.query_one("#session-state").text = config["session_state"]
            except:
                pass

    def update_ui(self):
        if hasattr(self, "orchestrator"):
            # Update Overall Status
            status_text = "Running" if self.orchestrator.is_running else "Idle / Finished"

            if self.orchestrator.scheduler:
                # Update Task List (Left Panel)
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

                # Update DAG Tree
                self.update_dag_tree(status_map)

            # Update Fleet Status
            for i, (sid, session) in enumerate(self.orchestrator.hydra.sessions.items(), 1):
                if i <= 3:
                    self.query_one(f"#slot-{i}").update(f"Slot {i}: {sid} ({session.branch})")

    def update_dag_tree(self, status_map: Dict[str, str]):
        tree = self.query_one("#dag-tree")

        # If tree is empty but we have tasks, initialize it
        try:
            root = tree.root
            if not root.children and self.orchestrator.scheduler.nodes:
                self.build_initial_tree(tree)
        except:
            if self.orchestrator.scheduler.nodes:
                self.build_initial_tree(tree)

        # Update node labels with current status
        def update_node(node):
            task_id = node.data
            if task_id in status_map:
                status = status_map[task_id]
                # Add emoji for status
                emoji = "⏳"
                if status == "ready": emoji = "✅"
                if status == "running": emoji = "🚀"
                if status == "completed": emoji = "🏁"
                if status == "failed": emoji = "❌"
                if status == "conflicted": emoji = "⚠️"

                node.label = f"{task_id} [{emoji} {status}]"

            for child in node.children:
                update_node(child)

        try:
            for child in tree.root.children:
                update_node(child)
        except:
            pass

    def build_initial_tree(self, tree: Tree):
        # Reset the tree to a new root
        tree.reset("Task Graph")

        nodes = self.orchestrator.scheduler.nodes
        # Find roots (tasks that no one else depends on, OR tasks with no dependencies)
        # Actually, in a tree view of a DAG, we can show roots as tasks with NO dependencies.
        # Then children are tasks that depend on them.

        task_to_node = {}

        # First, find all tasks with no dependencies
        roots = [t_id for t_id, node in nodes.items() if not node.task.dependencies]

        added_tasks = set()

        def add_task_recursive(task_id, parent_node):
            if task_id in added_tasks: return # Avoid infinite recursion just in case
            added_tasks.add(task_id)

            status = nodes[task_id].status
            node = parent_node.add(f"{task_id} [{status}]", data=task_id)
            node.expand()

            # Find tasks that depend ON this task
            dependents = [t_id for t_id, n in nodes.items() if task_id in n.task.dependencies]
            for dep_id in dependents:
                add_task_recursive(dep_id, node)

        for root_id in roots:
            add_task_recursive(root_id, tree.root)

        tree.root.expand()

    def log_to_ui(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        try:
            self.query_one("#main-log").write_line(formatted_msg)
        except:
            pass # App might not be fully mounted

        # Also log to file
        with open("hydra.log", "a") as f:
            f.write(formatted_msg + "\n")

    def save_current_config(self):
        config = {
            "gemini_api_key": self.query_one("#api-key").value,
            "github_token": self.query_one("#gh-token").value,
            "repo_full_name": self.query_one("#repo-name").value,
            "proxy_url": self.query_one("#proxy-url").value,
            "session_state": self.query_one("#session-state").text,
            "repo_path": "."
        }
        with open("config.json", "w") as f:
            json.dump(config, f)
        self.log_to_ui("Configuration saved to config.json")

    async def on_button_pressed(self, event: Button.Pressed):
        proxy_url = self.query_one("#proxy-url").value or os.getenv("PROXY_URL")
        if proxy_url:
            # Ensure SOCKS5 prefix for Playwright if missing
            if "://" not in proxy_url:
                proxy_url = f"socks5://{proxy_url}"
            setup_global_proxy(proxy_url)

        if event.button.id == "toggle-goal-btn":
            container = self.query_one("#goal-container")
            if container.has_class("collapsed"):
                container.remove_class("collapsed")
                container.add_class("expanded")
            elif container.has_class("expanded"):
                container.remove_class("expanded")
                container.add_class("collapsed")
            else:
                # Default toggle if neither class is present
                container.add_class("collapsed")

        elif event.button.id == "test-api-btn":
            self.save_current_config()
            key = self.query_one("#api-key").value
            if not key:
                self.notify("API Key is missing", severity="error")
                return
            self.log_to_ui(f"Testing Gemini API Key with model: gemini-3-flash-preview...")

            def test_api():
                import google.generativeai as genai
                genai.configure(api_key=key, transport='rest')
                model = genai.GenerativeModel("gemini-3-flash-preview")
                return model.generate_content("test")

            try:
                await asyncio.to_thread(test_api)
                self.notify("API Key is valid!")
                self.log_to_ui("Gemini API Key validation successful.")
            except Exception as e:
                self.notify(f"API Key invalid: {e}", severity="error")
                self.log_to_ui(f"Gemini API Key validation failed: {e}")
                self.log_to_ui(traceback.format_exc())

        elif event.button.id == "test-gh-btn":
            self.save_current_config()
            token = self.query_one("#gh-token").value
            if not token:
                self.notify("GitHub Token is missing", severity="error")
                return
            self.log_to_ui("Testing GitHub Token...")

            def test_gh():
                from github import Github
                g = Github(token)
                return g.get_user().login

            try:
                login = await asyncio.to_thread(test_gh)
                self.notify(f"GitHub Token is valid! (User: {login})")
                self.log_to_ui(f"GitHub Token validation successful. Logged in as: {login}")
            except Exception as e:
                self.notify(f"GitHub Token invalid: {e}", severity="error")
                self.log_to_ui(f"GitHub Token validation failed: {e}")
                self.log_to_ui(traceback.format_exc())

        elif event.button.id == "test-repo-btn":
            self.save_current_config()
            repo_name = self.query_one("#repo-name").value
            token = self.query_one("#gh-token").value
            if not repo_name or not token:
                self.notify("Repo name or GitHub token missing", severity="error")
                return
            self.log_to_ui(f"Testing access to repository: {repo_name}...")

            def test_repo():
                from github import Github
                g = Github(token)
                repo = g.get_repo(repo_name)
                return repo.full_name, repo.id, repo.private

            try:
                full_name, rid, is_private = await asyncio.to_thread(test_repo)
                self.notify(f"Successfully accessed repo: {repo_name}")
                self.log_to_ui(f"Repository access confirmed: {repo_name} (ID: {rid})")
                self.log_to_ui(f"Repo full name: {full_name}, Visibility: {'Private' if is_private else 'Public'}")
            except Exception as e:
                self.notify(f"Could not access repo: {e}", severity="error")
                self.log_to_ui(f"Repository access failed for {repo_name}: {e}")
                self.log_to_ui(traceback.format_exc())

        elif event.button.id == "clear-logs-btn":
            self.query_one("#main-log").clear()

        elif event.button.id == "test-proxy-btn":
            self.save_current_config()
            proxy_url = self.query_one("#proxy-url").value
            if not proxy_url:
                self.notify("Proxy URL is missing", severity="warning")
                return
            self.log_to_ui(f"Testing SOCKS5 proxy connection: {proxy_url}...")

            if await asyncio.to_thread(check_proxy, proxy_url):
                self.notify("Proxy connection successful!")
                self.log_to_ui("SOCKS5 proxy validation successful.")
            else:
                self.notify("Proxy connection failed!", severity="error")
                self.log_to_ui("SOCKS5 proxy validation failed. Check if the proxy server is running and the URL is correct.")

        elif event.button.id == "login-btn":
            self.save_current_config()
            asyncio.create_task(self.perform_login())

        elif event.button.id == "start-btn":
            self.save_current_config()
            asyncio.create_task(self.handle_start())

    async def perform_login(self):
        from hydra_controller import HydraController
        proxy_url = self.query_one("#proxy-url").value or os.getenv("PROXY_URL")
        if proxy_url and "://" not in proxy_url:
            proxy_url = f"socks5://{proxy_url}"

        self.log_to_ui("Initializing browser for manual Google Login...")
        self.temp_hydra = HydraController(proxy_url)
        try:
            await self.temp_hydra.start(headless=False)
            self.push_screen(LoginScreen())
            await self.temp_hydra.login()
            self.log_to_ui("Google Login detected successfully! Session state updated.")
            self.notify("Google Login Successful!")
            # Automatically update the session state TextArea with the new content
            if os.path.exists("state.json"):
                with open("state.json", "r") as f:
                    self.query_one("#session-state").text = f.read()
                self.save_current_config()
        except Exception as e:
            self.log_to_ui(f"Login failed or interrupted: {e}")
            self.notify("Login Failed", severity="error")
            if hasattr(self, "temp_hydra"):
                await self.temp_hydra.stop()

    async def handle_start(self):
        try:
            # Show the tree and expand the container
            container = self.query_one("#goal-container")
            container.add_class("show-tree")
            container.remove_class("collapsed")
            container.add_class("expanded")

            # Reset the tree
            tree = self.query_one("#dag-tree")
            tree.reset("Task Graph")

            config = {
                "gemini_api_key": self.query_one("#api-key").value or os.getenv("GEMINI_API_KEY"),
                "github_token": self.query_one("#gh-token").value or os.getenv("GITHUB_TOKEN"),
                "repo_full_name": self.query_one("#repo-name").value or os.getenv("REPO_NAME"),
                "proxy_url": self.query_one("#proxy-url").value or os.getenv("PROXY_URL"),
                "session_state": self.query_one("#session-state").text,
                "repo_path": "."
            }
            goal = self.query_one("#user-goal").text

            if not all([config["gemini_api_key"], config["github_token"], config["repo_full_name"], goal]):
                self.log_to_ui("Missing required configuration or goal!")
                return

            # Save config for next run
            with open("config.json", "w") as f:
                json.dump(config, f)

            self.query_one(TabbedContent).active = "monitor-tab"
            self.orchestrator = Orchestrator(config, self.log_to_ui)
            asyncio.create_task(self.orchestrator.run(goal))
        except Exception as e:
            self.log_to_ui(f"Failed to handle start: {e}")
            self.log_to_ui(traceback.format_exc())

if __name__ == "__main__":
    app = HydraApp()
    app.run()
