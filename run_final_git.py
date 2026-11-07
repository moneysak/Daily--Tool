import subprocess
import sys

def run_command(command, cwd=None):
    print(f"Executing: {' '.join(command) if isinstance(command, list) else command}")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=isinstance(command, str),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"Output:\n{result.stdout}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error (Exit code {e.returncode}):\n{e.stderr}")
        return False, e.stderr

workspace_dir = "/data/workspace"

# 1. Backup 'run.sh' to 'run.sh.bak'
run_command("cp run.sh run.sh.bak", cwd=workspace_dir)

# 2 & 3: run.sh is already written and has executable permission
run_command("chmod +x run.sh", cwd=workspace_dir)

# 4. Commit the changes to the 'develop' branch and push
# Fetch and checkout develop
run_command("git fetch", cwd=workspace_dir)

# Try checkout, if fails create it
success, _ = run_command("git checkout develop", cwd=workspace_dir)
if not success:
     run_command("git checkout -b develop", cwd=workspace_dir)

# Add files
run_command("git add run.sh run.sh.bak", cwd=workspace_dir)

# Commit
run_command(['git', 'commit', '-m', 'Add diagnostic run.sh'], cwd=workspace_dir)

# Push
run_command("git push -u origin develop", cwd=workspace_dir)
