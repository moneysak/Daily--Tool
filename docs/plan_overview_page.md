# Plan: "Heute"-Übersichtsseite (/api/overview)

Branch: develop. Betroffen: alltags_manager_dev/src (Arbeitskopie) und alltags_manager/src (muss byte-identisch sein, siehe tests/test_parity.py).
Status: nur Plan, kein Code.

## 0. Ist-Analyse (Befunde, die den Plan bestimmen)

- Models (backend/models/task.py): Task(id,title,description,completed,created_at), ShoppingItem(..., checked), Routine(title,description,frequency:str,active,completed_today:bool,created_at).
- Es gibt KEINE Migration. main.py nutzt nur Base.metadata.create_all(). Das legt keine neuen Spalten in bestehenden SQLite-Tabellen an -> bei bestehenden Installationen (/data/alltags_manager.db) würde jede neue Spalte zu "no such column"-Fehlern führen. => Mini-Migration ist Pflicht (Task D3).
- completed_today wird nirgends zurückgesetzt (kein Scheduler). Ohne Fix wäre "heute erledigt" ab Tag 2 falsch. => Datum statt Bool als Quelle der Wahrheit (D2).
- Kein User-Name vorhanden. auth_status liefert nur "default"/"authenticated"/HA-User-ID. => neue Add-on-Option user_name (D5).
- Frontend: Vanilla JS, contentMap (HTML-Templates pro Tab), renderActiveTab() dispatcht nach data-target, Tabs per Klick (kein Hash-Routing), Initial-Tab = Element mit Klasse "active" in index.html. Alle Fetches via apiBaseUrl + getAuthHeaders() + handleUnauthorized() bei 401. escapeHtml() existiert und ist Pflicht für Titel.
- Tests: tests/conftest.py stellt Fixture `client` (parametrisiert über dev+prod, offener Modus, tmp DB) bereit. Auth-Tests/Parity-Test existieren.
- Zeitzone: HA-Add-on-Container laufen typischerweise in UTC; "heute" und Begrüßung dürfen nicht blind datetime.utcnow() nutzen (D6).

## 1. Datenmodell-Änderungen

D1 Task
- due_date: Date, nullable, default None. Grund: Aggregation "heute/überfällig/irgendwann".
- completed_at: DateTime, nullable. Wird in crud.update_task gesetzt, wenn completed False->True (auf now), und auf None, wenn True->False. Grund: "X von Y erledigt" braucht "heute erledigt"; nur completed-Bool reicht nicht (alte erledigte Tasks würden ewig mitzählen). Alt-Daten mit completed=True und completed_at=NULL zählen NICHT zum Tagesfortschritt.
- Schemas: TaskBase/Create/Update/Task um due_date: Optional[date] = None erweitern; Task (Response) zusätzlich completed_at: Optional[datetime]. Update nutzt weiterhin model_dump(exclude_unset=True), damit due_date explizit auf null gesetzt werden kann (Datum entfernen) -> bleibt rückwärtskompatibel.

D2 Routine
- weekdays: String, nullable. CSV der Wochentage nach Python-Konvention Mo=0..So=6, z.B. "0,2,4". Grund: SQLite-freundlich, kein JSON-Typ nötig. In Schema als Optional[list[int]] mit Validator (0..6, dedupliziert, sortiert); Konvertierung CSV<->list im CRUD/Schema (Task B2).
- last_completed_on: Date, nullable. Quelle der Wahrheit für "heute erledigt".
- completed_today bleibt als Spalte/Feld erhalten (API-Kompatibilität mit bestehendem Frontend), wird aber effektiv berechnet: effective = (last_completed_on == today). Schreiben von completed_today=True setzt last_completed_on=today; =False setzt last_completed_on=None. Lesen (get_routines und overview) liefert den berechneten Wert, nie den veralteten Spaltenwert. => kein Cron/Reset nötig ("lazy reset").
- frequency bleibt String: erlaubt "daily" | "weekly". Validierung im Schema (Literal), unbekannte Alt-Werte werden beim Lesen wie "daily" behandelt (defensiv), nicht per Fehler.
- Fälligkeitsregel is_due(routine, today):
  - active == False -> nie fällig
  - daily -> immer fällig
  - weekly mit weekdays -> fällig, wenn today.weekday() in weekdays
  - weekly ohne weekdays (Alt-Daten) -> fällig am Wochentag von created_at (deterministischer Fallback, keine Datenmigration der Werte nötig)
- next_due (Optional[date]) NICHT persistieren: wird bei Bedarf berechnet (Hilfsfunktion), da abgeleitet. Im Overview optional nicht ausgeliefert (YAGNI); nur falls später "Demnächst"-Block kommt.

D3 Mini-Migration (db/database.py)
- Funktion ensure_schema(engine) die nach create_all läuft: per PRAGMA table_info(<tabelle>) fehlende Spalten ermitteln und per ALTER TABLE ... ADD COLUMN ergänzen (tasks.due_date, tasks.completed_at, routines.weekdays, routines.last_completed_on). Idempotent. Kein Alembic (YAGNI für SQLite-Single-User).
- Aufruf in main.py direkt nach create_all.

D4 ShoppingItem: keine Änderung. "ungeprüft" = checked == False (UI-Begriff "abgehakt" ist checked; Zähler = nicht abgehakte Artikel).

D5 Add-on-Option user_name
- config.yaml in BEIDEN Add-ons: options.user_name: "" und schema.user_name: "str?" (config.yaml darf sich laut Parity-Test nur in erlaubten Feldern unterscheiden, daher identisch ändern; Versionen separat nur in Dev bumpen, z.B. 1.0.3-dev).
- Lesen: Env USER_NAME hat Vorrang, dann options.json (Pfad via ALLTAGS_OPTIONS_PATH, gleiche Logik wie get_configured_password in auth.py). Leer/nur Whitespace -> None. Länge begrenzen (z.B. 50) und nur als JSON ausliefern (Frontend escaped).
- Keine Änderung am Auth-Verhalten.

D6 Zeitbezug
- "heute" = lokales Datum. Endpoint akzeptiert optionalen Query-Param today=YYYY-MM-DD (ungültig -> 422). Frontend sendet sein lokales Datum. Ohne Param: Server nutzt zoneinfo mit Env TZ (HA setzt TZ), Fallback UTC. Der Param macht Tests deterministisch.
- Begrüßung wird im Frontend aus der lokalen Uhrzeit berechnet (Backend bleibt zeitlos): 05-10 Guten Morgen, 11-17 Guten Tag, sonst Guten Abend.

## 2. API-Vertrag: GET /api/overview?today=YYYY-MM-DD (require_auth)

Response (Pydantic-Schema Overview in schemas/overview.py):
{
  "today": "2026-11-09",
  "user_name": "Daniel" | null,
  "tasks": {
    "due_today":  [Task...],   // open, due_date == today
    "overdue":    [Task...],   // open, due_date < today, älteste zuerst; jedes Item mit is_overdue=true
    "someday":    [Task...],   // open, due_date IS NULL
    "done_today": [Task...]    // completed_at-Datum == today
  },
  "routines": [ {id,title,description,frequency,weekdays,completed_today} ... ],  // nur aktiv + heute fällig
  "shopping": { "open_count": int },
  "progress": { "done": int, "total": int, "percent": int }   // total>0 sonst percent 0
}
Fortschritts-Definition: total = len(due_today)+len(overdue)+len(done_today)+len(routines_due); done = len(done_today)+Anzahl routines_due mit completed_today. "Irgendwann"-Tasks zählen nicht zum total (sonst wäre 100% nie erreichbar), ihre heute erledigten zählen via done_today mit. Offener Punkt: ein heute erledigter Irgendwann-Task erhöht done UND total (bewusst, belohnend, einfach).
Fehlerfälle: 401 ohne Auth wie alle anderen Endpunkte; leere DB -> alle Listen leer, total 0, percent 0 (kein Division-by-zero).

## 3. Backend-Tasks

B1 Modelle + Schemas erweitern (D1, D2) in models/task.py und schemas/task.py. Akzeptanz: POST /tasks/ mit due_date "2026-11-10" liefert es zurück; ohne due_date weiterhin 200 mit null; Routine mit weekdays [0,2] round-trippt; weekdays [7] -> 422; frequency "monthly" -> 422.
B2 CRUD-Anpassungen (crud/task.py): CSV<->Liste für weekdays; update_task setzt/leert completed_at; update_routine/create_routine pflegen last_completed_on; get_routines gibt effektives completed_today. Akzeptanz: Task erledigt -> completed_at gesetzt; wieder geöffnet -> None; Routine completed_today=True gesetzt, dann mit today+1 gelesen -> False.
B3 ensure_schema (D3) + Aufruf in main.py. Akzeptanz: alte DB (nur Alt-Spalten, mit Datensätzen) wird beim Start migriert, Daten bleiben erhalten; zweimaliger Start wirft nichts.
B4 Aggregationslogik in NEUER Datei backend/crud/overview.py (bewusst unter dem Paket crud/, damit conftest-Modul-Reset ohne Änderung greift). Reine Funktionen: is_routine_due(routine, today), build_overview(db, today, user_name) -> dict. Nur 3 Queries (tasks, routines, count shopping). Kein HTTP-Wissen. Akzeptanz: siehe Tests T2.
B5 Settings-Helper für user_name (D5), möglichst Wiederverwendung der options.json-Leselogik aus auth.py; Auth-Tests dürfen nicht brechen. Akzeptanz: Env/Options/leer wie in D5.
B6 Endpoint GET /api/overview in main.py (dünn: Param parsen, build_overview, response_model=schemas.Overview). WICHTIG: Route muss vor app.mount("/", StaticFiles) stehen (Mount am Dateiende, daher einfach oberhalb des Index-Handlers/bei den anderen API-Routen). Akzeptanz: 200 + Schema im offenen Modus, 401 im Passwort-Modus ohne Token, 422 bei today=abc.
B7 config.yaml (beide) um user_name erweitern; nur Dev-Version bumpen. Akzeptanz: test_config_only_differs_in_allowed_fields grün.

## 4. Frontend-Tasks (alltags_manager_dev/src/frontend, danach spiegeln)

F1 index.html: neuer erster Tab <a data-target="today" class="tab-item active"> (Icon z.B. ☀, Label "Heute"); "active" von Aufgaben entfernen; Aufgaben wird zweiter Tab. Platzhalter-Text "Willkommen" im main-content entfällt/bleibt irrelevant, da renderActiveTab ihn ersetzt. Bottom-Bar hat dann 5 Tabs: Breite/Label-Größe in CSS prüfen (Mobile 360px).
F2 app.js: contentMap['today'] Template (Header mit Begrüßung + Datum, Fortschrittskarte, Abschnitte Überfällig / Heute / Routinen / Irgendwann, Einkaufs-Karte, Leerzustand). renderActiveTab: Zweig für 'today' -> loadOverview() + attachTodayListeners().
F3 loadOverview(): fetch `${apiBaseUrl}/api/overview?today=<lokales Datum YYYY-MM-DD>`, 401 -> handleUnauthorized(), sonst Fehlerbanner statt leerer Seite. Rendering ausschließlich mit escapeHtml() für title/description/user_name (XSS, vgl. tests/test_index_xss.py).
F4 Begrüßung: Funktion greetingFor(hour, name) -> "Guten Morgen, Daniel" bzw. ohne Namen ohne Komma. Rein, separat testbar/lesbar.
F5 Interaktion: Checkbox bei Aufgaben -> PUT /tasks/{id} {completed:true}; bei Routinen -> PUT /api/routines/{id} {completed_today:true/false}; danach loadOverview() neu (Single Source of Truth, kein lokales Fortschreiben). Erledigte Tasks (done_today) erscheinen durchgestrichen am Ende ihres Abschnitts.
F6 Einkaufs-Karte: Text "Heute einkaufen: X Artikel" (X==1 -> "1 Artikel", X==0 -> "Nichts zu kaufen 🎉"); Klick programmatisch auf den Shopping-Tab: Tab-Klassen umschalten + renderActiveTab() (gleiche Logik wie der Tab-Click-Handler; ggf. zu Hilfsfunktion activateTab(name) refactoren, ohne Verhalten zu ändern).
F7 Aufgaben-Tab: Eingabefeld type=date für due_date beim Anlegen, Fälligkeits-Badge in der Liste (rot, wenn überfällig). Routinen-Tab: Auswahl frequency daily/weekly + Wochentags-Chips (nur bei weekly sichtbar). Ohne F7 wären die neuen Daten nicht erfassbar -> Pflicht, aber nach Backend umsetzen.
F8 style.css: Fortschrittsbalken (Track + Fill mit transition, Breite per inline style width:X% aus Zahl), Klassen .overdue (roter Akzent, z.B. var(--danger) oder fester Rotton passend zum Glass-Design), .section-title, .badge, .shopping-card (klickbar, cursor/focus-Stil), .greeting. Zugänglichkeit: Fortschritt mit role="progressbar" + aria-valuenow; Karte als <button> oder role="link"+Tastatur. Rot nicht als einziges Signal (zusätzlich Text "überfällig seit N Tagen" oder Icon).

## 5. Test-Tasks (pytest, tests/test_overview.py; parametrisiert über Fixture `client`, deckt Dev+Prod ab)

T1 Modell/Schema: Task mit/ohne due_date; completed_at-Lebenszyklus; Routine-Validierung (weekdays/frequency).
T2 Aggregation (mit festem ?today=2026-11-09, ein Montag): Task due heute -> due_today; due gestern -> overdue; kein Datum -> someday; Zukunft -> nirgends; erledigt heute -> done_today; erledigt gestern -> nirgends. Routinen: daily fällig; weekly [0] fällig am Montag, weekly [1] nicht; inaktive nie; weekly ohne weekdays -> Wochentag von created_at; completed_today nur wenn last_completed_on == today (Folgetag wieder False).
T3 Fortschritt: Beispielrechnung total/done/percent; leere DB -> 0/0/0.
T4 Shopping: 3 Artikel, 1 checked -> open_count 2.
T5 Auth: Passwort-Modus ohne Token -> 401; mit Token -> 200 (Muster aus tests/test_auth_endpoints.py via app_factory).
T6 user_name: gesetzt via Env -> im Response; leer -> null.
T7 Migration: SQLite-Datei mit Alt-Schema anlegen, App laden, /tasks/ und /api/overview funktionieren, Alt-Daten erhalten.
T8 Rückwärtskompatibilität: bestehende smoke-/auth-Tests unverändert grün; PUT /api/routines/{id} mit nur completed_today funktioniert wie zuvor.
T9 Frontend-Smoke (statisch, wie test_index_xss.py): index.html enthält data-target="today" als ersten Tab mit "active"; app.js enthält '/api/overview' und nutzt escapeHtml in der Today-Renderfunktion (einfacher String-/Regex-Check; kein Browser-Test).
T10 Parity: kein neuer Test nötig; tests/test_parity.py muss nach Sync grün sein (siehe Abschnitt 7).

## 6. Task-Reihenfolge (jeweils eigener Commit auf develop, nach jedem Schritt: pytest -q)

1. T-Rot: Tests T1/T2 zuerst als fehlschlagende Tests (TDD) - optional, aber empfohlen.
2. B3 + B1 + B2 (Daten & Migration), T1/T7/T8 grün.
3. B4 + B5 + B6 (Aggregation, Settings, Endpoint), T2-T6 grün.
4. B7 (config.yaml beide, Dev-Version bump).
5. SYNC-Punkt A: Backend dev -> prod spiegeln, Parity grün.
6. F1, F2, F3, F4, F8 (Heute-Tab lesend, inkl. Style), dann F5, F6 (Interaktion), danach F7 (Erfassung im Aufgaben-/Routinen-Tab). T9 ergänzen.
7. SYNC-Punkt B: Frontend dev -> prod spiegeln, Parity + komplette Suite grün.
8. Manuelle Abnahme im Dev-Add-on (siehe Abschnitt 8), dann erst PR develop -> main (main bis dahin unberührt).

## 7. Parity-Vorgehen

- Entwickelt wird ausschließlich unter alltags_manager_dev/src; danach Spiegeln nach alltags_manager/src (rsync --exclude __pycache__ oder git-basiert). Parity-Test vergleicht SHA-256 jeder Datei unter src/ (außer __pycache__/.pyc): neue Dateien (crud/overview.py, schemas/overview.py) müssen in beiden Add-ons existieren.
- config.yaml: neue Option user_name in beiden identisch; nur name/description/version/slug/image/panel_*/ports dürfen differieren (ALLOWED_CONFIG_DIFFERENCES). Dockerfile/requirements unverändert (keine neue Abhängigkeit; zoneinfo ist stdlib, ggf. tzdata nur prüfen, falls Alpine-Image keine Zonen hat -> sonst Fallback UTC statt Abhängigkeit).
- Hinweis: Dev und Prod laufen mit getrennten /data-DBs; die Migration D3 läuft daher bei beiden unabhängig beim ersten Start.

## 8. Manuelle Abnahme (Checkliste)

- Frische Installation + bestehende DB-Kopie: App startet, Aufgaben/Einkauf/Routinen funktionieren wie vorher.
- Heute-Tab ist beim Öffnen aktiv; Aufgaben-Tab ist zweiter Tab und unverändert nutzbar.
- Aufgabe mit gestern-Datum erscheint rot unter "Überfällig"; mit heute unter "Heute"; ohne Datum unter "Irgendwann".
- Routine weekly nur am gewählten Wochentag sichtbar; Abhaken erhöht Fortschritt; nach Mitternacht (oder today-Param) wieder offen.
- Einkaufs-Karte zeigt korrekte Zahl und springt zum Einkauf-Tab.
- Begrüßung passt zur Tageszeit; mit user_name gesetzt erscheint der Name, ohne nicht.
- Läuft über Ingress (apiBaseUrl-Pfad) und Standalone mit Passwort.

## 9. Risiken / offene Punkte

- ALTER TABLE-Migration ist handgebaut: bei weiteren Features ggf. Alembic erwägen (nicht jetzt).
- Overdue-Routinen gibt es bewusst nicht (verpasste Routine verfällt am Tagesende).
- Zeitzone im Container: Wenn TZ nicht gesetzt, nutzt Server UTC; Frontend-today-Param umgeht das. Server-Fallback nur für API-Direktaufrufe (z.B. Hermes).
- Die Hermes-Chat-Schnittstelle kennt die neuen Felder nicht; falls Hermes Aufgaben anlegt, ist due_date einfach null (landet unter "Irgendwann").
