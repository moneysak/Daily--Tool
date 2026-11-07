#!/bin/bash
set -e

if [ "$1" == "staging" ]; then
    BRANCH="develop"
elif [ "$1" == "prod" ]; then
    BRANCH="main"
else
    echo "Nutzung: $0 [staging|prod]"
    exit 1
fi

echo "Wechsle zu Branch '$BRANCH'..."
git checkout "$BRANCH"

echo "Führe git pull aus..."
git pull origin "$BRANCH"

echo "------------------------------------------------------"
echo "Deployment auf $1 (Branch: $BRANCH) abgeschlossen."
echo "Um den Code im Add-on wirksam zu machen, muss das Add-on neu gestartet werden:"
echo " -> Gehe in Home Assistant zu Einstellungen > Add-ons"
echo " -> Wähle 'Alltags-Manager'"
echo " -> Klicke auf 'Neu starten'"
echo "------------------------------------------------------"
