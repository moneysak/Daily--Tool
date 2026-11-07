import subprocess

with open('execute_git_final.sh', 'w') as f:
    f.write('''#!/bin/bash
cd /data/workspace
git branch -a
git checkout develop || git checkout -b develop
git add run.sh run.sh.bak
git commit -m "add diagnostic run.sh"
git push origin develop
''')

subprocess.run(['chmod', '+x', 'execute_git_final.sh'])
res = subprocess.run(['./execute_git_final.sh'], capture_output=True, text=True, cwd='/data/workspace')
print(res.stdout)
print(res.stderr)
