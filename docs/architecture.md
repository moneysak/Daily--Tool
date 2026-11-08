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

## Workflow
Gemäß Systemvorgaben wird Code für spezifische Module nicht in `src/` geschrieben (sondern via Subagenten delegiert). Die Review-Ergebnisse werden in `docs/review.md` dokumentiert.