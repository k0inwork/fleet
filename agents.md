# Agents Capabilities
This file defines the capabilities of Jules VMs.

```yaml
capabilities:
  - task: "Build Android APK"
    supported: false  # VM cannot handle this task
    fallback: "github_actions"  # GitHub Actions is used for this task
  - task: "Run unit tests"
    supported: true  # VM can handle unit tests natively
    fallback: "none"  # No external fallback is needed
```
