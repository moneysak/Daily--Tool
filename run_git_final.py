import subprocess

script = """
cd /data/workspace
chmod +x run.sh
git checkout -B develop
git add run.sh run.sh.bak
git commit -m "Update run.sh for diagnostic mode"
git push -u origin develop
"""
result = subprocess.run(script, shell=True, executable='/bin/bash', capture_output=True, text=True)
print("OUT:", result.stdout)
print("ERR:", result.stderr)
