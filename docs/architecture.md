# Systemarchitektur: Alltags-Manager Dashboard

## 1. Überblick
Das Alltags-Manager Dashboard ist eine App zur täglichen Organisation, die einen Premium-Look (Hintergrund: `#070708`, Akzente: `#cba970`, Glassmorphism) bietet. Der Fokus liegt auf einer mobilen, Frontend-zentrierten Entwicklung mit einer Backend-API für die Persistenz.

## 2. Technologie-Stack
*   **Frontend:** HTML5, CSS3 (Glassmorphism, CSS-Variablen), JavaScript (Vanilla oder leichtgewichtiges Framework für PWA/SPA). Fonts: Outfit (Headings) & Plus Jakarta Sans (Body).
*   **Backend:** Python 3 mit FastAPI.
*   **Datenbank:** SQLite (via SQLAlchemy).
*   **Deployment (Home Assistant Add-on):** 
    * Bereitstellung als lokales Home Assistant Add-on basierend auf dem `ghcr.io/hassio-addons/alpine-base` Image.
    * Prozessmanagement via **s6-overlay**.
    * Persistenz der SQLite-Datenbank zwingend im `/data/`-Verzeichnis des Containers.
    * Frontend und API werden nahtlos via **HA Ingress** eingebunden. Python-Abhängigkeiten werden sauber isoliert in einer `venv` installiert.

## 3. Architektur
Die Architektur folgt dem Client-Server-Modell mit einer klaren Trennung von Frontend und Backend.

### 3.1 Frontend
*   **Mobile-First Design:** Eine Bottom Tab Bar bietet Zugriff auf die Hauptbereiche: Aufgaben, Einkaufslisten, Routinen und Chat.
*   **Styling:**
    *   Dark Mode Basis (`#070708`).
    *   Glassmorphism-Effekte für Container und Overlays (`backdrop-filter: blur()`).
    *   Semantische Typografie (Outfit für Header, Plus Jakarta Sans für Lesbarkeit).

### 3.2 Backend (FastAPI)
Das Backend folgt einer mehrschichtigen Architektur (Layered Architecture), um Controller (API-Routen), Geschäftslogik und Datenzugriff zu trennen.

**Verzeichnisstruktur (`src/backend/`):**
```text
src/backend/
├── main.py              # Uvicorn/FastAPI Entrypoint
├── api/                 # API-Endpunkte
├── db/                  # SQLite Datenbank-Setup (engine, session)
├── models/              # SQLAlchemy Datenbankmodelle
├── schemas/             # Pydantic Modelle für In/Out Validierung
└── crud/                # Create, Read, Update, Delete Operationen
```

**Spezifika für SQLite & FastAPI:**
*   SQLAlchemy Engine erfordert `connect_args={"check_same_thread": False}`.
*   Dependency Injection via `yield` in einer `get_db()` Funktion stellt sicher, dass Sessions pro Request geöffnet und geschlossen werden.

## 4. Datenmodell (Draft)
*   **Aufgaben (Tasks):** ID, Titel, Status (Offen, Erledigt), Fälligkeit, Erstellt am.
*   **Einkaufsliste (ShoppingList):** ID, Artikel, Menge, Status (Gekauft).
*   **Routinen (Routines):** ID, Name, Frequenz, Letzte Ausführung.
*   **Chat (Hermes):** (Schnittstelle zur externen Kommunikation/Lagerung von Chat-Historien, je nach Integration).

## 5. Workflow
1.  **Frontend-First:** Basis-HTML/CSS/JS Strukturen entwickeln, um das UI/UX (Glassmorphism, Navigation) abzusichern.
2.  **Mock-API:** Erste Interaktionen mit Dummy-Daten implementieren.
3.  **Backend-Integration:** FastAPI aufsetzen und SQLite-Modelle definieren.
4.  **Verbindung:** Frontend-Aufrufe an das reale Backend anbinden.
