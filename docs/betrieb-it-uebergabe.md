# Friondo Angebotstool – Übergabe an die IT (eine Seite, Stand 06.10.2026, v27)

Das Angebotstool (FastAPI/uvicorn, SQLite, Python) läuft auf dem Server im
Projektordner `C:\Users\kdadmin\Desktop\Angebotstool` als Windows-Dienst
`FriondoAngebotstool` (NSSM) bzw. als Aufgabe „Friondo Angebotstool“ unter dem
Konto SYSTEM, Port 8000, Adresse `http://192.168.35.4:8000`, Status ohne
Anmeldung unter `GET /health`. Demnächst nutzen es 50 Mitarbeiter per Browser im
Firmennetz und über das WireGuard-VPN. Ansprechpartner Tool: Andreas; Runbook
`docs/betrieb.md`; Einrichtung `docs/installation-terminal-server.md`.

Die folgenden Punkte verbessern den Betrieb, **blockieren aber nichts** – für
jeden gibt es einen Zwischenstand, der heute ohne IT funktioniert.

| # | Punkt | Was die IT liefert | Zwischenstand heute |
|---|---|---|---|
| 1 | **Dienstkonto** | lokales Dienstkonto oder gMSA mit Schreibrecht auf den Projektordner und `data\` (und auf das Backup-Ziel, Punkt 2). Eintragen: `scripts\nssm.exe set FriondoAngebotstool ObjectName "DOMÄNE\Konto" "Kennwort"`, dann `scripts\dienst-neustart.bat` | Konto SYSTEM |
| 2 | **Backup-Ziel** | Netzlaufwerk/UNC-Pfad mit Schreibrecht für das Dienstkonto, Aufbewahrung **90 Tage**, Einbindung in die zentrale Sicherung. Eintragen als `BACKUP_ZIEL=\\Server\Freigabe\Angebotstool` in der `.env` (Spiegelung nächtlich 02:30 per robocopy: `backups`, `angebote`, `projekte`, `.env`; Protokoll `data\backups\ziel.log`) | Ordner auf fr-wts-02 oder OneDrive/SharePoint als `BACKUP_ZIEL`; lokale Sicherung 30 Tage in `data\backups\` |
| 3 | **Reverse-Proxy mit HTTPS** | IIS mit ARR, Caddy oder nginx; internes Zertifikat; DNS-Name **`tool.friondo.local`** [ANNAHME] → `http://127.0.0.1:8000`; danach Port 8000 nur noch lokal (Firewall-Regel „Friondo Angebotstool“ entfernen). Tool-Seite ist vorbereitet: `.env` `PROXY_IPS=<Proxy-IP>` (uvicorn `--proxy-headers --forwarded-allow-ips`), `HTTPS_AKTIV=1` (Cookie secure), `BASIS_URL=https://tool.friondo.local`; `/health` bleibt ohne Login erreichbar | HTTP im Firmennetz/VPN über `http://192.168.35.4:8000` |
| 4 | **VPN** | **vorhanden** (WireGuard, Variante A, Stand 06.10.2026 – der Außendienst arbeitet darüber bereits mit dem Tool). Nur noch: neue WireGuard-Profile (je Gerät ein Peer, QR-Code), Sperrprozess bei Geräteverlust | läuft |
| 5 | **Monitoring** | `GET http://192.168.35.4:8000/health` alle **60 s**; Alarm bei HTTP ≠ 200 oder `status ≠ ok` länger als **5 Minuten**; Empfänger Andreas + IT. JSON-Felder siehe `docs/betrieb.md` („/health-Felder“); `warn` = Hinweis, `fehler`/503 = Störung | Wächter-Aufgabe auf dem Server (Neustart bei Ausfall), `scripts\health-pruefen.ps1` auf fr-wts-02 (Benachrichtigung an Andreas), Admin-Glocke im Tool |
| 6 | **Serverausbau** | nur, wenn der Lasttest (PLAN_V17 Phase 131) es verlangt: Empfehlung 4 vCPU / 8 GB RAM / SSD; `data\` auf lokaler Platte; Uhrzeit per NTP | aktueller Server, Messwerte in `docs/betrieb.md` |
| 7 | **Virenscanner-Ausnahme** | zentral verwalteter Scanner: Echtzeitscan-Ausnahme für `C:\Users\kdadmin\Desktop\Angebotstool\data\` (Datei-Sperren sind eine bekannte Ursache für „database is locked“) | lokal eingetragen bzw. offen |
| 8 | **Windows-Updates des Servers** | nur im Wartungsfenster (**Dienstag 18:30–19:30** [ANNAHME]), Neustart danach prüfen: Dienst/Aufgabe startet automatisch, Kontrolle `/health` | Andreas setzt vorher das Wartungsbanner im Tool |
| 9 | **Option: Anmeldung über Microsoft 365 (Entra ID)** statt PIN | eigener Plan, wenn gewünscht (App-Registrierung, Gruppen → Rollen) | PIN-Login mit Härtung (Mindestlänge, Fehlversuchssperre, Sitzungsablauf) |

Was die IT **nicht** anfassen muss: Updates des Tools (`update.bat` im
Wartungsfenster durch Andreas), Rollback (`rollback.bat`), Smoke-Test
(`scripts\smoke.bat`), Restore-Test (`scripts\restore-test.bat`, monatlich),
Benutzer und PINs (im Tool). Logs: `data\fehler.log`, `data\log\zugriff.log`,
`data\log\dienst-*.log`, `data\log\waechter.log`, `data\backups\ziel.log`.
