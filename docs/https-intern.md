# HTTPS im Firmennetz/VPN – Vorbereitung (v34, PLAN_V21 Phase 181)

Stand 15.10.2026 · **Entscheidung Andreas/IT – nicht Teil von v34.** Das Tool läuft heute über
`http://192.168.35.4:8000` (Firmennetz, Außendienst über WireGuard-VPN, `docs/mobilzugriff.md`).
Zwei Funktionen der Handys brauchen einen **sicheren Kontext** (HTTPS oder `localhost`;
im Browser `window.isSecureContext`), den der Browser über http nicht gewährt:

| Funktion | Browser-Schnittstelle | heute (http) | mit HTTPS |
|---|---|---|---|
| Diktat in Textfeldern (Knopf „Diktieren“, v34) | Web Speech API `SpeechRecognition` | Knopf zeigt „Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden“ (Tastatur-Diktat von iOS/Android funktioniert in jedem Feld) | Erkennung im Browser, Text landet am Cursor |
| Live-Kamera im Browser (nicht geplant) | `getUserMedia` | – | möglich; die Kamera-Serie v34 (Fotos über die Kamera-App, Upload gesammelt) braucht KEIN HTTPS |
| Push-Benachrichtigungen, Service-Worker (nicht geplant) | Service Worker | – | möglich |

Alles Übrige (Anmeldung, Erfassung, Galerie-Upload, PDF, Kalender) funktioniert über http unverändert.

## Was das Tool schon kann (v27, PLAN_V17 Phase 129)

Die Tool-Seite ist vorbereitet, es ist keine Codeänderung nötig – nur `.env` und ein Reverse-Proxy:

- `HTTPS_AKTIV=1` → Sitzungs-Cookie mit `Secure` (bleibt `HttpOnly`, `SameSite=Lax`, `Path=/`).
- `BASIS_URL=https://<name>` → absolute Links in Mails, ICS-Dateien und Signatur-Links.
- `PROXY_IPS=<IP des Proxys>` → die Start-Skripte starten uvicorn mit `--proxy-headers
  --forwarded-allow-ips`, damit das Tool die Client-Adresse (Login-Protokoll, IP-Sperre) aus
  `X-Forwarded-For` liest.
- `/health` bleibt ohne Anmeldung erreichbar (Wächter, Monitoring).

Das Tool selbst spricht weiter http auf Port 8000; HTTPS endet am Proxy (IIS mit ARR, Caddy oder
nginx auf demselben Server, siehe `docs/betrieb-it-uebergabe.md` Punkt 3). Nach der Umstellung Port
8000 nur noch lokal freigeben (Firewall-Regel „Friondo Angebotstool“ auf 127.0.0.1 beschränken).

## Option A – Zertifikat für eine interne Friondo-Subdomain (DNS-Challenge)

- Name z. B. `tool.friondo.de` (öffentliche Domain, interne Adresse): im **internen** DNS (und im
  WireGuard-DNS) zeigt der Name auf `192.168.35.4`; im öffentlichen DNS steht KEIN A-Record.
- Zertifikat von Let's Encrypt über die **DNS-01-Challenge** (TXT-Record `_acme-challenge.tool.
  friondo.de` beim DNS-Anbieter der Domain) – dafür muss nichts aus dem Internet erreichbar sein.
  Caddy erneuert automatisch (DNS-Plugin des Anbieters), bei IIS/nginx win-acme bzw. certbot mit
  DNS-Plugin (Erneuerung alle 60–90 Tage als geplante Aufgabe).
- Vorteil: öffentliche CA, **kein Geräteprofil** auf den Handys, alle Browser vertrauen sofort.
- Nachteil: der Hostname steht in den öffentlichen Zertifikats-Logs (nur der Name, keine Adresse);
  DNS-API-Zugang des Domain-Anbieters wird auf dem Server hinterlegt.
- Aufwand: 1–2 Stunden IT, laufend keiner.

## Option B – interne CA mit Geräteprofil

- Eigene Zertifizierungsstelle (vorhandene Windows-CA der Domäne oder eine neue, z. B. mit
  `step-ca`/mkcert); Server-Zertifikat für `tool.friondo.local` (oder die IP als SAN).
- Das Stammzertifikat muss auf **jedes** Gerät: Domänen-PCs per Gruppenrichtlinie; iPhones/iPads
  über ein Konfigurationsprofil, das der Nutzer installiert UND unter Einstellungen → Allgemein →
  Info → Zertifikatsvertrauen aktiviert (sonst „Verbindung nicht privat“); Android über
  Einstellungen → Sicherheit → Zertifikat installieren (Chrome vertraut Nutzer-Zertifikaten, einige
  Apps nicht).
- Vorteil: nichts verlässt das Firmennetz, kein DNS-Anbieter, keine Erneuerung durch Dritte.
- Nachteil: je Handy ein manueller Schritt (bei 50 Nutzern ~15 Geräte des Außendienstes plus alle
  Geräte, die später dazukommen); vergessene Profile = Fehlermeldung beim Kunden.
- Aufwand: 2–4 Stunden IT plus 5 Minuten je Gerät, Erneuerung je nach Laufzeit (3–5 Jahre).

## Option C – vorerst nichts tun

Das Tastatur-Diktat der Handys (Mikrofon-Taste der iOS-/Android-Tastatur) funktioniert in jedem
Textfeld – der Knopf „Diktieren“ sagt das genau so. Die Kamera-Serie und der Mehrfachupload der
Galerie brauchen kein HTTPS. Das ist der Stand nach v34.

## Empfehlung

Option A (interne Subdomain mit DNS-Challenge), weil sie ohne Geräteprofile auskommt und
WireGuard-DNS den Namen ohnehin intern auflösen kann. Reihenfolge: (1) DNS-Name intern anlegen,
(2) Proxy mit Zertifikat vor Port 8000 (Testadresse zuerst parallel zum alten http-Zugang),
(3) `.env`: `HTTPS_AKTIV=1`, `BASIS_URL=https://tool.friondo.de`, `PROXY_IPS=127.0.0.1`,
Dienst neu starten (`scripts\dienst-neustart.bat`), (4) Prüfen: `/health` über https, Anmeldung
am Handy (Cookie mit `Secure`), Knopf „Diktieren“ in der Freitext-Erfassung startet die
Erkennung, Mail-Links zeigen auf die https-Adresse, (5) http-Zugang abschalten, Wartungshinweis
und Team-Info (neue Adresse, Home-Bildschirm-App neu anlegen – andere Adresse = andere App).

## Prüfliste für die IT nach der Umstellung

- [ ] `https://<name>/health` antwortet mit `"status": "ok"` (Zertifikat ohne Warnung am Handy)
- [ ] Anmeldung am Handy: Set-Cookie trägt `Secure`, `HttpOnly`, `SameSite=lax`, `Max-Age` + `Expires`
- [ ] Freitext-Erfassung am Handy: „Diktieren“ fragt das Mikrofon ab und schreibt Text ins Feld
- [ ] Login-Protokoll zeigt die echte Client-IP (nicht die des Proxys)
- [ ] Mails/ICS/Signatur-Links verwenden `BASIS_URL`
- [ ] Port 8000 von außen geschlossen, Wächter (`scripts\waechter.ps1`) prüft weiter lokal
