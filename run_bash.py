import subprocess

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    print(f"Command: {cmd}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
    print(f"Return code: {result.returncode}")
    print("-" * 20)

run_cmd("bash git_commit.sh")
