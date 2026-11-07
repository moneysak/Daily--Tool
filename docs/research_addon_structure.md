# Recherche: Home Assistant Add-on Struktur für FastAPI

Dieses Dokument fasst die Best Practices und minimalen Anforderungen zusammen, um eine FastAPI Python-Anwendung als lokales Home Assistant (HA) Add-on bereitzustellen.

## 1. Minimale Dateistruktur
Ein HA Add-on erfordert bestimmte Metadaten und Build-Anweisungen. Eine saubere Struktur trennt den Code der App von den Add-on-Konfigurationen:

```text
addon/
├── config.yaml          # Metadaten des Add-ons (Name, Version, Ports, Ingress)
├── Dockerfile           # Bauanleitung für das Container-Image
├── rootfs/              # Dateisystem-Overlay (für s6-overlay und HA-spezifisches)
│   └── etc/
│       └── s6-overlay/
│           └── s6-rc.d/
│               ├── fastapi/
│               │   ├── run        # Start-Skript für die FastAPI
│               │   └── type       # Typ des s6-Services (z.B. "longrun")
│               └── user/
│                   └── contents.d/
│                       └── fastapi # Aktiviert den fastapi-Service
├── requirements.txt     # Python Abhängigkeiten
└── src/                 # Quellcode der FastAPI-Anwendung
```

## 2. Best Practices für das Dockerfile
Das Dockerfile sollte auf einem offiziellen Home Assistant Base-Image aufbauen, da dieses bereits **s6-overlay v3** und andere HA-spezifische Werkzeuge (wie das Bashio-Framework) enthält.
Zudem erfordert Python (seit PEP 668) in neueren OS-Versionen oft eine virtuelle Umgebung (Virtual Environment, venv), um das System bei Installationen nicht zu stören.

**Beispiel Dockerfile:**
```dockerfile
# Offizielles HA Alpine Base Image verwenden
ARG BUILD_FROM=ghcr.io/hassio-addons/alpine-base:7.3.0
FROM $BUILD_FROM

# System-Abhängigkeiten installieren
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    python3-dev

# Virtual Environment erstellen
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Python-Abhängigkeiten installieren
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Anwendungscode und rootfs (s6-overlay Konfiguration) kopieren
COPY rootfs /
COPY src /app/src

# HA Build-Labels (best practice)
LABEL \
    io.hass.name="Alltags-Manager" \
    io.hass.description="FastAPI Backend für den Alltags-Manager" \
    io.hass.type="addon"
```

## 3. Home Assistant Ingress-Support
Ingress ermöglicht es, das Web-UI des Add-ons nahtlos in die Home Assistant Oberfläche (Sidebar) einzubetten, ohne zusätzliche Ports im Router freigeben zu müssen. HA agiert als Reverse Proxy.

**`config.yaml` Konfiguration (Auszug):**
```yaml
name: "Alltags-Manager"
description: "Alltags-Organisations-App (FastAPI)"
version: "1.0.0"
slug: "alltags_manager"
arch:
  - aarch64
  - amd64
  - armv7
ingress: true
ingress_port: 8099
panel_icon: mdi:view-dashboard
panel_title: "Alltags-Manager"
panel_admin: false
```

**Umgang mit dynamischen Ingress-Pfaden in FastAPI:**
Home Assistant routet Anfragen über einen dynamischen Pfad (z.B. `/api/hassio_ingress/xyz123/`). Wenn das Frontend API-Calls macht oder absolute Pfade nutzt, müssen diese den Ingress-Pfad beinhalten.
Der Pfad wird von HA im HTTP-Header `X-Ingress-Path` an die App übergeben.

In FastAPI kann man das über eine Middleware lösen, die den `root_path` dynamisch anpasst, sodass OpenAPI (Swagger) und intern generierte Links weiterhin korrekt funktionieren:
```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def add_ingress_path(request: Request, call_next):
    ingress_path = request.headers.get("X-Ingress-Path", "")
    request.scope["root_path"] = ingress_path
    response = await call_next(request)
    return response
```

## 4. s6-overlay für Prozess-Management
Home Assistant nutzt in den Base-Images das s6-overlay, um Prozesse im Container zu verwalten. Dies ist die sauberste Methode, den FastAPI-Server im Add-on zu starten.

**Struktur für s6-overlay v3:**
In `rootfs/etc/s6-overlay/s6-rc.d/fastapi/run`:
```bash
#!/command/with-contenv bashio
# bashio ist eine Bibliothek im HA Base-Image für Logging etc.
bashio::log.info "Starte FastAPI Backend..."

# Gehe ins Arbeitsverzeichnis
cd /app

# Starte Uvicorn über das Virtual Environment
exec s6-setuidgid root /opt/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8099
```

In `rootfs/etc/s6-overlay/s6-rc.d/fastapi/type`:
```text
longrun
```

In `rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/fastapi` (leere Datei anlegen):
*(Diese Datei signalisiert s6, dass der `fastapi` Service gestartet werden soll).*

## 5. Datenspeicherung (SQLite)
Für ein HA Add-on müssen persistente Daten (wie die SQLite-Datenbank) im speziellen Mount-Ordner `/data` gespeichert werden, da dieser Ordner bei Add-on-Updates oder Container-Neustarts erhalten bleibt. Alle Änderungen in anderen Verzeichnissen gehen beim Update verloren.
In der FastAPI/SQLAlchemy-Konfiguration muss der Pfad zur Datenbank auf `/data/database.sqlite` verweisen.
