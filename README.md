# Jules Hydra Orchestrator

The Jules Hydra Orchestrator is a system designed to decompose high-level software engineering goals into a Directed Acyclic Graph (DAG) of tasks. Each task is then executed by an autonomous Jules AI agent in a separate ephemeral VM.

## Key Components

- **Brain (`brain.py`):** The strategic component that utilizes the Gemini API to analyze a user's goal and the codebase context, generating a structured DAG of tasks.
- **Hydra Controller (`hydra_controller.py`):** Manages the execution sessions using Playwright. It automates interaction with the Jules UI to create sessions, assign tasks, and monitor progress.
- **Scheduler (`scheduler.py`):** Handles the execution flow of the DAG, ensuring tasks are run in the correct order based on their dependencies.
- **Context Engine (`context_engine.py`):** Gathers information about the codebase (file tree, manifests, etc.) to provide context for the Brain when generating tasks.
- **Main Application (`main.py`):** A Textual-based terminal user interface (TUI) that brings all components together, allowing users to configure the system, input goals, and monitor the fleet of Jules agents.

## Workflow

1.  **Configuration:** Configure the system via the TUI with necessary API keys and repository details.
2.  **Goal Input:** Provide a high-level software engineering goal.
3.  **Task Generation:** The Brain analyzes the goal and codebase context to generate a DAG of tasks.
4.  **Execution:** The Scheduler coordinates with the Hydra Controller to launch Jules sessions for each task, respecting dependencies.
5.  **Monitoring:** Monitor the progress of tasks and sessions through the TUI.
