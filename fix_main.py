import sys

with open('main.py', 'r') as f:
    lines = f.readlines()

# Remove the duplicated on_mount and its body at the end
# The second on_mount starts at line 513
final_lines = lines[:512]

with open('main.py', 'w') as f:
    f.writelines(final_lines)
