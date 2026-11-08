# Lessons Learned & Vereinfachungs-Strategie: Alltags-Manager Add-on

## 1. Was gestern schiefgelaufen ist (Root-Cause-Analyse)

### A. Container-Isolation & Missverständnisse der HA-Umgebung
* **Problem:** Hermes läuft selbst als isoliertes Docker-Add-on und hat keinen direkten Schreibzugriff auf das Host-Dateisystem (`/config/www`, `/addons`, `/share`). Frühere Versuche, Dateien direkt via Bash/Python nach `/addons` oder `/config/www` zu schieben, schlugen fehl.
* **Folge:** Ein Wirrwarr aus temporären Hilfsskripten (`run_now*.py`, `do_git*.py`, etc.) im Workspace, da der Agent versuchte, Berechtigungsbarrieren mit Workarounds zu umgehen.

### B. Docker Base-Images & Supervisor-Restriktionen (`ghcr.io` 403 Forbidden)
* **Problem:** Beim Bauen des Add-ons in Home Assistant zieht der HA Supervisor die Base-Images anonym. Anfragen an `ghcr.io` (GitHub Container Registry) scheiterten reproduzierbar an Authentifizierungs- & Rate-Limits (HTTP 403 Forbidden).
* **Lösung:** Offizielle Base-Images müssen über Docker Hub bezogen werden oder `build.yaml` mit sauberen Architektur-Mappings definiert sein.

### C. Architektur-Spezifika (Multi-Arch `aarch64` vs `amd64`)
* **Problem:** Hardcodierte Architektur-Strings führen auf Home Assistant (meist Raspberry Pi/ODROID mit `aarch64` oder Intel/NUC mit `amd64`) zu Build-Abbrüchen.
* **Lösung:** Saubere Nutzung von Supervisor-Build-Argumenten (`ARG BUILD_FROM`) und `build.yaml`.

### D. Git-Deployment & Token-Handling
* **Problem:** Das Deployment über manuelles Kopieren war fehleranfällig. Die Umstellung auf Git war der richtige Schritt, führte aber durch Authentifizierungshürden und unstrukturierte Test-Commits zu Verwirrung.

---

## 2. Review deiner manuellen Korrekturen

* **Supervisor-Token & Chat-API (`main.py`):**
  * Du hast das Supervisor-Token bzw. die Kommunikation mit der Home Assistant Core API geradegerückt.
  * *Hinweis für Reviewer:* Achte darauf, Tokens nicht im Klartext im Git-Repository zu committen. Tokens sollten idealerweise dynamisch über das Supervisor-Environment (`$SUPERVISOR_TOKEN`) oder `options.json` des Add-ons übergeben werden.
* **Frontend Tasks (`app.js`):**
  * Du hast den Task-Lösch-Button (`🗑️`) ergänzt und den Event-Flow korrigiert.
* **Add-on-Lauffähigkeit:**
  * Das Add-on startet nun sauber via s6-overlay mit Uvicorn auf Port 8099 und wird per Ingress in der HA-Seitenleiste gerendert.

---

## 3. Wie wir das drastisch vereinfachen (Standard-Playbook)

Statt Ad-hoc-Skripten etablieren wir für das Team einen sauberen, standardisierten 3-Schritte-Workflow:

### 1. Workspace-Hygiene
* Alle 30+ temporären Debug-Skripte (`run_now*.py`, `execute_*.py`) aus dem Workspace entfernen.
* Der Workspace bleibt eine saubere Codebase mit:
  ```text
  /data/workspace/
  ├── Dockerfile
  ├── build.yaml
  ├── config.yaml
  ├── requirements.txt
  ├── rootfs/
  └── src/ (backend & frontend)
  ```

### 2. Standardisierter Git-Release-Workflow (Single Source of Truth)
* **Kein manuelles Kopieren mehr.**
* Änderungen werden ausschließlich im Git (`develop` für Staging, `main` für Prod) gepusht.
* Das Add-on in Home Assistant holt sich Updates über die lokale Add-on-Aktualisierung oder einen einfachen `git pull` im Zielordner `/addons/alltags-manager-staging/`.

### 3. Klare Rollenaufteilung im Team
* **Architect (Gemini Pro):** Plant Schnittstellen & DB-Schema in `docs/architecture.md`.
* **Researcher (Gemini Flash):** Prüft HA-APIs, S6-Overlay-Standards & Pydantic/FastAPI Versionen.
* **Coder (Claude Sonnet):** Schreibt sauberen Code direkt in `src/` (ohne Meta-Bash-Wrapper).
* **Reviewer (DeepSeek):** Validiert Codequalität, Security (keine hardcodierten Tokens) und testet Syntax.
