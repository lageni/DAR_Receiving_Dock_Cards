# ACL Feature Installer
import sys

print("Installing ACL Freight Awareness...")

# Step 1: Read main.py
with open("main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Read {len(lines)} lines from main.py")

# Step 2: Find insertion point
insert_idx = None
for i, line in enumerate(lines):
    if "@app.get("/delivery-analysis"," in line:
        insert_idx = i
        break

if insert_idx is None:
    print("ERROR: Could not find delivery-analysis endpoint")
    sys.exit(1)

print(f"Found insertion point at line {insert_idx}")

# Step 3: Check if already installed
if any("/acl-freight-awareness" in line for line in lines):
    print("ACL endpoints already installed!")
    sys.exit(0)

print("Installing...")
sys.exit(0)
