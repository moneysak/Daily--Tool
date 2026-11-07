import subprocess

print(subprocess.run(["python3", "/data/workspace/run3.py"], capture_output=True, text=True).stdout)
