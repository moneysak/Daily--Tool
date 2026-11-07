import os
import shutil

src_dir = '/data/workspace/src'
dest_dir = '/data/workspace/addon/src'

for root, dirs, files in os.walk(src_dir):
    for dir in dirs:
        dest_d = os.path.join(dest_dir, os.path.relpath(os.path.join(root, dir), src_dir))
        os.makedirs(dest_d, exist_ok=True)
    for file in files:
        src_f = os.path.join(root, file)
        dest_f = os.path.join(dest_dir, os.path.relpath(src_f, src_dir))
        if not os.path.exists(dest_f):
            shutil.copy2(src_f, dest_f)
