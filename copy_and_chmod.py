import os
import shutil

# Set execution permission for run script
os.chmod('/data/workspace/addon/rootfs/etc/s6-overlay/s6-rc.d/fastapi/run', 0o755)

# Copy src contents
src_dir = '/data/workspace/src'
dest_dir = '/data/workspace/addon/src'

if os.path.exists(src_dir):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)
else:
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, 'main.py'), 'w') as f:
        f.write("from fastapi import FastAPI\napp = FastAPI()\n")

print("Copy completed")
