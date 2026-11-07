#!/usr/bin/env python3
import os
import subprocess

def exec_cmd(cmd):
    print(f"Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd='/data/workspace', capture_output=True, text=True)
    if res.stdout:
        print("STDOUT:", res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)
    return res

exec_cmd("git config --global user.email 'ai@example.com'")
exec_cmd("git config --global user.name 'AI Agent'")
exec_cmd("git checkout -B develop")
exec_cmd("git add run.sh run.sh.bak")
exec_cmd("git commit -m 'Update run.sh for diagnostic script'")
exec_cmd("git push -u origin develop")
