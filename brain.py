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
1. Tasks should be substantial and high-impact. Avoid trivial or purely administrative tasks (like "setup environment" or "create gitignore") as standalone nodes. Instead, combine them with meaningful implementation (e.g., "Initialize project, configure environment, and implement core data models").
2. Jules agents are highly capable; they can handle complex, multi-step engineering workflows. Design tasks that leverage this autonomy.
3. Dependencies must be correctly mapped (e.g., a frontend feature depends on its required API endpoints).
4. Branch names are unique and descriptive.
5. Aim for a concise graph of 3-7 tasks for a typical project. Total tasks must not exceed 15.

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
