# Research: UI/UX & Architektur Best Practices

Dieses Dokument fasst die Best Practices für das gewählte Design (Glassmorphism, Mobile-First Bottom Tab Bar) und die Backend-Architektur (FastAPI + SQLite) für das Alltags-Manager Dashboard zusammen.

## 1. UI/UX Best Practices

### 1.1 Glassmorphism & Premium Look
Das Designziel ist ein eleganter Premium Look mit einem dunklen Hintergrund (`#070708`) und goldenen Akzenten (`#cba970`).

*   **Layering & Tiefe:** Glassmorphismus lebt von der Illusion schwebender Elemente über einem Hintergrund. Subtile Schatten (`box-shadow`) helfen, die Glasschichten vom dunklen Hintergrund abzuheben.
*   **Backdrop-Filter (Hintergrundunschärfe):** Die Kernkomponente. Eine gut abgestimmte Unschärfe (`backdrop-filter: blur()`) sorgt für den Milchglaseffekt.
*   **Transluzente Ränder:** Dünne, halbtransparente Ränder (z.B. `border: 1px solid rgba(255, 255, 255, 0.1)`) definieren die Kanten der "Glasscheiben" und imitieren die Lichtbrechung.
*   **Kontrast & Lesbarkeit:** Auf dem dunklen Hintergrund (#070708) muss auf ausreichend Kontrast für Text geachtet werden. Weißer oder hellgrauer Text auf dunklem Glas funktioniert am besten.
*   **Akzentfarbe (#cba970):** Kann gezielt für aktive Zustände, wichtige Buttons, dezente Verläufe im Hintergrund (die durch das Glas scheinen) oder Icons genutzt werden.
*   **Performance:** Zu viele überlappende Backdrop-Filter können besonders auf mobilen Geräten die Rendering-Performance beeinträchtigen. Daher sollten sie bewusst und sparsam eingesetzt werden.

### 1.2 Mobile-First Bottom Tab Bar
Eine Bottom Tab Bar ist essenziell für die mobile Navigation, da sie leicht mit dem Daumen erreichbar ist.

*   **Daumenreichweite (Thumb Zone):** Die Platzierung am unteren Bildschirmrand ist ergonomisch ideal für die Einhandbedienung.
*   **Anzahl der Tabs:** 3 bis maximal 5 Tabs verwenden, um Überladung und eine zu dichte Darstellung zu vermeiden.
*   **Klares Feedback:** Der aktuell ausgewählte Tab muss visuell deutlich hervorgehoben sein (z.B. farbiges Icon in `#cba970`, fetterer Text oder ein kleiner Punkt/Indikator über dem Icon).
*   **Labels & Icons:** Eindeutige Icons verwenden. Textlabels sollten kurz sein. Eine Kombination aus beidem erhöht die Verständlichkeit erheblich.
*   **Safe Areas berücksichtigen:** Auf Geräten ohne physischen Homebutton (z.B. moderne iPhones) muss Padding am unteren Rand hinzugefügt werden, um Konflikte mit der System-Navigation zu vermeiden (`padding-bottom: env(safe-area-inset-bottom)`).
*   **Glas-Effekt für die Tab Bar:** Die Tab Bar selbst kann im Glassmorphism-Stil gehalten sein, um leicht in den Hintergrund überzugehen, sollte aber durch einen subtilen Rand (`border-top`) vom restlichen Inhalt abgegrenzt werden.

### 1.3 Typografie
*   **Outfit:** Ideal für Überschriften (Headers) und markante UI-Texte. Die Schriftart hat eine geometrische, moderne Anmutung und unterstreicht den angestrebten Premium-Look.
*   **Plus Jakarta Sans:** Sehr gut geeignet für Fließtext, UI-Labels, kleine Hinweise und Daten, da sie auf Bildschirmen exzellent lesbar ist und saubere, klare Linien aufweist.

---

## 2. Backend Best Practices: FastAPI & SQLite

### 2.1 Projektstruktur
Eine saubere Trennung der Verantwortlichkeiten (Separation of Concerns) ist für die Wartbarkeit und Skalierbarkeit essenziell.

Typische, bewährte Ordnerstruktur:
```text
project_root/
├── main.py              # Einstiegspunkt der FastAPI-App (uvicorn)
├── core/                # Globale App-Konfiguration, Sicherheit, Settings (z.B. JWT)
│   ├── config.py
│   └── security.py
├── api/                 # API-Router und Endpunkte (Controller)
│   ├── dependencies.py  # Dependency Injection (z.B. get_db)
│   └── v1/
│       ├── endpoints/   # Hier liegen die eigentlichen Routen-Definitionen
│       └── api.py       # Zusammenfassung (include_router) der v1-Router
├── db/                  # Datenbank-Setup, Engine und Session
│   └── database.py
├── models/              # SQLAlchemy (ORM) Datenbankmodelle (Datenbank-Schema)
├── schemas/             # Pydantic Modelle (Request/Response Validierung & Serialisierung)
└── crud/                # Datenbank-Operationen (Create, Read, Update, Delete)
```

### 2.2 Best Practices für FastAPI mit SQLite
*   **Thread-Sicherheit deaktivieren:** SQLite erlaubt standardmäßig nicht, dass eine Verbindung über mehrere Threads geteilt wird. Da FastAPI in einem multithreaded (oder asynchronen) Umfeld läuft, muss dies bei der SQLAlchemy-Engine explizit deaktiviert werden:
    `connect_args={"check_same_thread": False}`.
*   **Asynchrone DB-Zugriffe (Optional aber Empfohlen):** Für maximale Performance bei I/O-lastigen Aufgaben empfiehlt sich die Nutzung von `aiosqlite` anstelle der synchronen Standardbibliothek, insbesondere in Kombination mit `async def` FastAPI-Endpunkten.
*   **Dependency Injection für Sessions:** Datenbank-Sessions sollten über FastAPIs `Depends` an die Endpunkte übergeben werden. Ein `get_db` Generator stellt sicher, dass Verbindungen pro Request geöffnet und am Ende (im `finally`-Block) sauber wieder geschlossen werden.
*   **Pydantic vs. SQLAlchemy strikt trennen:**
    *   **SQLAlchemy (`models/`):** Repräsentiert die Tabellen in der SQLite-Datenbank.
    *   **Pydantic (`schemas/`):** Validiert ein- und ausgehende JSON-Daten.
    *   Pydantics Konfiguration `model_config = ConfigDict(from_attributes=True)` (ehemals `orm_mode=True`) ermöglicht die nahtlose Konvertierung von SQLAlchemy-Objekten in JSON-Responses.
*   **Datenbank-Migrationen:** Auch wenn SQLite "nur" als Datei vorliegt, sollten Schema-Änderungen von Beginn an über ein Migrationstool wie **Alembic** versioniert und verwaltet werden, um Updates im Betrieb reibungslos durchführen zu können.
