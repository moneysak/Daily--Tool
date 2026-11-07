#!/bin/bash
set -e

# Zielordner für die Add-ons im Home Assistant Dateisystem
ADDON_BASE_DIR="/addons"

# Dein GitHub Repository und der Token
REPO_URL="https://github.com/moneysak/Daily--Tool.git"
# WICHTIG: Das Token hier direkt zu hinterlegen ist praktisch, aber für maximale Sicherheit
# sollte es später in die `secrets.yaml` von Home Assistant ausgelagert werden.
# Für den Moment belassen wir es hier, damit es einfach funktioniert.
GITHUB_TOKEN="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"
REPO_URL_WITH_TOKEN="https://oauth2:${GITHUB_TOKEN}@github.com/moneysak/Daily--Tool.git"

# Funktion zum Klonen oder Aktualisieren eines Repos
sync_repo() {
    local target_dir=$1
    local branch=$2
    
    echo "Synchronisiere Branch '$branch' nach '$target_dir'..."
    
    if [ -d "$target_dir/.git" ]; then
        echo "Verzeichnis existiert, führe 'git pull' aus..."
        cd "$target_dir"
        git stash
        git pull origin "$branch"
        git stash pop || true
        cd - > /dev/null
    else
        echo "Verzeichnis existiert nicht, führe 'git clone' aus..."
        git clone --branch "$branch" "$REPO_URL_WITH_TOKEN" "$target_dir"
    fi
}

# Add-on neu laden und starten
reload_addon() {
    local addon_slug=$1
    echo "Lade Add-on Store neu..."
    ha addons reload
    
    echo "Starte Add-on '$addon_slug' neu..."
    # Prüfen, ob das Add-on installiert ist
    if ha addons list | grep -q "$addon_slug"; then
        ha addons restart "$addon_slug"
    else
        echo "Add-on '$addon_slug' ist noch nicht installiert. Bitte installiere es manuell aus dem Add-on Store."
    fi
}

# Hauptlogik
if [ "$1" == "staging" ]; then
    ADDON_DIR="${ADDON_BASE_DIR}/alltags-manager-staging"
    ADDON_SLUG="local_alltags_manager_staging"
    BRANCH="develop"
    
    sync_repo "$ADDON_DIR" "$BRANCH"
    reload_addon "$ADDON_SLUG"

elif [ "$1" == "prod" ]; then
    ADDON_DIR="${ADDON_BASE_DIR}/alltags-manager"
    ADDON_SLUG="local_alltags_manager"
    BRANCH="main"
    
    sync_repo "$ADDON_DIR" "$BRANCH"
    reload_addon "$ADDON_SLUG"

else
    echo "Fehler: Ungültiges Argument. Benutze 'staging' oder 'prod'."
    echo "Beispiel: bash $0 staging"
    exit 1
fi

echo "Deployment für '$1' erfolgreich abgeschlossen."
