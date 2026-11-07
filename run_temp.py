import subprocess
import os

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    return result

print(run_cmd("chmod +x run.sh").stdout)
print(run_cmd("git branch -a").stdout)
print(run_cmd("git status").stdout)
