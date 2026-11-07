import subprocess
with open('git_out.txt', 'w') as f:
    res = subprocess.run(['bash', 'run_git.sh'], cwd='/data/workspace', capture_output=True, text=True)
    f.write(res.stdout)
    f.write("\n---\n")
    f.write(res.stderr)
