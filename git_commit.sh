#!/bin/bash
chmod +x /data/workspace/run.sh
cd /data/workspace
git fetch origin
git checkout -B develop origin/develop || git checkout -b develop
git add run.sh run.sh.bak
git commit -m "Update run.sh with diagnostic script"
git push -u origin develop
