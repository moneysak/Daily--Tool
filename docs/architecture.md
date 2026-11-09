# Alltags-Manager - Architektur

## Frontend
*   Technologie: HTML, CSS, Vanilla JavaScript (iterativer Frontend-First Ansatz).
*   Hosting: Home Assistant Ingress oder Cloudflare Tunnel.

## Backend
*   Technologie: Python
*   Datenbank: SQLite
*   Speicherort: `/data/alltags_manager.db` (innerhalb des Hermes HA Add-ons)

## Komponenten-Analyse (Gemeldete Probleme)

1.  **Hermes Chat**
    *   *Frontend:* Chat-UI mit Nachrichtenverlauf (User/Hermes).
    *   *Backend/Integration:* API-Schnittstelle zur Hermes Agent Instanz (lokal oder via WebSocket), um natürliche Sprachbefehle direkt aus der App an Hermes zu senden.
2.  **Aufgaben (Tasks)**
    *   *Frontend:* Listenansicht (CRUD-Operationen) mit Checkboxen, Fälligkeitsdaten und Prioritäten.
    *   *Backend:* SQLite-Tabelle `tasks` (id, title, description, due_date, status, priority). REST-Endpunkte für Verwaltung.
3.  **Einkaufsliste**
    *   *Frontend:* Spezifische Listenansicht für Artikel. Schnelleingabe.
    *   *Backend:* SQLite-Tabelle `shopping_list` (id, item_name, quantity, category, checked). Optional: Synchronisation mit Home Assistant Todo-Listen.
4.  **Routinen**
    *   *Frontend:* Ansicht für wiederkehrende Abläufe (z.B. Morgenroutine).
    *   *Backend:* SQLite-Tabelle `routines` und `routine_steps`. Logik zur automatischen Generierung von täglichen Instanzen dieser Routinen basierend auf einem Cron-ähnlichen Zeitplan.

## HA-Integration (Kalender + To-do-Listen)

Die "Heute"-Seite enthält zwei optionale Abschnitte: **Termine heute** (HA-Kalender)
und **To-dos** (HA-To-do-Listen, abhakbar mit Rückschreiben nach HA). Ist HA nicht
konfiguriert oder nicht erreichbar, werden beide Abschnitte lautlos ausgeblendet.

*   **Backend:** Modul `crud/ha.py` kapselt einen `httpx.AsyncClient` auf den
    Supervisor-Proxy `http://supervisor/core/api` (Token aus `SUPERVISOR_TOKEN`,
    Timeout 5 s). Modelle in `schemas/ha.py`. Routen sind `async def`.
*   **Endpunkte** (alle `Depends(require_auth)`):
    *   `GET /api/ha/agenda?today=YYYY-MM-DD` – Termine aller konfigurierten Kalender;
        All-Day zuerst, dann nach Startzeit; mehrtägige Overlaps inklusive
        (All-Day-`end` ist bei HA exklusiv).
    *   `GET /api/ha/todos` – offene (`needs_action`) Items je Liste, Reihenfolge
        wie in der Konfiguration.
    *   `POST /api/ha/todos/item` – Body `{entity_id, uid, completed}`; hakt ein
        Item ab bzw. setzt es zurück (`completed:false` -> `needs_action`).
*   **Optionen** (beide `config.yaml`, identisch):
    `calendar_entities: []` und `todo_entities: []` (jeweils Liste von
    Entity-IDs, Schema mit `match(^calendar\.[a-z0-9_]+$)?` bzw. `todo`-Äquivalent).
    Ein Env-Override (`ALLTAGS_CALENDAR_ENTITIES` / `ALLTAGS_TODO_ENTITIES`,
    CSV) hat Vorrang vor `/data/options.json`.
*   **Allowlist:** Der Supervisor-Token hat Zugriff auf alle Entities. Daher prüft
    das Backend jeden Zugriff gegen die konfigurierte Liste (Schreiben: 403 außerhalb
    der Liste). Es gibt keine Discovery-Endpunkte.
*   **Fallback:** Fehlt das Token, ist die Liste leer oder schlägt HA fehl, liefern
    die GET-Endpunkte HTTP 200 mit `available: false` und leeren Listen. Einzelne
    fehlschlagende Kalender/Listen werden übersprungen. Schreibfehler: 503 (nicht
    verfügbar) bzw. 502 (von HA abgelehnt).
*   **Voraussetzung:** HA >= 2023.7 (Service-Responses für `todo/get_items`).
    Ohne diese Version erscheinen To-dos als nicht verfügbar (graceful).

## Workflow
Gemäß Systemvorgaben wird Code für spezifische Module nicht in `src/` geschrieben (sondern via Subagenten delegiert). Die Review-Ergebnisse werden in `docs/review.md` dokumentiert.