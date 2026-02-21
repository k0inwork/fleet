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
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"): # Defaulting to 1.5 flash for now as per genai support, but user mentioned 3.1
        # Note: If gemini-3.1-pro-preview is available, we should use it.
        # Based on my search, gemini-3.1-pro-preview might be the ID.
        genai.configure(api_key=api_key)
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
1. Tasks are granular enough to be completed in a single Jules session.
2. Dependencies are correctly mapped (e.g., a feature depends on its required base components).
3. Branch names are unique and descriptive.
4. Total tasks should not exceed 15 (daily limit), but keep it efficient.

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
