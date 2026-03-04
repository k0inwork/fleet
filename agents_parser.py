import yaml
import os
from typing import Dict, Any, List

class AgentsManifest:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self.capabilities: List[Dict[str, Any]] = []
        self.load_manifest()

    def load_manifest(self):
        """Loads and parses agents.md (assuming yaml content inside)"""
        agents_md_path = os.path.join(self.repo_path, "agents.md")
        if not os.path.exists(agents_md_path):
            return

        with open(agents_md_path, "r") as f:
            content = f.read()

        # Simple parsing for yaml blocks in markdown
        if "```yaml" in content:
            try:
                yaml_content = content.split("```yaml")[1].split("```")[0]
                data = yaml.safe_load(yaml_content)
                if "capabilities" in data:
                    self.capabilities = data["capabilities"]
            except Exception as e:
                print(f"Failed to parse agents.md: {e}")

    def get_fallback(self, task_instruction: str) -> str:
        """
        Determines if a task needs a fallback based on instruction matching.
        In a real system, this would use LLM or exact task ID matching.
        """
        for cap in self.capabilities:
            task_name = cap.get("task", "").lower()
            if task_name and task_name in task_instruction.lower():
                if not cap.get("supported", True):
                    return cap.get("fallback", "none")
        return "none"
