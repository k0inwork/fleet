import sys

with open('main.py', 'r') as f:
    lines = f.readlines()

# Find the end of on_mount (where it was originally before the messy edit)
# It was around line 282
# We want to insert the bridge initialization into the FIRST on_mount

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if "self.query_one(\"#session-state\").text = config[\"session_state\"]" in line:
        # This is inside the try block of config loading.
        pass
    if i == 283: # Just after the config loading try/except in on_mount
        new_lines.append("\n        # Start Bridge\n")
        new_lines.append("        from hydra_bridge import HydraBridge\n")
        new_lines.append("        self.bridge = HydraBridge(log_callback=self.log_to_bridge)\n")
        new_lines.append("        asyncio.create_task(self.bridge.listen_for_sessions(self.on_bridge_event))\n")

with open('main.py', 'w') as f:
    f.writelines(new_lines)
