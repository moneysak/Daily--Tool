#!/bin/bash
git config --global user.email 'bot@example.com'
git config --global user.name 'Bot'
git init -b main
git commit --allow-empty -m 'Initial empty commit'
git checkout -b develop
git add addon/ docs/
git commit -m 'Add addon and docs'
chmod +x setup_repo.sh deploy.sh
