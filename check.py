import subprocess
res = subprocess.run("git status", shell=True, cwd="/data/workspace", capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
