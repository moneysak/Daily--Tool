import subprocess

def run_git():
    # Execute commands and log output to file
    with open('/data/workspace/git_log.txt', 'w') as log_file:
        commands = [
            ['chmod', '+x', 'run.sh'],
            ['git', 'branch', '-a'],
            ['git', 'checkout', 'develop'],
            ['git', 'add', 'run.sh', 'run.sh.bak'],
            ['git', 'commit', '-m', 'Update run.sh for diagnostic mode'],
            ['git', 'push', 'origin', 'develop']
        ]
        
        for cmd in commands:
            log_file.write(f"Running: {' '.join(cmd)}\n")
            result = subprocess.run(cmd, cwd='/data/workspace', capture_output=True, text=True)
            log_file.write(f"STDOUT:\n{result.stdout}\n")
            log_file.write(f"STDERR:\n{result.stderr}\n")
            log_file.write("-" * 40 + "\n")
            
            # If checkout develop fails, try creating it
            if cmd == ['git', 'checkout', 'develop'] and result.returncode != 0:
                log_file.write("Trying to create develop branch...\n")
                result2 = subprocess.run(['git', 'checkout', '-b', 'develop'], cwd='/data/workspace', capture_output=True, text=True)
                log_file.write(f"STDOUT:\n{result2.stdout}\n")
                log_file.write(f"STDERR:\n{result2.stderr}\n")
                log_file.write("-" * 40 + "\n")

run_git()
