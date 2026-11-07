import subprocess
import os

with open("/data/workspace/run.sh", "w") as f:
    f.write("#!/bin/bash\n")
    f.write("cd /data/workspace\n")
    f.write("git config --global user.email 'bot@example.com'\n")
    f.write("git config --global user.name 'Bot'\n")
    f.write("git init -b main\n")
    f.write("git commit --allow-empty -m 'Initial empty commit'\n")
    f.write("git checkout -b develop\n")
    f.write("git add addon/ docs/\n")
    f.write("git commit -m 'Add addon and docs'\n")
    f.write("chmod +x setup_repo.sh deploy.sh\n")

os.chmod("/data/workspace/run.sh", 0o755)
result = subprocess.run("/data/workspace/run.sh", shell=True, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr)
