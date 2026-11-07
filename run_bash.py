import subprocess

# Running git commands locally since the python runner didn't output properly. I am assuming I can just use python to run bash.
res = subprocess.run(["bash", "-c", """
cd /data/workspace
git config --global user.email 'bot@example.com'
git config --global user.name 'Bot'
git init -b main
git commit --allow-empty -m 'Initial empty commit'
git checkout -b develop
git add addon/ docs/
git commit -m 'Add addon and docs'
chmod +x setup_repo.sh deploy.sh
"""], capture_output=True, text=True)

print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
