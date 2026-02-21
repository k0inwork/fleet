import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

class FileInfo(BaseModel):
    path: str
    size: int
    extension: str

class CodebaseContext(BaseModel):
    file_tree: List[str]
    manifests: Dict[str, str]
    summary: str

class ContextEngine:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()

    def get_context(self) -> CodebaseContext:
        file_tree = self._build_file_tree()
        manifests = self._read_manifests()
        summary = self._generate_summary(file_tree, manifests)
        return CodebaseContext(
            file_tree=file_tree,
            manifests=manifests,
            summary=summary
        )

    def _build_file_tree(self) -> List[str]:
        tree = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip .git and common build dirs
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", "dist", "build"}]
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), self.repo_path)
                tree.append(rel_path)
        return tree

    def _read_manifests(self) -> Dict[str, str]:
        manifest_files = ["package.json", "requirements.txt", "pom.xml", "go.mod", "Cargo.toml", "README.md"]
        manifests = {}
        for filename in manifest_files:
            file_path = self.repo_path / filename
            if file_path.exists():
                try:
                    with open(file_path, "r") as f:
                        manifests[filename] = f.read()[:5000] # Limit size
                except Exception as e:
                    manifests[filename] = f"Error reading file: {e}"
        return manifests

    def _generate_summary(self, file_tree: List[str], manifests: Dict[str, str]) -> str:
        # A simple summary for now. Gemini will use this to understand the project structure.
        summary = f"Codebase has {len(file_tree)} files.\n"
        if "README.md" in manifests:
            summary += f"README Snippet:\n{manifests['README.md'][:500]}\n"

        detected_tech = []
        if "package.json" in manifests: detected_tech.append("Node.js/NPM")
        if "requirements.txt" in manifests: detected_tech.append("Python")
        if "go.mod" in manifests: detected_tech.append("Go")

        if detected_tech:
            summary += f"Detected Technologies: {', '.join(detected_tech)}\n"

        return summary

if __name__ == "__main__":
    engine = ContextEngine()
    context = engine.get_context()
    print(context.summary)
    print(f"Files indexed: {len(context.file_tree)}")
