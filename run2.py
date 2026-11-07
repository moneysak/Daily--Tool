import subprocess
import json

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    return {
        "cmd": cmd,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip(),
        "returncode": res.returncode
    }

results = []
results.append(run_cmd("git status"))
results.append(run_cmd("git add ."))
results.append(run_cmd("git commit -m 'Implement GET/POST/PUT tasks in frontend and backend'"))
results.append(run_cmd("git push origin develop"))

with open("/data/workspace/results.json", "w") as f:
    json.dump(results, f, indent=2)
