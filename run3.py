import subprocess

print("Running shell script...")
res = subprocess.run(["bash", "/data/workspace/init_workspace.sh"], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)

with open("/data/workspace/run.log", "w") as f:
    f.write("STDOUT:\n")
    f.write(res.stdout)
    f.write("STDERR:\n")
    f.write(res.stderr)
