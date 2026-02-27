import json
import os
from typing import List, Optional
from pydantic import BaseModel, Field
import google.generativeai as genai
from context_engine import CodebaseContext

class Task(BaseModel):
    id: str
    branch: str
    instruction: str
    dependencies: List[str] = Field(default_factory=list)

class TaskGraph(BaseModel):
    tasks: List[Task]

class Brain:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview"):
        # Use REST transport to better respect environment proxies and avoid gRPC SOCKS5 issues
        genai.configure(api_key=api_key, transport='rest')
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)

    def generate_task_graph(self, user_goal: str, context: CodebaseContext) -> TaskGraph:
        prompt = f"""
You are the Strategic Brain of the Jules Hydra Orchestrator.
Your goal is to decompose a high-level software engineering goal into a Directed Acyclic Graph (DAG) of tasks.
Each task will be executed by an autonomous Jules AI agent in a separate ephemeral VM.

User Goal: {user_goal}

Codebase Context Summary:
{context.summary}

File Tree:
{json.dumps(context.file_tree, indent=2)}

Manifests:
{json.dumps(context.manifests, indent=2)}

Output a JSON object that strictly follows this schema:
{{
  "tasks": [
    {{
      "id": "task_id",
      "branch": "branch_name",
      "instruction": "Detailed technical instruction for Jules. include context about the files to modify.",
      "dependencies": ["list_of_dependency_ids"]
    }}
  ]
}}

Ensure that:
1. **Parallelism is Priority**: Maximize parallel execution by identifying independent tracks of work (e.g., Backend implementation, Frontend UI development, and Documentation/Test suites can often run concurrently). Aim for up to 3 parallel tasks at any given time.
2. **Merge Sequential Overhead**: If tasks are strictly sequential and depend on each other, merge them into a single, comprehensive task. Do not split sequential work unless there is a clear benefit to doing so (e.g., hitting a very large context limit).
3. **Substantial Tasks**: Each task should be high-impact. Avoid trivial nodes like "setup environment". Combine setup with the first meaningful implementation phase.
4. **Agent Autonomy**: Jules agents are expert engineers; they can handle complex, multi-step workflows in a single session. Trust their ability to execute broad instructions.
5. **Dependencies**: Map dependencies strictly. A task should only depend on others if it physically cannot start without their completed code (e.g., Frontend depends on API contract/models).
6. **Graph Size**: Aim for a lean, efficient DAG of 3-6 substantial tasks.
7. **Test-First Architecture**:
   - **Mandatory Quality Architect Task**: Always include a primary task (e.g., `test_planning`) that creates a comprehensive `TEST_PLAN.md`. This document must define detailed GUI checks (Playwright), Backend API validations, and End-to-End integration scenarios.
   - **Implementation Dependencies**: All implementation tasks must depend on the `test_planning` task.
   - **Test Execution**: Instructions for implementation tasks must explicitly require writing and passing the relevant tests defined in `TEST_PLAN.md` before completion.

Response must be ONLY the JSON object.
"""
        response = self.model.generate_content(prompt)
        # Attempt to parse JSON from response
        try:
            # Clean up response if it has markdown blocks
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())
            return TaskGraph(**data)
        except Exception as e:
            raise ValueError(f"Failed to parse Task Graph from Gemini response: {e}\nResponse: {response.text}")

if __name__ == "__main__":
    # Test with dummy key and data (will fail but good for structure check)
    pass
