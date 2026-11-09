# Review: "Heute"-Übersichtsseite (Branch develop)

Scope: Implementierung der "Heute"-Übersichtsseite im Alltags-Manager (FastAPI-Backend, Vanilla-JS-Frontend) gegen den Plan.

Gesamturteil: Kein BLOCKER. Dev und Prod sind byte-identisch.

## Geprüfte Bereiche

- Datenmodell: tasks.due_date, tasks.completed_at; routines.weekdays (CSV, Mo=0..So=6), routines.last_completed_on, lazy Reset "heute erledigt".
- Mini-Migration über PRAGMA table_info und ALTER TABLE ADD COLUMN (ensure_schema), ohne Alembic.
- Add-on-Option user_name in beiden config.yaml (Env USER_NAME hat Vorrang, dann options.json).
- Endpoint GET /api/overview?today=YYYY-MM-DD (422 bei ungültigem Datum, 401 ohne Auth im Passwort-Modus).
- Frontend: neuer erster Tab data-target="today", Begrüßung, Fortschrittsbalken, Einkaufs-Karte (springt zum Einkaufs-Tab), Interaktionen, Wochentags-Chips.
- Dev/Prod-Parität über tests/test_parity.py (SHA-256 pro Datei).

## Testergebnisse

- pytest -q: 109 passed, viele DeprecationWarnings für datetime.utcnow().
- Paritätscheck: keine unterschiedlichen, nur-dev oder nur-prod Dateien. config.yaml unterscheidet sich nur in name/version/slug/image/panel/ports (erlaubt).
- Frontend-Diff (index.html, app.js): Today-Tab, renderTodaySections, renderTodayShoppingCard, toggleOverviewTask/toggleOverviewRoutine, greetingFor, activateTab, Wochentags-Chips, escapeHtml vorhanden.
- activateTab-Refactor behält das Klickverhalten bei.
- test_overview_requires_auth einzeln ausgeführt: 2 passed.
- Zeitzonen-Prüfung per Skript: Berlin Di 00:30 ergibt UTC-completed_at am Mo 23:30, .date() liefert Montag. Die beiden Vergleiche widersprechen sich.

## Befunde

1. MAJOR, Zeitzone bei "heute erledigt": update_task setzt completed_at = datetime.utcnow(), die Aggregation vergleicht aber mit dem lokalen Datum des Clients. Zwischen lokaler Mitternacht und UTC-Mitternacht (ca. 00:00 bis 01:00/02:00 in Berlin) landet eine heute erledigte Aufgabe am Vortag und verschwindet aus "heute erledigt" und aus dem Fortschritt. Fix: completed_at mit lokaler Zeitzone setzen (Helper wie local_today() bzw. datetime.now(ZoneInfo(TZ))) oder das Client-Datum mit dem PUT senden.

2. MAJOR, Routinen-Datum serverseitig: update_routine setzt last_completed_on = local_today() (Server-TZ), die Anzeige nutzt aber das Browser-Datum. Ist TZ im Container nicht gesetzt, rechnet der Server in UTC; eine um 00:30 abgehakte Routine kann nach dem Neuladen als offen erscheinen. Nicht verifiziert, ob das Add-on TZ setzt (Dockerfile/run.sh nicht geprüft). Fix: wie bei Befund 1 oder Client-Datum senden.

3. MINOR, Aufgaben-Toggle im Frontend: toggleOverviewTask sendet immer {completed: true}. Eine versehentlich abgehakte Aufgabe lässt sich im Heute-Tab nicht wieder öffnen. Fix: completed: done senden, wie der Routinen-Toggle es bereits tut.

4. MINOR, wöchentliche Routine ohne weekdays: Fallback nutzt den Wochentag von created_at in UTC, der um Mitternacht springen kann. Keine UI-Hinweis.

5. MINOR, Testlücken gegenüber dem Plan:
   - Kein Test für die Zeitzonengrenze (hätte Befund 1 und 2 aufgedeckt).
   - Kein Test für Altdaten mit completed=True und ohne completed_at (Plan T2).
   - Kein Migrationstest mit Routinen-Zeilen.
   - Keine PUT-Tests für ungültige weekdays/frequency (nur POST).
   - T9 ist nur ein statischer String-Check, kein gerenderter XSS-Test.

## Ohne Befund geprüft

- Aggregation: fällig, überfällig (älteste zuerst), someday, Zukünftiges ausgeschlossen, heute erledigt.
- Routinen-Fälligkeitslogik.
- Fortschrittsformel und Division-by-Zero-Schutz.

## Technische Details

- Endpoint: GET /api/overview?today=YYYY-MM-DD
- Fortschritt: total = due_today + overdue + done_today + routines_due; done = done_today + erledigte Routinen.
- local_today() in backend/crud/overview.py nutzt Env TZ über zoneinfo, Fallback UTC.
- Testdatei: tests/test_overview.py, fixes Testdatum 2026-11-09 (Montag), Fixtures client, app_factory, addon_name.

## Offen

- Unklar, ob die Fixes bereits angewendet wurden.
- Nicht verifiziert: setzt der Add-on-Container TZ?
- Bestehende utcnow()-DeprecationWarnings bleiben (vorhandenes Muster, neuer Code übernimmt es).
