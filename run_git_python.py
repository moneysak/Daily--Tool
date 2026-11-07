import subprocess

print("Executing python script to write out bash script and run it")

bash_script = """#!/bin/bash
cd /data/workspace
echo "=== Git Status Before ==="
git status
echo "=== Branch ==="
git branch -a
echo "=== Checkout ==="
git checkout -B develop origin/develop || git checkout -b develop
echo "=== Add ==="
git add run.sh run.sh.bak
echo "=== Commit ==="
git commit -m "Update run.sh for diagnostic mode"
echo "=== Push ==="
git push origin develop
echo "=== Git Status After ==="
git status
"""

with open("/data/workspace/run_git_bash.sh", "w") as f:
    f.write(bash_script)

res = subprocess.run("bash /data/workspace/run_git_bash.sh", shell=True, capture_output=True, text=True, cwd="/data/workspace")
print(res.stdout)
print(res.stderr)
