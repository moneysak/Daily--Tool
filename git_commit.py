import subprocess
import os

def run_cmd(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(f"Output: {result.stdout}")

run_cmd("chmod +x run.sh")
run_cmd("git checkout -b develop || git checkout develop")
run_cmd("git add run.sh run.sh.bak")
run_cmd('git commit -m "Add diagnostic run.sh"')
run_cmd("git push origin develop")
