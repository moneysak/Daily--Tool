#!/usr/bin/env python3
import subprocess

def run_git():
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
        print(f"Executing: {cmd}")
        print(result.stdout)
        if result.returncode != 0:
            print(f"Error executing {cmd}:")
            print(result.stderr)
            
run_git()
