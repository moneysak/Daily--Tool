# Plan: Migration Dev -> Prod Add-on und Auth-Härtung

Repo: Daily--Tool, Branch `develop` (`main` bleibt unberührt bis zur Freigabe)
Quelle: Dev-Add-on `alltags_manager_dev` (Commit 45b6c0f)
Ziel: Prod-Add-on `alltags_manager` auf Stand bringen, danach Auth in beiden Add-ons härten.

Regeln:
- Jeder Task ist ein eigener Commit auf `develop` (kleiner Diff, für `builder`).
- `config.yaml` bleibt je Add-on verschieden (slug, image, version, Port, Icon).
- Dockerfile und requirements.txt sind identisch und bleiben unverändert.
- Es gibt aktuell kein `tests/`-Verzeichnis; pytest wird in Phase 0 eingeführt.

## Befunde (Begründung der Auth-Tasks)

1. Passwort wirkungslos: auth.py liest `APP_PASSWORD` aus der Umgebung, HA liefert Optionen aber nur in `/data/options.json`. Das Dockerfile-CMD startet uvicorn ohne bashio, daher ist das Passwort immer leer (offener Modus).
2. Ingress-Bypass fälschbar: `require_auth` vertraut dem Header `X-Ingress-Path`, den jeder auf den Standalone-Ports 8050/8051 setzen kann.
3. XSS in `serve_index`: `X-Ingress-Path` wird unvalidiert in ein JS-String-Literal injiziert.
4. Schwächen: `hash_secret` ungenutzt, Klartext-Vergleich, `VALID_SESSIONS` nur im Speicher, Klartext-Passwort wird als Token akzeptiert.

Design-Entscheidungen Auth:
- Passwort wird nur als SHA-256-Hex-Hash gehalten, Vergleich mit `secrets.compare_digest`.
- Tokens via `secrets.token_hex(32)`; in der DB nur `sha256(token)` als `token_hash`.
- Session-Lebensdauer 30 Tage (`SESSION_TTL_DAYS`).
- Kein Klartext-Passwort-Fallback als Token.
- Kein Salt (bewusste Entscheidung, im Docstring von `hash_secret` dokumentiert).

## Abhängigkeiten

T0 -> T1 (in Reihenfolge). T2.1 -> T2.2 und T2.3 (parallel) -> T2.4 -> T2.5. T2.6 und T2.7 unabhängig nach T2.4. T2.8 braucht T2.5. T2.9 braucht alle T2.x. T3 zuletzt.

---

## Phase 0: Testbasis

### T0.1 ALLTAGS_DATA_DIR-Override
- Dateien: Dev `backend/db/database.py` (Pfad relativ zum Add-on-Verzeichnis, genaue Lage per `ls` prüfen)
- Beschreibung: Datenverzeichnis über Umgebungsvariable `ALLTAGS_DATA_DIR` überschreibbar machen (Default `/data`), damit Tests eine temporäre DB nutzen.
- Akzeptanz:
  - Ohne Variable unverändertes Verhalten (`/data`).
  - Mit gesetzter Variable liegt die SQLite-Datei im angegebenen Verzeichnis.

### T0.2 pytest-Gerüst
- Dateien: `tests/conftest.py`, `tests/test_smoke.py`, `requirements-test.txt`
- Beschreibung: Fixture `addon`, parametrisiert über beide Add-ons (Dev und Prod). Pro Lauf werden sys.path und geladene Module zurückgesetzt, `ALLTAGS_DATA_DIR` zeigt auf tmp_path. Smoke-Test ruft die App per TestClient auf.
- Akzeptanz:
  - `pytest` läuft grün für beide Add-ons (Prod-Smoke darf nur Basis-Endpunkte prüfen, die schon existieren).
  - Kein Test schreibt nach `/data`.

---

## Phase 1: Prod-Sync (rein mechanische Kopie aus Dev)

### T1.1 Datenschicht
- Dateien: Prod `db/database.py`, `models/`, `schemas/`, `crud/` (Kopie aus Dev; Unterschiede laut diff: crud/task.py, db/database.py, models/task.py, schemas/task.py)
- Beschreibung: Dateien 1:1 aus Dev nach Prod kopieren.
- Akzeptanz:
  - `diff -r` der betroffenen Verzeichnisse Dev vs. Prod ist leer.
  - Smoke-Test grün für Prod.
  - Bestehende Prod-Datenbank startet ohne Fehler (Tabellen werden ergänzt, nichts gelöscht).

### T1.2 main.py
- Dateien: Prod `main.py`
- Beschreibung: Aus Dev kopieren (Shopping- und Routines-CRUD, Hermes-Proxy, Ingress-Injection).
- Akzeptanz:
  - `diff` main.py Dev vs. Prod leer.
  - App importiert und startet im Test; neue Endpunkte antworten (200/401, je nach Auth-Modus).

### T1.3 Frontend
- Dateien: Prod `index.html`, `app.js`, `style.css`
- Beschreibung: Aus Dev kopieren.
- Akzeptanz:
  - `diff` der drei Dateien Dev vs. Prod leer.
  - `GET /` liefert HTML mit eingebettetem app.js-Bezug ohne Fehler.

### T1.4 Paritätstest
- Dateien: `tests/test_parity.py`
- Beschreibung: Vergleicht per Datei-Hash alle Dateien unter `src/` beider Add-ons. Für `config.yaml` sind nur diese Felder erlaubt abzuweichen: name, description, version, slug, image, panel_icon, panel_title, ports.
- Akzeptanz:
  - Test grün nach T1.1 bis T1.3.
  - Test wird rot, wenn eine Quelldatei oder ein nicht erlaubtes config-Feld abweicht.
- Unberührt: config.yaml, build.yaml, Dockerfile, requirements.txt, rootfs.

---

## Phase 2: Auth-Härtung (zuerst Dev, dann Kopie nach Prod)

### T2.1 Session-Modell
- Dateien: Dev `models/session.py`, Registrierung in `db/database.py`
- Beschreibung: Tabelle `sessions` mit `token_hash` (PK), `created_at`, `expires_at`, `last_seen`.
- Akzeptanz:
  - Tabelle wird beim Start angelegt.
  - Test: Insert und Query funktionieren.

### T2.2 Passwort-Konfiguration und Verifikation
- Dateien: Dev `auth.py`, `tests/test_auth_password.py`
- Beschreibung: `get_configured_password()` liest zuerst Umgebung (`APP_PASSWORD`), dann `/data/options.json` (`app_password`; Pfad via `ALLTAGS_OPTIONS_PATH` überschreibbar). `verify_password(candidate)` hasht und vergleicht mit `secrets.compare_digest` gegen SHA-256-Hash. `hash_secret` erhält Docstring zur Salt-Entscheidung.
- Akzeptanz:
  - Passwort aus options.json wird erkannt.
  - Richtiges Passwort: True, falsches: False, leeres Passwort konfiguriert = offener Modus.
  - Kein Klartext-Vergleich mehr im Code.

### T2.3 DB-gestützte Sessions
- Dateien: Dev `auth.py`, `tests/test_auth_sessions.py`
- Beschreibung: Funktionen `hash_token`, `create_session_token(db)`, `verify_session_token(db, token)`, `revoke_session(db, token)`, `purge_expired(db)`. `VALID_SESSIONS` entfällt. Token = `secrets.token_hex(32)`, gespeichert nur als Hash, TTL 30 Tage.
- Akzeptanz:
  - Erzeugtes Token verifiziert; nach `revoke_session` nicht mehr.
  - Abgelaufenes Token wird abgelehnt und von `purge_expired` entfernt.
  - Session überlebt Neuaufbau der App (Persistenz-Test).
  - In der DB steht nie das Klartext-Token.

### T2.4 require_auth neu
- Dateien: Dev `auth.py`, `db/database.py` (`get_db` dorthin verschieben), `main.py`
- Beschreibung: `require_auth` als Dependency mit DB-Zugriff. Akzeptiert nur gültige Session-Tokens (oder offenen Modus). Klartext-Passwort als Token entfällt.
- Akzeptanz:
  - Geschützter Endpunkt ohne Token: 401, mit gültigem Token: 200.
  - Klartext-Passwort als Token: 401.
  - Alle bisherigen Endpunkte weiterhin geschützt.

### T2.5 Login und Logout
- Dateien: Dev `main.py` (oder Auth-Router), `tests/test_auth_endpoints.py`
- Beschreibung: Login prüft via `verify_password`, erzeugt Session, ruft `purge_expired`. Neuer Logout-Endpunkt widerruft das Token.
- Akzeptanz:
  - Falsches Passwort: 401, richtiges: 200 mit Token.
  - Nach Logout ist das Token ungültig (401).

### T2.6 Ingress-Vertrauen einschränken
- Dateien: Dev `auth.py`, `tests/test_auth_ingress.py`
- Beschreibung: `X-Ingress-Path` wird nur akzeptiert, wenn die Client-IP `172.30.32.2` ist (überschreibbar via `ALLTAGS_INGRESS_TRUSTED_IPS`).
- Akzeptanz:
  - Request mit Header von beliebiger anderer IP: 401.
  - Request mit Header von vertrauter IP: durchgelassen.

### T2.7 XSS-Fix in serve_index
- Dateien: Dev `main.py`, `tests/test_index_xss.py`
- Beschreibung: Ingress-Pfad nur bei Match auf `^/[A-Za-z0-9/_\-.]*$` verwenden, sonst leerer Fallback; Einbettung via `json.dumps`.
- Akzeptanz:
  - Header mit `"; alert(1); //` oder `</script>` taucht nicht im HTML auf.
  - Gültiger Pfad wird korrekt eingesetzt.

### T2.8 Frontend 401-Behandlung und Logout
- Dateien: Dev `app.js`, `index.html`, `style.css`
- Beschreibung: Bei 401 Login-Ansicht zeigen und Token verwerfen; optionaler Logout-Button ruft den Logout-Endpunkt.
- Akzeptanz (manuell):
  - Abgelaufene/ungültige Session führt zur Login-Maske, nicht zu leerer Seite.
  - Logout-Button beendet die Session.

### T2.9 Auth nach Prod kopieren
- Dateien: Prod `auth.py`, `models/session.py`, `db/database.py`, `main.py`, Frontend-Dateien
- Beschreibung: Alle Änderungen aus T2.1 bis T2.8 1:1 nach Prod.
- Akzeptanz:
  - Alle Tests für beide Add-ons grün.
  - `test_parity.py` grün.

---

## Phase 3: Rollout

### T3.1 (optional) Hermes-Optionen im config.yaml-Schema
- Dateien: beide `config.yaml`
- Beschreibung: `hermes_api_url` und `hermes_api_key` im options/schema deklarieren (ebenso `app_password`, falls noch nicht vorhanden).
- Akzeptanz:
  - Optionen erscheinen in der HA-UI des Add-ons.
  - Parity-Test weiterhin grün (erlaubte Felder ggf. erweitern).

### T3.2 CI-Testjob
- Dateien: `.github/workflows/*.yml`
- Beschreibung: Job `test` (pytest) als `needs`-Abhängigkeit vor dem Multi-Arch-Build.
- Akzeptanz:
  - Roter Test verhindert den Image-Build.
  - Grüner Lauf baut wie bisher.

### T3.3 Versionen und Abnahme
- Dateien: beide `config.yaml` (nur Version)
- Beschreibung: Dev auf 1.0.2-dev, Prod auf 1.0.1, nur auf `develop`. Manuelle Abnahme auf Port 8051 (Dev).
- Akzeptanz:
  - Checkliste: Login mit Passwort, Fehlversuch, Logout, Session nach Add-on-Neustart noch gültig, Ingress-Zugriff ohne Login, Direktzugriff mit gefälschtem Header wird abgewiesen.
  - Merge nach `main` erst nach ausdrücklicher Freigabe durch Daniel.

---

## Offene Punkte

1. Session-Lebensdauer 30 Tage ok?
2. Offener Modus ohne Passwort beibehalten (Risiko auf Standalone-Port)?
3. T3.1 behalten?
4. Verifikation im Betrieb: Kommt HA-Ingress tatsächlich von 172.30.32.2?
