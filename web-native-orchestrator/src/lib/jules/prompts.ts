export const AGENTS_MD_BOOTSTRAP = `
# AGENTS.md - Web-Cloud Protocol

## 1. Toolchain Persistence
- Jules must ensure \`gh\` is available before any Git operations.

## 2. Execution & Offloading
- **VM-Local:** Small edits, \`npm test\`, documentation.
- **GH-Offload:** Integration tests or heavy builds.
  - *Procedure:* Jules commits code -> \`gh workflow run\` -> \`gh run watch\`.

## 3. The "PR Handover"
- **Requirement:** Every successful task MUST result in a Pull Request.
- **Reporting:** Jules must return the **URL of the PR** to the Browser Orchestrator.
- **HIL Logic:** The Orchestrator will display the PR link and a \`git diff\` summary to the User for a final merge click.

### Instructions for Current Task:
Before starting the task, please verify that \`gh\` is installed. Then proceed with the task below.
`;
