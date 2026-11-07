import subprocess
import os

print(subprocess.run(['python3', 'run_git_final.py'], cwd='/data/workspace', capture_output=True, text=True).stdout)
