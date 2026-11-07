import subprocess

def run_cmd(cmd):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    if res.stdout:
        print("STDOUT:")
        print(res.stdout)
    if res.stderr:
        print("STDERR:")
        print(res.stderr)
    print(f"Return code: {res.returncode}")
    print("-" * 40)
    return res

run_cmd("git config user.email 'bot@example.com'")
run_cmd("git config user.name 'Bot'")
run_cmd("git status")
run_cmd("git add src/ docs/ *.py *.sh")
run_cmd("git status")
run_cmd("git commit -m 'Implement GET/POST/PUT tasks in frontend and backend'")
run_cmd("git push origin develop")
