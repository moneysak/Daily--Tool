import subprocess

res = subprocess.run("git push -u origin develop", shell=True, cwd="/data/workspace", capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
