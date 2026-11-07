# Recherche: Sichere API-Kommunikation vom Home Assistant Add-on zum Hermes-Agenten

## Zielsetzung
Das FastAPI-Backend des Home Assistant Add-ons (Alltags-Manager) soll Chat-Nachrichten sicher an den Haupt-Hermes-Agenten weiterleiten. Das Frontend (HTML/JS) darf nicht direkt mit Hermes kommunizieren, sondern nutzt das Add-on-Backend als sicheren Proxy.

## Beste Methode: Add-on Optionen & Umgebungsvariablen

Die sicherste und Home-Assistant-konforme Methode basiert auf der Nutzung der Add-on-Konfiguration in Kombination mit Umgebungsvariablen.

### 1. Konfiguration in Home Assistant (`config.yaml`)
Das Add-on muss so konfiguriert werden, dass der Nutzer die Hermes API-URL und den API-Token in der Home Assistant Oberfläche eingeben kann. Dazu werden Optionen im Schema des Add-ons definiert:

```yaml
options:
  hermes_api_url: "https://<hermes-ip>:<port>/api/v1/chat"
  hermes_api_token: ""
schema:
  hermes_api_url: str
  hermes_api_token: password
```
*Der Typ `password` für den Token stellt sicher, dass die Eingabe in der Home Assistant UI maskiert wird.*

### 2. Bereitstellung als Umgebungsvariablen
Home Assistant speichert diese Benutzereingaben in der Datei `/data/options.json` innerhalb des Add-on-Containers. Da das FastAPI-Backend Umgebungsvariablen nutzen soll (Best Practice), sollte das Startskript des Add-ons (z.B. `run.sh`) diese Werte auslesen und vor dem Start von FastAPI exportieren:

```bash
#!/usr/bin/with-contenv bashio
# Nutzt bashio (Home Assistant Standard), um Optionen zu lesen
export HERMES_API_URL=$(bashio::config 'hermes_api_url')
export HERMES_API_TOKEN=$(bashio::config 'hermes_api_token')

# Starten des FastAPI-Backends
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
```

### 3. Umsetzung im FastAPI-Backend (`src/backend/main.py`)
Im FastAPI-Backend werden die Umgebungsvariablen eingelesen. Mit einer asynchronen HTTP-Bibliothek wie `httpx` sendet das Backend dann gesichert Requests an Hermes.

```python
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Konfiguration über Umgebungsvariablen laden
HERMES_API_URL = os.getenv("HERMES_API_URL")
HERMES_API_TOKEN = os.getenv("HERMES_API_TOKEN")

class ChatMessage(BaseModel):
    message: str

@app.post("/api/hermes/chat")
async def chat_with_hermes(payload: ChatMessage):
    if not HERMES_API_URL or not HERMES_API_TOKEN:
        raise HTTPException(status_code=500, detail="Hermes API nicht konfiguriert.")

    headers = {
        "Authorization": f"Bearer {HERMES_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                HERMES_API_URL, 
                json={"message": payload.message}, 
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Kommunikationsfehler: {str(e)}")
```

## Sicherheitsvorteile dieser Architektur
1. **Kein Token-Leak im Frontend:** Das Frontend (HTML/JS) erhält den sensiblen Hermes-Token nie.
2. **Sichere Speicherung:** Home Assistant verwaltet die Add-on-Optionen. Der Token steht nicht hartkodiert im Quellcode.
3. **Flexibilität:** URL und Token können vom Benutzer über die UI jederzeit geändert werden.
4. **Saubere Trennung:** Die Injektion via `run.sh` isoliert die Home-Assistant-spezifische Logik (`options.json`) vom FastAPI-Code, der lediglich standardisierte Umgebungsvariablen erwartet.

## Fazit
Die Kommunikation sollte als Backend-to-Backend-Integration erfolgen. Das Add-on-Backend liest Token und URL aus den injizierten Umgebungsvariablen und nutzt `httpx` für die sichere, Token-basierte Anfrage an den Haupt-Hermes-Agenten.
