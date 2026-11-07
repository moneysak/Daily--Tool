import subprocess
res = subprocess.run(["python3", "/data/workspace/run_all.py"], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
