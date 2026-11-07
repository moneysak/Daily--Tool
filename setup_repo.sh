#!/bin/bash
set -e

echo "=== GitHub Repository Setup ==="
echo "Bitte erstelle nun ein leeres Repo auf GitHub (ohne README/gitignore/Lizenz)."
echo "Da wir mit HTTPS arbeiten (für bessere Kompatibilität im Add-on), verwende bitte die HTTPS-URL."
read -p "Gib die Remote-URL ein (z.B. https://github.com/user/repo.git): " REMOTE_URL

if [ -z "$REMOTE_URL" ]; then
    echo "Keine URL angegeben. Setup abgebrochen."
    exit 1
fi

echo "Initialisiere Git..."
git init

echo "Erstelle und wechsle zu 'main'..."
git branch -m main || git checkout -b main
# Leerer Init-Commit für main
git commit --allow-empty -m "Initial empty commit on main"

echo "Erstelle und wechsle zu 'develop'..."
git checkout -b develop

echo "Füge Code hinzu..."
git add addon/ docs/
git commit -m "Initialer Import von addon und docs auf develop"

echo "Füge Remote hinzu..."
git remote add origin "$REMOTE_URL"

echo "Pushe main..."
git push -u origin main

echo "Pushe develop..."
git push -u origin develop

echo "Remote 'origin' hinzugefügt und Branches hochgeladen!"
