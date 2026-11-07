import subprocess
print(subprocess.run(["bash", "/data/workspace/do_git.sh"], cwd="/data/workspace", capture_output=True, text=True).stdout)
