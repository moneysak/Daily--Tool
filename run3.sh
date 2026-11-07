#!/bin/bash
cd /data/workspace
git config user.email 'bot@example.com'
git config user.name 'Bot'
git add -A
git commit -m 'Implement GET/POST/PUT tasks in frontend and backend'
git push origin develop
