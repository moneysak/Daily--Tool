#!/bin/bash
set -e

echo "=== Initialisiere Git-Repository ==="
cd /data/workspace
git init -b main

echo "=== Erstelle 'develop' Branch ==="
git commit --allow-empty -m "Initialer leerer Commit für Branch-Erstellung"
git checkout -b develop

echo "=== Füge Code und Docs hinzu ==="
git add addon/ docs/
git commit -m "Initialer Commit: Add-on und Docs"

echo "=== Mache Skripte ausführbar ==="
chmod +x /data/workspace/setup_repo.sh
chmod +x /data/workspace/deploy.sh

echo "Git-Repository erfolgreich lokal initialisiert!"
