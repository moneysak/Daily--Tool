# HA-Integration (Kalender + To-do-Listen) in "Heute" – Implementierungsplan

> Für die Umsetzung: subagent-driven-development, Task für Task (Coder = Sonnet).
> Status: nur Plan, KEIN Code. Branch `develop`, kein Commit, kein Eingriff in `main`.

**Ziel:** Die Heute-Seite zeigt zwei neue Abschnitte: "Termine heute" (HA-Kalender) und "To-dos" (HA-To-do-Listen, abhakbar mit Rückschreiben nach HA). Fehlt HA oder ist es nicht erreichbar, werden die Abschnitte lautlos ausgeblendet.

**Architektur:** Neues Backend-Modul `crud/ha.py` (Name an `crud/overview.py` angelehnt, damit der Modul-Reset in conftest greift) kapselt einen httpx-Client auf den Supervisor-Proxy. `/api/overview` bleibt unverändert und DB-only. Zwei neue, getrennte Endpunkte liefern die HA-Daten. Das Frontend lädt sie parallel und unabhängig von der Übersicht.

**Tech Stack:** FastAPI, httpx (schon in requirements), pydantic, pytest + `httpx.MockTransport`, Vanilla-JS.

---

## 0. Korrekturen zum Briefing (wichtig, vor Umsetzung lesen)

1. Die HA-REST-API hat KEINE Endpunkte `/api/todo/lists`, `/api/todo/lists/{id}/items` oder `/api/todo/items/{id}/update`. To-do-Listen werden über Services angesprochen:
   - Lesen: `POST /core/api/services/todo/get_items?return_response` mit Body `{"entity_id": "todo.x", "status": ["needs_action"]}`. Antwort: `{"changed_states": [], "service_response": {"todo.x": {"items": [{"summary","uid","status","due","description"}]}}}`. Braucht HA >= 2023.7 (Service-Response). Ohne `?return_response` kommt keine Antwort zurück.
   - Schreiben: `POST /core/api/services/todo/update_item` mit Body `{"entity_id": "todo.x", "item": "<uid>", "status": "completed"|"needs_action"}`. `item` akzeptiert uid oder summary, wir nutzen immer die uid.
   - Namen der Listen: `GET /core/api/states/todo.x` -> `attributes.friendly_name` (state = Anzahl offener Items).
2. Kalender: `GET /core/api/calendars/{entity_id}?start=<ISO>&end=<ISO>` (start/end Pflicht, ISO 8601 mit Offset). `GET /core/api/calendars` liefert nur die Entity-Liste (für Namen nutzbar, aber nicht nötig).
3. `X-Hass-User-ID` wird NICHT benötigt und NICHT gesendet. Nur `Authorization: Bearer $SUPERVISOR_TOKEN`.
4. Basis-URL: `http://supervisor/core/api`. Token aus Env `SUPERVISOR_TOKEN`. Fehlt die Variable, gilt HA als "nicht verfügbar" (Standalone).
5. Der Supervisor-Token hat Zugriff auf alle Entities. Daher MUSS das Backend selbst gegen die konfigurierte Allowlist prüfen (siehe 1.4), sonst könnte jeder App-Nutzer beliebige HA-Todo-Entities schreiben.

---

## 1. API-Vertrag (App-Backend, alle mit `Depends(require_auth)`)

### 1.1 GET /api/ha/agenda?today=YYYY-MM-DD
`today` optional wie bei `/api/overview` (Default `local_today()`, ungültig -> 422).

Antwort 200 (immer 200, auch bei HA-Ausfall):
```
{
  "available": true,            // false: kein Token / HA nicht erreichbar / nichts konfiguriert
  "date": "2026-11-09",
  "events": [
    {
      "calendar": "calendar.familie",
      "calendar_name": "Familie",
      "title": "Zahnarzt",
      "all_day": false,
      "start": "2026-11-09T14:30:00+01:00",   // all_day: "2026-11-09"
      "end":   "2026-11-09T15:30:00+01:00",
      "location": null
    }
  ]
}
```
Regeln: Sortierung All-Day zuerst, dann nach Startzeit, dann Titel. Einzelner fehlschlagender Kalender wird übersprungen (die anderen kommen trotzdem). `available=false` nur, wenn kein Token ODER alle Abfragen mit Verbindungsfehler/401 scheitern ODER Liste leer konfiguriert. Mehrtägige Events, die heute überlappen, sind enthalten. All-Day-`end` ist bei HA exklusiv (Event "heute" hat end = morgen) -> beim Filtern beachten.

### 1.2 GET /api/ha/todos
Antwort 200:
```
{
  "available": true,
  "lists": [
    {
      "entity_id": "todo.einkaufsliste",
      "name": "Einkaufsliste",
      "items": [
        {"uid": "abc", "summary": "Milch", "status": "needs_action", "due": null}
      ]
    }
  ]
}
```
Regeln: Reihenfolge der Listen = Reihenfolge in der Konfiguration. Pro Liste nur `needs_action` (Erledigte erscheinen nach Abhaken erst nach Reload nicht mehr; für Rückgängig siehe 1.3/Frontend). Listen mit 0 Items bleiben im Array (Frontend blendet leere aus). Fehlerhafte Einzelliste wird übersprungen.

### 1.3 POST /api/ha/todos/item
Body: `{"entity_id": "todo.x", "uid": "abc", "completed": true}`
- 200 `{"status": "success"}`
- 403 wenn `entity_id` nicht in der konfigurierten `todo_entities`-Liste
- 422 bei fehlenden Feldern/ungültiger Entity-ID (Regex `^todo\.[a-z0-9_]+$`)
- 503 wenn HA nicht verfügbar
- 502 wenn HA den Service-Call ablehnt (Detail-Text, deutsch)
Mapping: `completed=true` -> `status: "completed"`, `false` -> `"needs_action"`.

### 1.4 Allowlist
Gültig sind ausschließlich die in den Add-on-Optionen konfigurierten Entity-IDs. Es gibt KEINE Discovery-Endpunkte (YAGNI).

### 1.5 Entscheidung: separate Endpunkte statt /api/overview erweitern
Gründe: (a) `/api/overview` bleibt schnell, deterministisch und offline-fähig, bestehende Tests bleiben grün; (b) HA-Latenz (bis 11 Kalender-Calls) blockiert nicht die Kernansicht; (c) HA-Fehler können die Übersicht nie brechen; (d) einfacheres Mocken. Frontend lädt alles parallel.

---

## 2. Konfiguration (Add-on-Optionen)

In BEIDEN `config.yaml` (`alltags_manager/` und `alltags_manager_dev/`) identisch ergänzen (config.yaml wird vom Paritätstest verglichen; nur die erlaubten Felder dürfen abweichen):
```
options:
  ...
  calendar_entities: []
  todo_entities: []
schema:
  ...
  calendar_entities:
    - "match(^calendar\\.[a-z0-9_]+$)?"
  todo_entities:
    - "match(^todo\\.[a-z0-9_]+$)?"
```
Hinweis: Syntax für Listen mit Regex-Schema gegen die HA-Add-on-Doku prüfen (optionale Listenelemente `?`); Fallback `- str?`, falls der Supervisor `match()` in Listen ablehnt. Das Backend validiert zusätzlich selbst per Regex und ignoriert ungültige Einträge.

Semantik: leere Liste = Funktion für diesen Typ aus (opt-in, kein Rauschen durch z.B. Feiertage/Geburtstage). Versionen in beiden config.yaml anheben (dev z.B. `1.0.4-dev`, prod nur wenn Daniel es freigibt – Version ist laut Paritätstest erlaubte Abweichung). `homeassistant_api: true` ist bereits gesetzt.

Lesen der Optionen: dieselbe Quelle wie `auth._options_path()` (`ALLTAGS_OPTIONS_PATH`, Default `/data/options.json`), bei jedem Request frisch (wie `get_user_name`). Zusätzlich Env-Override `ALLTAGS_CALENDAR_ENTITIES` / `ALLTAGS_TODO_ENTITIES` (CSV) für Standalone/Tests. Reihenfolge: Env > options.json > leer.

---

## 3. Backend-Struktur

Neu (identisch in beiden Add-ons unter `src/backend/`):
- `crud/ha.py` – HA-Client + Mapping (kein FastAPI-Wissen)
- `schemas/ha.py` – Pydantic-Modelle: `AgendaEvent`, `AgendaResponse`, `TodoItem`, `TodoList`, `TodosResponse`, `TodoToggle`
- Änderung `main.py` – drei neue Routen im Block "# --- Home-Assistant-Integration ---" vor "Hermes Chat API Proxy"

Schnittstellen in `crud/ha.py` (nur Signaturen/Verträge):
- `get_ha_token() -> str | None` (Env `SUPERVISOR_TOKEN`)
- `get_ha_base_url() -> str` (Env `ALLTAGS_HA_BASE_URL`, Default `http://supervisor/core/api`; Override für Tests)
- `get_configured_entities(kind: "calendar"|"todo") -> list[str]` (Allowlist, validiert, dedupliziert)
- `make_client() -> httpx.AsyncClient` (Timeout 5 s, Header gesetzt; Tests ersetzen die Factory per monkeypatch durch `MockTransport`)
- `async fetch_agenda(day: date) -> dict` / `async fetch_todos() -> dict` / `async set_todo_status(entity_id, uid, completed) -> None`
- Eigene Exceptions: `HAUnavailable` (kein Token/Netzfehler/401/Timeout), `HARejected` (4xx/5xx des Service-Calls)
- Parallele Abfragen mit `asyncio.gather(return_exceptions=True)`.
- Tageszeitraum: `start = 00:00` lokal (TZ aus `crud.overview._local_timezone()`, Fallback UTC), `end = nächster Tag 00:00`, jeweils `isoformat()` mit Offset; httpx `params=` übernimmt das URL-Encoding (das `+` im Offset!).
- Event-Mapping: `start.date` vorhanden -> `all_day=true`; sonst `start.dateTime` parsen. Titel aus `summary` (Fallback "(ohne Titel)"). Nie Beschreibung durchreichen (YAGNI/Datenschutz).
- Logging: nur Entity-ID + Fehlerklasse, niemals Token.
- Routen sind `async def` (httpx async, wie Hermes-Proxy).

---

## 4. Frontend-Aufgaben (`src/frontend/`, in beiden Add-ons identisch)

- `index.html`: im Heute-Template (bzw. `contentMap['today']` in app.js) zwei Slots `<div id="agenda-slot">` und `<div id="todos-slot">` nach `#today-sections`, vor/neben `#shopping-card-slot` (Reihenfolge: Termine, Aufgaben/Routinen, HA-To-dos, Shopping-Karte; Termine sollen oben stehen).
- `app.js` (Block "5. TODAY OVERVIEW LOGIC"):
  - `loadAgenda()` und `loadTodos()` – parallel zu `loadOverview()` aus `renderActiveTab()` aufrufen. Eigenes try/catch; bei Fehler, Non-200 oder `available:false` -> Slot leeren (`innerHTML = ''`), nur `console.warn`, KEIN Fehlerbanner. 401 -> `handleUnauthorized()` wie bisher.
  - `renderAgenda(data)`: Block mit `h2.section-title` "Termine heute". Pro Event: Zeit-Spalte (`HH:MM` via `toLocaleTimeString('de-DE')` oder "Ganztägig"), Titel, optional Kalendername als kleines Badge. Keine Events -> Slot leer (kein "keine Termine"-Text, laut Anforderung ausblenden).
  - `renderTodos(data)`: Block "To-dos", je Liste Untertitel (`list.name`), Zeilen mit Checkbox `.ha-todo-checkbox` + `data-entity`/`data-uid`. Leere Listen auslassen; alle leer -> Slot leer.
  - Abhaken: optimistisch (Zeile durchgestrichen), `POST /api/ha/todos/item`; bei Fehler Checkbox zurücksetzen und kurze Inline-Meldung; bei Erfolg Zeile nach ~600 ms entfernen (kein vollständiger Reload, HA-Latenz). Kein Rückgängig-Pfad in v1 (YAGNI), API unterstützt `completed:false` trotzdem.
  - Ausnahmslos `escapeHtml()` für `summary`, `title`, `name`; Attribute `data-*` ebenfalls escapen (Test `test_index_xss`/`test_app_js_overview_and_escaping` als Vorbild). Entity-IDs/uids nur über `dataset` auslesen.
  - `attachTodayListeners()` um die HA-Checkboxen erweitern (Event-Delegation auf `#todos-slot` ist einfacher, da asynchron gerendert).
  - Alle Fetches via `apiBaseUrl` + `getAuthHeaders()` (Ingress-fähig).
- `style.css`: wiederverwendet `.today-block`, `.section-title`, `.app-list`, `.list-item`, `.glass-panel`. Neu nur: `.agenda-time` (feste Breite, tabular-nums, gedämpfte Farbe), `.agenda-allday` (Badge-Stil), `.agenda-cal` (kleines Badge), `.todo-list-title` (Untertitel, klein/gedämpft). Mobile: Zeit-Spalte schrumpft, Titel umbricht.

---

## 5. Test-Plan (pytest, HA gemockt)

Neue Datei `tests/test_ha_integration.py`, parametrisiert über beide Add-ons (Fixtures `client`, `app_factory`, `addon_name`). Fester Testtag `2026-11-09`.

Mock-Strategie: In `crud.ha` ist `make_client` ersetzbar. Fixture `ha_mock(monkeypatch, handler)` baut `httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=..., headers=...)`. Handler routet nach `request.url.path`:
- `/calendars/<entity>` -> JSON-Event-Liste (pro Entity konfigurierbar, auch 500/Exception)
- `/services/todo/get_items` (Query enthält `return_response`) -> service_response
- `/services/todo/update_item` -> 200 `[]` (Body wird mitgeschnitten und geprüft)
- `/states/todo.x` -> friendly_name
Zusätzlich Fixture `ha_env` (setzt `SUPERVISOR_TOKEN`, `ALLTAGS_CALENDAR_ENTITIES`, `ALLTAGS_TODO_ENTITIES`).
Wichtig: Es darf in Tests nie ein echter Netzwerkzugriff passieren (Handler-Default: `pytest.fail`).

Testfälle:
1. Fallback ohne `SUPERVISOR_TOKEN`: `/api/ha/agenda` -> 200 `{available:false, events:[]}`; `/api/ha/todos` -> `{available:false, lists:[]}`.
2. Leere Konfiguration -> `available:false`, kein HA-Request (Handler-Zähler == 0).
3. Agenda: All-Day-Event -> `all_day:true`, kein Zeitanteil; Zeit-Event -> ISO mit Offset; Sortierung All-Day zuerst, dann Zeit.
4. Agenda: HA-Request enthält `start`/`end` als Europe/Berlin-Tagesgrenzen (Winter +01:00 an 2026-11-09; zusätzlicher Test Sommerzeit-Datum, z.B. 2026-07-01 -> +02:00) und `Authorization: Bearer <token>`, KEIN `X-Hass-User-ID`.
5. Agenda: mehrtägiges Event überlappt heute -> enthalten; All-Day-Event von gestern (end exklusiv = heute 00:00) -> NICHT enthalten.
6. Agenda: ein Kalender liefert 500, einer OK -> 200, `available:true`, nur OK-Events.
7. Agenda: alle Kalender werfen `httpx.ConnectError` -> `available:false`, 200.
8. Agenda: ungültiges `today` -> 422.
9. Todos: Mapping von `service_response`, Reihenfolge der Listen gemäß Konfiguration, Namen aus `friendly_name`, nur `needs_action` angefragt.
10. Todos: Fehler einer Liste -> andere bleiben.
11. Toggle: POST completed:true -> HA-Request-Body `{"entity_id","item":uid,"status":"completed"}`; completed:false -> `needs_action`.
12. Toggle: Entity nicht in Allowlist -> 403, HA nicht aufgerufen. Ungültiges Entity-Format -> 422. Fehlendes Feld -> 422.
13. Toggle: HA nicht verfügbar -> 503; HA antwortet 400 -> 502.
14. Auth: alle drei Endpunkte ohne Token (Passwort-Modus via `app_factory(password=...)`) -> 401.
15. Konfig-Parsing: Env-CSV, options.json-Liste, ungültige/duplizierte Einträge werden verworfen (Unit-Test auf `get_configured_entities`).
16. Statische Frontend-Prüfung (Muster `test_app_js_overview_and_escaping`): `app.js` enthält `loadAgenda`, `loadTodos`, `/api/ha/agenda`, `/api/ha/todos`, `escapeHtml`; `index.html` bzw. Template enthält `agenda-slot` und `todos-slot`.
17. `config.yaml` (beide): enthält `calendar_entities`/`todo_entities` in `options` und `schema`; `homeassistant_api: true`.
18. Regression: bestehende `tests/test_overview.py` unverändert grün (`/api/overview` darf keine HA-Felder bekommen); `tests/test_parity.py` grün.
19. Optional: `conftest.APP_MODULES` um `crud.ha`, `schemas.ha`, `crud.overview`, `schemas.overview` ergänzen (rein kosmetisch, `_clear_app_modules` räumt ohnehin per Präfix).

---

## 6. Tasks (klein, testbar, mit Akzeptanzkriterien)

Parität: Alle Dateien werden zuerst in `alltags_manager_dev/` entwickelt, am Ende jedes Tasks 1:1 nach `alltags_manager/` kopiert (`src/` byte-identisch). Jeder Task endet mit `pytest tests/test_parity.py -q` grün.

**T1 – Optionen in config.yaml (beide Add-ons)**
Dateien: `alltags_manager_dev/config.yaml`, `alltags_manager/config.yaml`, Test `tests/test_ha_integration.py` (Fall 17).
AK: Beide Dateien enthalten die zwei Optionen + Schema; `test_parity.py` grün; YAML lädt.

**T2 – Schemas `schemas/ha.py`**
AK: Modelle importierbar; `AgendaResponse(available=False)` hat `events == []`; `TodosResponse` analog; `TodoToggle` validiert Entity-Regex (ungültig -> ValidationError).

**T3 – Konfig-Helper `get_configured_entities`, `get_ha_token`, `get_ha_base_url`**
AK: Testfall 15 grün; Priorität Env > options.json > leer; ungültige Einträge entfernt, Reihenfolge erhalten.

**T4 – Client-Factory `make_client` + Exceptions + Mock-Fixtures in tests**
AK: Test, dass ohne Token `HAUnavailable` entsteht; Fixture `ha_mock` blockiert unerwartete Requests (Handler-Default schlägt fehl).

**T5 – `fetch_agenda` (Zeitraum, Mapping, Sortierung, Overlap-Filter)**
AK: Testfälle 3, 4, 5, 6, 7 grün (direkt auf Modulebene mit asyncio-Run, ohne Route).

**T6 – Route GET /api/ha/agenda**
AK: Testfälle 1, 2, 8, 14 (Agenda) grün; Antwort validiert gegen `AgendaResponse`.

**T7 – `fetch_todos`**
AK: Testfälle 9, 10 grün; Request nutzt `?return_response` und Status-Filter.

**T8 – Route GET /api/ha/todos**
AK: Fallback-Fälle (1, 2 für Todos) + Auth grün.

**T9 – `set_todo_status` + Route POST /api/ha/todos/item**
AK: Testfälle 11, 12, 13, 14 (Toggle) grün; bei 403 kein HA-Call.

**T10 – Frontend-Slots + Lade-/Fehlerlogik (`loadAgenda`/`loadTodos`, leise Ausblendung)**
AK: Testfall 16 (Teil Slots/Funktionen) grün; manuell: Standalone ohne Token -> Heute-Seite unverändert, keine Fehlermeldung, keine roten Konsolen-Errors außer `console.warn`.

**T11 – Rendering Termine (`renderAgenda`) + CSS**
AK: Ganztägig-Badge vs. `HH:MM`; keine Events -> Slot leer; XSS-Test: `<img onerror>` im Titel wird als Text dargestellt (Smoke-Check per statischer Prüfung, dass nur `escapeHtml`-Pfade genutzt werden).

**T12 – Rendering + Abhaken To-dos**
AK: Checkbox sendet POST mit korrekten Feldern; bei Fehler Rücksetzen; Erfolg entfernt Zeile; leere Listen/alle leer -> Slot leer. Manuell gegen echtes HA im Dev-Add-on prüfen (ein Item in `todo.einkaufsliste` abhaken -> in HA erledigt).

**T13 – Parität & Regression final**
AK: `pytest -q` komplett grün (Dev + Prod), `src/` beider Add-ons identisch, Versionsfeld in config.yaml angehoben.

**T14 – Doku**
AK: `docs/architecture.md` um Abschnitt "HA-Integration" (Endpunkte, Optionen, Fallback-Verhalten, Hinweis auf nötige HA-Version >= 2023.7) ergänzen.

---

## 7. Reihenfolge

T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9 -> T10 -> T11 -> T12 -> T13 -> T14

Backend (T1-T9) ist vollständig ohne Frontend testbar und liefert nach T6 bereits einen nutzbaren Agenda-Endpunkt (per curl prüfbar). Frontend (T10-T12) baut darauf auf. Agenda (T5/T6) vor Todos, weil lesend und risikoärmer; Schreibpfad (T9) zuletzt.

## 8. Risiken / offene Punkte

- HA-Version < 2023.7: `get_items` mit `return_response` fehlt -> To-dos erscheinen als nicht verfügbar (graceful, kein Fehler).
- Add-on-Schema für Listen mit `match()` ggf. strenger als erwartet -> Fallback `str?` (Backend validiert ohnehin).
- Latenz: 11 Kalender parallel mit 5 s Timeout; bei Bedarf später 30-60 s In-Memory-Cache (bewusst nicht in v1).
- Standalone-Betrieb: kein Supervisor -> `available:false`; optionaler Zugriff auf eine entfernte HA-Instanz (Long-Lived-Token) ist ausdrücklich nicht Teil von v1.
- Kalender-Rückschreiben (Termine anlegen) ist nicht im Scope.
