# Review: Migration Dev-Fixes nach Prod und Auth-Härtung

Repo: `/data/workspace/Daily--Tool`, Branch `develop`
Grundlage: `docs/plan_migration_and_auth.md`

## Prüfumfang

1. Auth-Sicherheit (compare_digest, kein Klartext, Session-TTL, kein Klartext-Token in der DB, Ingress-IP-Prüfung, XSS-Fix)
2. Parität zwischen `alltags_manager` (prod) und `alltags_manager_dev`
3. CI-Workflow-Korrektheit
4. `config.yaml`-Gültigkeit für Home Assistant
5. Testlücken

## Stand des Working Trees

- 18 geänderte Dateien, 4 ungetrackte Einträge (`models/session.py` in beiden Add-ons, `docs/plan_migration_and_auth.md`, `requirements-test.txt`, `tests/`)
- Umfang ca. +1744 / -370 Zeilen
- Keine Dateien wurden im Rahmen des Reviews geändert.

## Geprüfte Quellen

- `auth.py`, `main.py`, `database.py`, `models/session.py`
- CI-Workflow-Diff
- `config.yaml`-Diffs beider Add-ons
- Frontend-Auth-Code

## Parität

- `src/` ist in beiden Add-ons identisch (nur `__pycache__` unterscheidet sich).
- Dockerfile und requirements.txt sind identisch.
- Unterschiede in den Config-Dateien beschränken sich auf erlaubte Felder.

## Testergebnis

- pytest: 53 passed in ca. 4,8 s (Python 3.13.5, pytest 9.2.0)
- Ca. 187 DeprecationWarnings wegen `datetime.utcnow()`
- Ein zweiter Lauf war ebenfalls grün (53 passed).
- Zwei Inline-`python3 -c`-Aufrufe wurden durch die Approval-Policy blockiert. Der Import-Zyklus-Check ist daher nur indirekt über die Testsuite abgedeckt.
- Hinweis: Eine Ausgabe von `test_auth_endpoints.py` zeigte `"***"` als Passwort. Folgelesungen ergaben `geheim` und `falsch`; die erste Ausgabe war ein Anzeigeartefakt.

## Befunde

### BLOCKER

- Keine.

### MAJOR

1. Kein Rate-Limit auf `/api/auth/login`. Brute-Force ist auf den Standalone-Ports 8050/8051 unbegrenzt möglich.
2. In beiden `config.yaml` ist `hermes_api_url: "url?"` mit Default `""` deklariert. Der HA-Validator für `url` lehnt einen leeren String wahrscheinlich ab, was das Speichern der Optionen oder die Installation brechen kann. Nicht gegen den HA-Validator verifiziert.
   - Fix-Vorschlag: Default entfernen oder `str?` verwenden. Vor dem Merge in der HA-UI testen.
3. Open Mode (kein Passwort) ist auf den Standalone-Ports weiterhin erreichbar. Offene Entscheidung laut Plan.
4. Die vertrauenswürdige Ingress-IP `172.30.32.2` ist im Produktivbetrieb nicht verifiziert. Weicht sie ab, liefert Ingress 401. Nur die manuelle Abnahme (T3.3) kann das aufdecken.

### MINOR

5. Die Regel "ein Commit pro Task" aus dem Plan wurde nicht eingehalten; alles liegt als ein uncommitteter Batch vor.
6. `datetime.utcnow()` ist veraltet (16 Vorkommen in Backend und Tests). Ersetzen durch `datetime.now(timezone.utc)`.
7. `verify_session_token` schreibt `last_seen` bei jedem Request (DB-Schreiblast). Für persönliche Nutzung akzeptabel.
8. Das Token liegt in `sessionStorage` und ist bei XSS lesbar. Der XSS-Fix mindert das Risiko.
9. Testlücken:
   - Kein Test für erfolgreichen Login mit `X-Auth-Token` (nur Bearer getestet).
   - Kein Test für Logout ohne Token oder doppeltes Logout.
   - Kein Test, dass die Env-Variable `APP_PASSWORD` Vorrang vor `options.json` hat.
   - Kein Test für vertrauenswürdige IP kombiniert mit `X-Ingress-Path` auf `/`.
   - Kein Migrationstest für eine bestehende prod-DB (verlangt durch Plan T1.1).
   - `test_no_plaintext_password_comparison_in_auth_sources` ist ein String-Grep und prüft wenig.
   - CI läuft mit Python 3.12, lokale Tests mit 3.13.
10. CI-`pip install` ohne Versions-Pins. Der Test-Job installiert nur die Dev-Requirements; die Prod-Requirements sind identisch, daher geringes Risiko.

### Geprüft und in Ordnung

- CI-Änderung (`needs: test` in beiden Build-Jobs) ist korrekt verdrahtet.
- Frontend-Listenrendering nutzt `escapeHtml` für Nutzerdaten; Chat-Antworten nutzen `textContent`.
- Nur Hash des Tokens wird gespeichert; abgedeckt durch `test_token_not_stored_in_plaintext`.

## Technische Details

- `hash_secret` = SHA-256 hex, bewusst ohne Salt (im Docstring dokumentiert).
- Tokens: `secrets.token_hex(32)`; in Tabelle `sessions` wird nur `sha256(token)` gespeichert (`token_hash` PK, `created_at`, `expires_at`, `last_seen`).
- `SESSION_TTL_DAYS = 30`.
- Vertrauenswürdige Ingress-IP Default `172.30.32.2`, überschreibbar via `ALLTAGS_INGRESS_TRUSTED_IPS`.
- Passwort-Reihenfolge: Env `APP_PASSWORD`, dann `/data/options.json` (`app_password`); Pfad überschreibbar via `ALLTAGS_OPTIONS_PATH`.
- Datenverzeichnis: `ALLTAGS_DATA_DIR` (Default `/data`).
- XSS-Fix: `_INGRESS_PATH_RE = ^/[A-Za-z0-9/_\-.]*$`, Injektion via `json.dumps`.
- CI: neuer Job `test` führt `pytest tests -q` mit Python 3.12 aus, installiert `alltags_manager_dev/requirements.txt` und `requirements-test.txt`.
- Testdateien: `conftest.py`, `test_smoke.py`, `test_parity.py`, `test_auth_password.py`, `test_auth_sessions.py`, `test_auth_endpoints.py`, `test_auth_ingress.py`, `test_index_xss.py`, `test_auth_model.py` (9 Dateien, 604 Zeilen).
- Versionen im Working Tree: prod `1.0.1`, dev `1.0.2-dev`.

## Offene Punkte

- Rate-Limiting für Login: Entscheidung ausstehend.
- Open Mode ohne Passwort auf Standalone-Ports: Entscheidung ausstehend.
- Optionaler Task T3.1 (Hermes-Optionen im Schema): Entscheidung, ob beibehalten; beide Config-Dateien enthalten ihn bereits.
- Schema-Problem `url?` in der HA-UI bzw. dem Validator prüfen.
- Ingress-Quell-IP im Betrieb bestätigen.
- Commit-Strategie: Plan verlangt einen Commit pro Task, derzeit alles uncommittet.

Empfohlene nächste Schritte: Config-Schema-Problem prüfen/beheben, Rate-Limiting entscheiden, dann Commits pro Task.
