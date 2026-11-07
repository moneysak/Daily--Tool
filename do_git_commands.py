#!/usr/bin/env python3
import subprocess

with open("/data/workspace/git_output2.txt", "w") as f:
    commands = [
        "chmod +x /data/workspace/run.sh",
        "git fetch origin",
        "git checkout develop",
        "git status",
        "git add run.sh run.sh.bak",
        'git commit -m "Update run.sh for diagnostic mode"',
        "git push origin develop"
    ]
    for cmd in commands:
        result = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
        f.write(f"Executing: {cmd}\n")
        f.write(result.stdout)
        f.write(result.stderr)
