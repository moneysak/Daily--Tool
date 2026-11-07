import subprocess
import os

print("--- Start python execution ---")

def run(cmd):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="/data/workspace")
    print(f"Return code: {res.returncode}")
    print(f"Stdout: {res.stdout.strip()}")
    print(f"Stderr: {res.stderr.strip()}")
    print("-" * 20)
    
run("chmod +x run.sh")
run("git branch -a")
run("git checkout develop || git checkout -b develop")
run("git status")
run("git add run.sh run.sh.bak")
run('git commit -m "Update run.sh for diagnostic mode"')
run("git push -u origin develop")

print("--- End python execution ---")
