import os

# Write a python script to run bash commands in order.
with open("/data/workspace/run_all_the_things.py", "w") as f:
    f.write('''import subprocess
import sys

def run(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="/data/workspace")
    print(f"[{cmd}] stdout:\\n{res.stdout}")
    if res.stderr:
        print(f"[{cmd}] stderr:\\n{res.stderr}")

run("git config --global user.email 'bot@example.com'")
run("git config --global user.name 'Bot'")
run("git init -b main")
run("git commit --allow-empty -m 'Initial empty commit'")
run("git checkout -b develop")
run("git add addon/ docs/")
run("git commit -m 'Add addon and docs'")
run("chmod +x setup_repo.sh deploy.sh")
''')
