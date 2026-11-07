# Git Workflow Plan für Alltags-Manager

## Ziel
Umstellung des manuellen Deployments auf einen automatisierten, Git-basierten Workflow für das Home Assistant Add-on 'Alltags-Manager'.

## Branching-Strategie
- `main`: Stabile Version für die Produktion. Aus diesem Branch wird das Add-on regulär im Home Assistant betrieben.
- `develop`: Staging-Bereich für Tests und Weiterentwicklung.

## Architektur des Workflows
1. **Quellcode-Verwaltung:** Das Verzeichnis `/data/workspace` (oder ein Unterordner wie `/data/workspace/addon`) dient als lokales Git-Repository.
2. **Authentifizierung:** HTTPS mit einem Personal Access Token (PAT), da dies für Skripte und Home Assistant Add-on Konfigurationen (options.json) oft leichter zu integrieren ist als SSH-Keys (siehe `docs/research_git_workflow.md`).
3. **Skripte:**
   - `setup_repo.sh`: Initialisiert das Repository, verbindet es mit einem vom Nutzer erstellten Remote (z.B. GitHub/GitLab) und pusht den initialen Code.
   - `deploy.sh`: Aktualisiert das lokale Verzeichnis (`git pull`) und stößt dann die Installation/Aktualisierung des Home Assistant Add-ons an.

## Ablauf (Step-by-Step)
1. **Entwicklung:** Der Nutzer (oder KI) arbeitet im `develop`-Branch.
2. **Test/Staging:** Ein `deploy.sh --staging` (oder ähnlich) macht einen Pull auf den `develop`-Branch und startet das Add-on lokal neu.
3. **Release:** Ein Merge von `develop` in `main`.
4. **Produktion:** Ein `deploy.sh --prod` macht einen Pull auf den `main`-Branch und installiert/aktualisiert das Add-on für den produktiven Einsatz.
