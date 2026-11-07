import subprocess

with open('output.txt', 'w') as f:
    result = subprocess.run(['bash', 'git_commit.sh'], cwd='/data/workspace', capture_output=True, text=True)
    f.write(result.stdout)
    f.write(result.stderr)
