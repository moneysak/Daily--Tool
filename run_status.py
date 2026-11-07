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

print(json.dumps(run_cmd("git status"), indent=2))
