# Recherche: Git-Repository Verwaltung im Home Assistant Add-on Umfeld

## 1. Einleitung
Für die Entwicklung und das Deployment eines Git-basierten Home Assistant Add-ons (wie dem "Alltags-Manager") stellt sich die Frage nach der optimalen und sichersten Verwaltung des Repositories innerhalb der Docker-Container-Umgebung (Supervisor). Ziel ist es, den Quellcode sicher, persistent und automatisierbar in das Add-on zu laden.

## 2. Authentifizierung: SSH-Keys vs. HTTPS

Im Kontext eines Home Assistant Add-ons gibt es zwei primäre Methoden, um sich gegenüber dem Git-Server (z.B. GitHub, GitLab, Gitea) zu authentifizieren:

### 2.1 SSH-Keys
**Vorteile:**
- **Sicherheit:** Nutzt asymmetrische Kryptographie. Private Keys sind sehr sicher gegen Brute-Force-Angriffe.
- **Deploy Keys:** Git-Provider erlauben oft sogenannte "Deploy Keys", die an ein spezifisches Repository gebunden sind und nur Lesezugriff (Read-Only) erhalten können.
- **Keine Token-Ablaufdaten:** SSH-Keys laufen in der Regel nicht ab, es sei denn, sie werden aktiv widerrufen.
- **Keine Passwörter im Speicher:** Das Klonen erfolgt ohne die Notwendigkeit, Passwörter in Umgebungsvariablen oder URLs speichern zu müssen.

**Nachteile:**
- **Komplexeres Setup:** Der Container muss so konfiguriert werden, dass er den SSH-Client enthält, die Datei `~/.ssh/config` oder `GIT_SSH_COMMAND` korrekt setzt und die richtigen Dateiberechtigungen (chmod 600) für den Private Key sicherstellt.
- **Host-Keys (StrictHostKeyChecking):** Der Public Key des Git-Servers muss in die `known_hosts`-Datei des Containers aufgenommen oder die Prüfung deaktiviert werden, was ein Sicherheitsrisiko (Man-in-the-Middle) darstellen kann.

### 2.2 HTTPS (mit Personal Access Token / PAT)
**Vorteile:**
- **Einfachheit:** Keine SSH-Schlüsselverwaltung notwendig. Git über HTTPS funktioniert "out of the box".
- **Firewall-freundlich:** Port 443 (HTTPS) ist in der Regel in jedem Netzwerk freigeschaltet, während Port 22 (SSH) manchmal blockiert sein kann.

**Nachteile:**
- **Sichtbarkeit des Tokens:** Wenn der Token in der Git-URL verpackt wird (`https://<token>@github.com/...`), taucht er in den Logs oder in der Konfigurationsdatei `.git/config` im Klartext auf, wenn man nicht aufpasst.
- **Lebensdauer:** Tokens haben oft ein Ablaufdatum (Best Practice), was bedeutet, dass der Nutzer den Token im Add-on regelmäßig erneuern muss.
- **Reichweite:** PATs sind oft an den User gebunden und haben unter Umständen mehr Rechte, als für das bloße Klonen eines Repositories erforderlich sind (obwohl z.B. GitHub mittlerweile "Fine-grained PATs" anbietet).

### 2.3 Fazit zur Authentifizierung
Für **lokale, unbeaufsichtigte Container (Add-ons)** ist die Nutzung von **SSH Deploy Keys (Read-only)** die professionellste und sicherste Methode, da das Risiko bei einem Leak minimiert wird und keine regelmäßige Erneuerung von Passwörtern nötig ist. Für Einsteiger ist oft HTTPS über die Add-on Konfiguration am leichtesten verständlich.

---

## 3. Sichere Speicherung von Credentials im HA-Umfeld

In Home Assistant Add-ons ist die Dateisystem-Struktur strikt geregelt. Es gibt primär zwei Orte, um Daten (und damit auch Credentials) zu verwalten:

### 3.1 Die Add-on Konfiguration (Options)
Credentials (wie ein HTTPS PAT oder ein Private SSH Key) können direkt über die Benutzeroberfläche des Add-ons in Home Assistant eingegeben werden. 
In der `config.yaml` des Add-ons können diese Felder definiert werden (z.B. als `password`, damit sie im UI nicht im Klartext lesbar sind).

- **Speicherort intern:** Die Werte landen in der Datei `/data/options.json` im Container.
- **Vorteil:** Sehr benutzerfreundlich. Der Nutzer bleibt in der Home Assistant GUI.
- **Nachteil:** Die `options.json` wird vom Supervisor auf dem Host-System verwaltet. Wenn ein Backup gemacht wird, landen die Klartext-Tokens im Backup, sofern dieses nicht verschlüsselt ist. Bei Multiline-Strings (wie SSH-Keys) kann das UI-Handling manchmal umständlich sein.

### 3.2 Das persistente `/data/`-Verzeichnis
Jedes Add-on hat ein eigenes `/data/`-Verzeichnis. Alle Daten, die hier gespeichert werden, überleben Neustarts und Add-on-Updates.

- **Vorteil:** Ideal für Datenbanken, Repositories und generierte Zertifikate/Keys. Dateiberechtigungen können strikt auf den Container-User beschränkt werden.
- **Nachteil:** Der Nutzer hat keinen direkten Zugriff über die Home Assistant GUI auf dieses Verzeichnis.

## 4. Best Practice Empfehlungen für den "Alltags-Manager"

Basierend auf den Eigenschaften der Home Assistant Architektur, ergeben sich zwei empfohlene Workflows:

### Option A: Automatisierte SSH-Key Generierung (Empfehlung für höchste Sicherheit)
1. **Initialisierung:** Beim ersten Start prüft das Add-on-Skript (`run.sh`), ob im Verzeichnis `/data/.ssh/` ein Schlüsselpaar existiert.
2. **Generierung:** Falls nicht, generiert das Skript automatisch einen neuen RSA/Ed25519-Key und speichert ihn in `/data/.ssh/`.
3. **Ausgabe:** Der Public Key (`/data/.ssh/id_ed25519.pub`) wird in den Add-on-Logs im Supervisor-Dashboard im Klartext ausgegeben.
4. **Benutzer-Aktion:** Der Nutzer wird im Log aufgefordert, diesen Public Key in seinem Git-Repository als "Deploy Key" hinzuzufügen.
5. **Git Clone:** Sobald eingerichtet, klont das Add-on das Repository in das persistente `/data/repo/`-Verzeichnis, unter Nutzung der generierten Keys.
*Vorteil:* Der Private Key verlässt niemals den Container und den persistenten `/data/` Speicher.

### Option B: HTTPS mit Token über Add-on Options (Empfehlung für höchste Benutzerfreundlichkeit)
1. **Konfiguration:** Der Nutzer erstellt auf GitHub/GitLab ein (Fine-grained) Personal Access Token (nur Lese-Rechte auf das Repo).
2. **Eingabe:** Der Token und die Repository-URL werden in den Add-on Einstellungen über das HA Dashboard eingegeben. Das Token-Feld hat in der `config.yaml` den Typ `password`.
3. **Git Clone:** Das Add-on liest beim Start die `/data/options.json`, extrahiert den Token und konfiguriert Git im Container so, dass es das Token verwendet (z.B. mittels `git config --global url."https://<token>@github.com/".insteadOf "https://github.com/"`).
4. **Persistenz:** Das Repository selbst wird in `/data/repo/` geklont. Der Token verbleibt in der `options.json` und nicht im Git-Repository selbst.

### Fazit und Speicherung
Das Git-Repository als solches (der Code, die `.git` Dateien) sollte **immer** im `/data/`-Verzeichnis des Add-ons geklont werden, da es dort persistent über Add-on Updates hinweg erhalten bleibt. Dies beschleunigt den Start (nur `git pull` statt `git clone`). 
Die Authentifizierung sollte je nach Zielgruppe gewählt werden: Option A (SSH, `/data/`) für maximale Sicherheit oder Option B (HTTPS, Add-on Config) für ein reibungsloseres Setup-Erlebnis in der Home Assistant GUI.