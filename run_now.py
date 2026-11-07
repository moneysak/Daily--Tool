import subprocess
subprocess.run("python3 /data/workspace/generate_runner.py", shell=True)
res = subprocess.run("python3 /data/workspace/run_all_the_things.py", shell=True, capture_output=True, text=True)
print(res.stdout)
