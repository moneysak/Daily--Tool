#!/bin/bash
cd /data/workspace
git config --global user.email "test@example.com"
git config --global user.name "Test User"
git checkout -B develop
git add run.sh run.sh.bak
git commit -m "Update run.sh for diagnostic script"
git push -u origin develop
