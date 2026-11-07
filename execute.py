import subprocess
print(subprocess.run("python3 /data/workspace/run_script.py", shell=True, capture_output=True, text=True).stdout)
