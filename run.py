import subprocess
print(subprocess.run(["python3", "/data/workspace/execute.py"], capture_output=True, text=True).stdout)
