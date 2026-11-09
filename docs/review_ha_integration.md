# Review: HA-Integration (Branch develop, uncommitted)

Plan-Referenz: docs/plan_ha_integration.md
Scope: Backend HA-Client über Supervisor-Proxy (httpx), Optionen calendar_entities/todo_entities, erweitertes /api/overview, Fallback mit available:false, Frontend-Sektionen "Termine heute" und "To-dos" mit optimistischem Abhaken und Rückschreiben nach HA, config.yaml-Schema beider Add-ons, 19 geplante Testfälle in tests/test_ha_integration.py.

## Tests

pytest -q gesamt: 155 passed.
Davon tests/test_ha_integration.py: 38 passed (17 Testfunktionen, parametrisiert auf dev und prod).
Warnungen: vorbestehende datetime.utcnow()-Deprecations.

## Befunde

1. MAJOR: Netzfehler beim Abhaken liefert HTTP 500 statt 503.
   crud/ha.py::set_todo_status fängt nur HAUnavailable und HARejected ab. Ein httpx.ConnectError oder httpx.TimeoutException beim client.post läuft unbehandelt durch die Route toggle_ha_todo.
   Reproduziert: Mock mit ConnectError ergibt Status 500.
   Plan-Vertrag (Abschnitt 1.3) verlangt 503.
   Das Frontend fängt jeden Non-OK-Status ab und setzt die Zeile zurück, der Schaden ist also begrenzt. Der Vertragsbruch bleibt bestehen.
   Fix: In set_todo_status den Aufruf in try/except httpx.HTTPError (inkl. Timeout) hüllen und als HAUnavailable werfen. Testfall 13 um einen ConnectError-Fall erweitern.
   Der Test fehlt aktuell, deshalb ist der Bug nicht aufgefallen.

2. MINOR: Testabdeckung weicht vom Plan ab.
   - Fall 13 prüft nur "kein Token -> 503" und "HA 400 -> 502". Netzfehler -> 503 fehlt (siehe Befund 1).
   - Fall 16 / T11 (XSS-Prüfung): Der Test prüft nur, dass Tokens wie escapeHtml im JS vorkommen. Er prüft nicht, dass alle Felder tatsächlich escaped werden. Schwach, der Code selbst ist aber sauber.
   - Nicht geprüft, ob Fall 9 (nur needs_action angefragt) und Fall 11 (completed:false -> needs_action) wirklich assertiert werden. Bitte gegenchecken.

3. MINOR: Frontend, Fehlerpfad beim Abhaken mit 401.
   handleHaTodoToggle ruft bei 401 handleUnauthorized() auf. Die Checkbox bleibt dabei disabled und die Zeile is-completed. Vermutlich harmlos, da die Session ohnehin abgelaufen ist. Eine Zeile Aufräumen würde es sauber machen.

4. MINOR: set_todo_status prüft die Allowlist nicht selbst.
   Die Prüfung liegt nur in der Route. Aktuell korrekt, aber Defense-in-Depth fehlt. Wird die Funktion später anderswo aufgerufen, ist sie offen.

5. MINOR: Zwei HTTP-Requests pro Kalender (/states/{id} für den Namen, danach /calendars/{id}).
   Bei 11 Kalendern verdoppelt das die Latenz. Der Plan akzeptiert das bewusst. Alternative: Namen aus GET /calendars (1 Request) ziehen oder cachen.

6. OFFEN (nicht gelöst): Schema-Syntax - "match(^calendar\\.[a-z0-9_]+$)?" für Listen ist nicht gegen einen echten Supervisor/HA-Validator verifiziert. Kein HA-Zugriff im Review.
   Vor dem Release im Dev-Add-on installieren und Optionen setzen. Falls der Validator ablehnt, Fallback "str?" laut Plan.

## Geprüft und in Ordnung

1. Auth/Token: SUPERVISOR_TOKEN wird nur im Authorization-Header gesetzt. Logs enthalten nur Entity-ID und Exception-Klasse. Fehlermeldungen (502) enthalten nur den Status. Kein Token-Leak gefunden. Kein X-Hass-User-ID-Header.
2. XSS: Alle nutzergesteuerten Felder (title, calendar_name, list.name, summary, entity_id, uid in data-Attributen) laufen durch escapeHtml. Die Uhrzeit kommt aus toLocaleTimeString. Kein Befund.
3. Fallback: Kein Token, leere Konfiguration und alle Kalender/Listen fehlgeschlagen liefern HTTP 200 mit available:false. Einzelne Fehler werden übersprungen. Das Frontend blendet die Slots lautlos aus. Die Route fängt HAUnavailable zusätzlich ab.
4. Parität: alltags_manager/src und alltags_manager_dev/src sind identisch (ohne __pycache__). Prod-Version blieb 1.0.1, wie im Plan gefordert. test_parity.py grün.
5. config.yaml: Beide Dateien sind identisch bis auf die erlaubten Felder. Optionen stehen in options und schema. Regex-Escaping ist in YAML korrekt. Validator-Verträglichkeit siehe Befund 6.
6. Zeitraum: Winter- (+01:00) und Sommerzeit-Grenzen (+02:00) sind getestet.

## Empfehlung

- Befund 1 vor dem Commit fixen und Testfall 13 um Netzfehler erweitern.
- Befunde 2 bis 5 können als Follow-up laufen.
- Befund 6 vor dem Release im Dev-Add-on prüfen.
- Manueller Browser-Test der Heute-Seite (mit und ohne HA) steht noch aus.
