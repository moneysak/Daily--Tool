# API-Kommunikation im Home Assistant Ingress Umfeld

## 1. Problemstellung
Das Frontend der Alltags-Manager-App muss API-Anfragen an das Python-Backend senden. 
In einer klassischen Web-Umgebung ist die Basis-URL fest (z. B. `http://localhost:8000`), aber bei **Home Assistant Ingress** wird dem Add-on ein dynamischer Pfad zugewiesen (z. B. `/api/hassio_ingress/abc123X/`). 
Da Single-Page-Applications (SPAs) oft tiefer verschachtelte URLs für ihr eigenes Routing nutzen (z. B. `/settings/profile`), sind rein relative Pfade (wie `../api/tasks`) fehleranfällig. Das Frontend muss daher den korrekten Basis-Pfad kennen, um API-Requests sicher und korrekt abzusetzen, egal in welcher Ansicht sich der Nutzer befindet.

## 2. Die Lösung: Der `X-Ingress-Path` Header
Home Assistant löst dieses Problem, indem der Supervisor bei jedem Request über Ingress den HTTP-Header `X-Ingress-Path` an das Add-on mitsendet. 
Das Backend (in diesem Fall die Python-API, welche idealerweise auch das Frontend ausliefert) empfängt diesen Header und kennt so seinen externen Basis-Pfad.

### Empfohlene Methode (Best Practice)
Die robusteste Methode ist die **dynamische Injektion des Ingress-Pfads in das Frontend** beim Ausliefern der initialen HTML-Datei (`index.html`).

#### Schritt 1: Backend liest den Header und injiziert ihn
Wenn das Frontend (die `index.html`) vom Python-Backend ausgeliefert wird, prüft das Backend den Header und schreibt ihn als globale JavaScript-Variable in die HTML-Datei. Falls die App z.B. über Cloudflare aufgerufen wird, fehlt der Header und es wird auf einen leeren String (Root-Pfad `/`) zurückgefallen.

**Beispiel (Python, z. B. mit FastAPI):**
```python
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="frontend/dist")

@app.get("/")
def serve_index(request: Request):
    # Header auslesen, Fallback auf leeren String (für Cloudflare / Standalone)
    ingress_path = request.headers.get("X-Ingress-Path", "")
    
    # HTML ausliefern und Pfad injizieren
    return templates.TemplateResponse("index.html", {
        "request": request,
        "ingress_path": ingress_path
    })
```

**In der `index.html` (Frontend):**
```html
<script>
    window.APP_CONFIG = {
        API_BASE_URL: "{{ ingress_path }}"
    };
</script>
```

#### Schritt 2: Frontend nutzt die Basis-URL für API-Calls
Das Frontend nutzt die injizierte Variable als Präfix für alle Backend-Anfragen.

**Beispiel (Frontend / JavaScript):**
```javascript
const apiBaseUrl = window.APP_CONFIG?.API_BASE_URL || "";

// API-Request durchführen
fetch(`${apiBaseUrl}/api/tasks`)
    .then(response => response.json())
    .then(data => console.log(data));
```

### Alternative: Nutzung des `<base>` Tags
Anstatt einer JavaScript-Variable kann das Backend auch das `<base href="{{ ingress_path }}/">` Tag im `<head>` der `index.html` anpassen.
- **Vorteil:** Relative URLs in HTML (Bilder, CSS, JS) und einfache `fetch()`-Calls (`fetch('api/tasks')`) funktionieren automatisch ohne Präfix im JS-Code.
- **Nachteil:** Kann in modernen SPAs (React/Vue/Angular) Konflikte mit dem clientseitigen History-Routing (HTML5 Mode) verursachen. Diese Router benötigen den Basis-Pfad meistens ohnehin explizit als String in ihrer Router-Konfiguration (z. B. `basename` beim React Router oder `base` beim Vue Router). Die Kombination aus globaler JS-Variable ist daher meist sicherer und flexibler.

## 3. Berücksichtigung von Cloudflare / Standalone-Zugriff
Da die App auch über Cloudflare (oder direct access) erreichbar sein soll:
- Über Cloudflare wird die App meist über eine eigene Subdomain (z. B. `app.deine-domain.de/`) aufgerufen.
- Der `X-Ingress-Path` Header existiert in diesem Fall nicht (bzw. ist leer).
- Das Backend verwendet dank `.get("X-Ingress-Path", "")` den Fallback `""` (leerer String).
- Das Frontend sendet API-Requests somit an `"" + "/api/tasks"`, was korrekterweise zu `/api/tasks` unter der jeweiligen Domain führt.

## 4. Fazit & Zusammenfassung
1. **Verwende den `X-Ingress-Path` Header** im Python-Backend.
2. **Injiziere diesen Pfad in die `index.html`** als globales Konfigurationsobjekt (`window.APP_CONFIG`).
3. **Nutze diesen Pfad im Frontend** sowohl als Base-URL für den API-Client (Axios oder Fetch) als auch als Base-Path für den SPA-Router (z. B. Vue/React Router).
4. **Nutze den Fallback (`""`)**, damit die App nahtlos über Cloudflare oder lokale Standalone-Setups funktioniert. Ohne Ingress ist die App dann weiterhin ganz normal unter dem absoluten Root-Pfad lauffähig.