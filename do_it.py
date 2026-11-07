import subprocess

def run(cmd):
    with open('git_exec.txt', 'a') as f:
        f.write(f"Executing: {cmd}\n")
        res = subprocess.run(cmd, shell=True, cwd='/data/workspace', capture_output=True, text=True)
        f.write(f"STDOUT:\n{res.stdout}\n")
        f.write(f"STDERR:\n{res.stderr}\n")

open('git_exec.txt', 'w').close()
run('git checkout -B develop')
run('git add run.sh run.sh.bak')
run('git commit -m "Add diagnostic run.sh"')
run('git push origin develop')
