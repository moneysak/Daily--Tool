import subprocess

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    print(f"Command: {cmd}")
    print(f"Return code: {res.returncode}")
    print(f"Stdout:\n{res.stdout}")
    print(f"Stderr:\n{res.stderr}")
    print("-" * 20)

run_cmd("git remote -v")
run_cmd("git branch -a")
run_cmd("git log -n 3")
