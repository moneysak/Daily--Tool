#!/bin/bash
set -e

cd /data/workspace
python3 run_git.py
python3 chmod_scripts.py
