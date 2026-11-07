import subprocess
result = subprocess.run(["python3", "run_git_direct.py"], cwd="/data/workspace", capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
