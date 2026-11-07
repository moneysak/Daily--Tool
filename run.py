import subprocess
import json

commands = [
    "git config --global user.email 'bot@example.com'",
    "git config --global user.name 'Bot'",
    "git init -b main",
    "git commit --allow-empty -m 'Initial empty commit'",
    "git checkout -b develop",
    "git add addon/ docs/",
    "git commit -m 'Add addon and docs'",
    "chmod +x setup_repo.sh deploy.sh"
]

results = []
for cmd in commands:
    res = subprocess.run(cmd, shell=True, cwd="/data/workspace", capture_output=True, text=True)
    results.append({
        "cmd": cmd,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip(),
        "returncode": res.returncode
    })

print(json.dumps(results, indent=2))
