import subprocess
print(subprocess.run(["python3", "/data/workspace/run_status.py"], capture_output=True, text=True).stdout)
