# Friondo Angebotstool

Internes Angebotstool für den Vertrieb der Friondo GmbH (Wärmepumpen zum Festpreis).
Geführter Frage-Konfigurator → automatisches Angebot mit KfW-Förderberechnung →
PDF im Friondo-Layout → Versand per Outlook. Läuft lokal, keine Cloud.

## Starten

**Server (Firmennetz):** Das Tool läuft seit v27 als Windows-Dienst bzw. Aufgabe
auf dem Server (Projektordner `C:\Users\kdadmin\Desktop\Angebotstool`) und ist
unter **`http://192.168.35.4:8000`** erreichbar – im Firmennetz direkt, mobil über
das WireGuard-VPN. Es muss nichts gestartet werden; Desktop-Verknüpfungen der
Innendienst-PCs zeigen auf diese Adresse. Verwaltung nur auf dem Server als
Administrator: `scripts\dienst-status.bat` (Zustand, `/health`),
`scripts\dienst-neustart.bat` (stoppen/starten), Einrichtung
`scripts\dienst-installieren.bat` (`docs/installation-terminal-server.md`,
Abschnitt 4); Updates mit `update.bat` im Wartungsfenster, Rückweg
`rollback.bat` (`docs/updates.md`). Betriebs-Runbook: `docs/betrieb.md`.

**Entwicklungs-PC / Einzelplatz:** Doppelklick auf `start.bat` – Server startet
als Konsolenfenster und der Browser öffnet sich (<http://localhost:8000>; im
Netz `http://<Rechnername>:8000`). Auf einer Maschine, auf der der Dienst oder
die Aufgabe „Friondo Angebotstool“ existiert, bricht `start.bat` mit einem
Hinweis ab.

Anmeldung beim allerersten Start (leere Datenbank): Admin / PIN 1234 (sofort
ändern). Mobilzugriff Außendienst: umgesetzt über WireGuard (Variante A), siehe
`docs/mobilzugriff.md`.

## Erstmalige Einrichtung (nur auf einem neuen Rechner nötig)

Voraussetzung: Python 3.12 oder neuer (Entwicklungs-PC: 3.14).

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

## Wichtige Dateien und Ordner

| Pfad | Zweck |
| --- | --- |
| `konfigurator_logik.xlsx` | Steuerdatei: Fragen, Aktionen, Paketmatrix, KfW-Parameter – Änderungen hier erfordern keine Codeänderung |
| `Artikel-Preislisten/Angebotserstellung Tool.xlsx` | TAIFUN-Preisliste für den Artikel-Import |
| `ANGEBOTSTEXTE.md` | Statische Angebotstexte (Briefkopf, Nachtext-Seiten) |
| `Layout - Logo/` | Logos und Referenz-PDF für das Angebots-Layout |
| `app/config.py` + `.env` | Konfiguration (Pfade, MwSt., Nummernkreis, Tokens, Backup-Ziel, Pool) |
| `data/` | Laufzeitdaten: SQLite-DB, erzeugte PDFs, Backups, Logs (nicht im Git) |
| `scripts/` | Betriebsskripte: Dienst (`dienst-*.bat`, `waechter.ps1`), Smoke-Test, Restore-Test, Crawl |
| `docs/betrieb.md` | Runbook für IT und Andreas (Dienst, Update, Rollback, Backup, Störungen) |

## Projektstand

Umsetzung erfolgt in Phasen laut `PLAN.md`; Projektkontext und fachliche Regeln
stehen in `CLAUDE.md`.
