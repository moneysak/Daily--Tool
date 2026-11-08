# Sicherheits- und Authentifizierungs-Konzept

## 1. Ausgangslage & Angriffsvektoren
Der Alltags-Manager wird auf zwei Wegen erreichbar sein:
1. **Home Assistant Ingress (Intern):** 
   * Zugriff erfolgt über die Home Assistant Web-Oberfläche bzw. Companion App.
   * HA authentifiziert den Benutzer vorab und setzt spezifische Header (`X-Ingress-Path`, `X-Hass-User-ID`, `X-Hass-Is-Admin`).
2. **Direktzugriff / Standalone / Extern (Cloudflare Tunnels, z.B. `app.deinedomain.de`):**
   * Zugriff erfolgt direkt auf Port 8099 ohne den HA-Ingress-Proxy davor.
   * **Risiko:** Ohne Authentifizierung könnte jeder im Netz oder über die Cloudflare-URL Aufgaben lesen, manipulieren oder über die Hermes-Chat-API Befehle an Hermes senden!

---

## 2. Das 2-Stufen-Sicherheitsmodell (Hybrid-Auth)

### Stufe A: Home Assistant Ingress (Seamless / Zero-Click)
* Wenn die Anfrage über Ingress reinkommt (erkennbar am Header `X-Ingress-Path`), vertraut das Backend der Session, da der User bereits in Home Assistant eingeloggt ist.
* Das Backend liest die HA-User-Daten aus und gewährt sofortigen Zugriff ohne lästiges Doppel-Login.

### Stufe B: Direkter Zugriff / API-Zugriff (Token- / Passwort-Schutz)
* Wenn kein Ingress-Header vorliegt:
  * Entweder Session-Token / API-Key (`Authorization: Bearer <TOKEN>`) oder Session-Cookie.
  * In `config.yaml` / Add-on-Options wird ein Konfigurations-Passwort/Token (`app_secret` / `api_token`) hinterlegt.
  * Das Frontend zeigt bei unauthentifizierten Direktaufrufen ein elegantes Login-Overlay im Glassmorphism-Design (PIN / Passwort).
  * Bei erfolgreichem Login wird ein kurzlebiges Auth-Token im `sessionStorage` gehalten und bei allen API-Requests (`/tasks/`, `/api/hermes/chat`) mitgeschickt.

---

## 3. Entfernung kritischer Hardcoded Secrets
* Im Backend (`src/backend/main.py`) wurde gestern ein Fallback-Token für das Supervisor-API hardcoded hinterlegt.
* **Maßnahme:** Dieser Fallback wird restlos entfernt. Das Token wird strikt und sicher aus `os.environ.get("SUPERVISOR_TOKEN")` bezogen. Sollte es fehlen, wird eine klare Fehlermeldung statt eines Sicherheitsrisikos ausgegeben.
