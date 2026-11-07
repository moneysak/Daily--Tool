#!/usr/bin/env python3
import subprocess

with open("/data/workspace/git_output.txt", "w") as f:
    commands = [
        "chmod +x /data/workspace/run.sh",
        "git fetch",
        "git checkout -B develop origin/develop || git checkout -b develop",
        "git add run.sh run.sh.bak",
        'git commit -m "Update run.sh with diagnostic script"',
        "git push -u origin develop"
    ]
    for cmd in commands:
        result = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
        f.write(f"Executing: {cmd}\n")
        f.write(result.stdout)
        if result.returncode != 0:
            f.write(f"Error executing {cmd}:\n")
            f.write(result.stderr)
            
