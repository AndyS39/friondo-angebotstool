# Friondo Angebotstool

Internes Angebotstool für den Vertrieb der Friondo GmbH (Wärmepumpen zum Festpreis).
Geführter Frage-Konfigurator → automatisches Angebot mit KfW-Förderberechnung →
PDF im Friondo-Layout → Versand per Outlook. Läuft lokal, keine Cloud.

## Starten

Doppelklick auf `start.bat` – Server startet und der Browser öffnet sich.

- am selben Rechner: <http://localhost:8000>
- im Firmennetz: `http://<Rechnername>:8000`

**Firmen-Adresse (Terminal Server):** `http://<SERVERNAME-EINTRAGEN>:8000`
– nach dem Umzug lt. `docs/installation-terminal-server.md` hier den echten
Servernamen eintragen; Desktop-Verknüpfungen der Innendienst-PCs zeigen auf
diese Adresse. Anmeldung beim allerersten Start: Admin / PIN 1234 (sofort ändern).
Mobilzugriff Außendienst: Entscheidung offen, siehe `docs/mobilzugriff.md`.

## Erstmalige Einrichtung (nur auf einem neuen Rechner nötig)

Voraussetzung: Python 3.11 oder neuer.

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
| `app/config.py` + `.env` | Konfiguration (Pfade, MwSt., Nummernkreis, Tokens) |
| `data/` | Laufzeitdaten: SQLite-DB, erzeugte PDFs, Backups (nicht im Git) |

## Projektstand

Umsetzung erfolgt in Phasen laut `PLAN.md`; Projektkontext und fachliche Regeln
stehen in `CLAUDE.md`.
