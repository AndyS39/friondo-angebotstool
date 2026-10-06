# Nach dem Update v26 (PLAN_PROJ_V5) – Heizreport-Anbindung & Pilot-Nebensachen

Dieses Update bindet Heizreport über die öffentliche Kunden-API v2 an
(Projektierung, Aufgabe „Heizlastberechnung liegt vor“), stellt das Montageteam
am Benutzer auf ein Dropdown um und gliedert die Parametrierung neu. Projektierung
läuft weiter im eingestellten `freigabe_modus` (Pilot); Angebotstool,
Lead-Management, monday-Sync und PDF-Erzeugung der Angebote sind unverändert.

## Echtlauf-Checkliste Heizreport (Andreas, ohne Netzaufrufe im Test)

1. **Token eintragen:** Parametrierung → Projektierung → Heizreport → Zugang:
   Modus „Kunden-API v2“, Token aus dem Pro-Bereich des Heizreport-Kontos,
   Speichern, dann „Verbindung testen“ – erwartete Meldung „Verbindung OK ·
   API-Version 2.4.0 · <n> eigene Projekte (Gruppen: …)“. Ohne Token: „Heizreport
   erreichbar, aber Token abgelehnt (HTTP 401)“.
2. **Erstes Projekt anlegen** (nach Freigabe – Projektanlage braucht eine aktive
   Jahres- oder Bildungslizenz): an einem Demo-Gewerk in der Projektakte, Aufgabe
   „Heizlastberechnung liegt vor“ → „Heizreport-Projekt anlegen“. Danach steht der
   Schlüssel (9 Buchstaben) an der Aufgabe, der Verlauf nennt die vorbelegten Felder.
3. **Kennzahlen ermitteln** mit `scripts/heizreport_kennzahlen.py` am Testprojekt
   (Ablauf in docs/heizreport-api.md, Abschnitt 3) und als JSON unter
   Parametrierung → Heizreport → Kennzahlen eintragen; bis dahin werden
   Heizungsart/Altersklasse/Trinkwasser/Solarart nicht gesendet (Klartext steht in
   `bemerkungen`).
4. **Referenzprojekt prüfen:** am fertig berechneten Referenzprojekt (Schlüssel von
   Hand eintragen, falls nicht aus dem Tool angelegt) „Heizlast abrufen“ und den
   Wert mit der Portal-Anzeige vergleichen (0,1 kW genau). Weicht er ab, den
   richtigen Ergebnis-Pfad unter Parametrierung → Heizreport → Ergebnis-Pfad
   eintragen (Vorbelegung `results.summary.heatLoad`; Ersatz = Summe der
   Raumheizlasten). Galerie-Ordner unter „Ablage“ prüfen (Vorbelegung
   „Montagedokumente“).
5. **Einmal „Heizreport-PDF ablegen“** – das PDF liegt danach in der Galerie des
   Vorgangs im eingestellten Ordner als `Heizreport-<PR-Nummer>-WP-<Datum>.pdf`.
   Achtung: jeder weitere Abruf erzeugt bei Heizreport ein neues Dokument – das
   Tool fragt deshalb beim zweiten Klick nach.

## Für die Projektierung

- **Heizreport-Knöpfe an der Heizlast-Aufgabe** (sobald der Token hinterlegt ist):
  „Heizreport-Projekt anlegen“ (nur solange kein Schlüssel am Gewerk; alternativ
  „Schlüssel von Hand eintragen“), danach „Heizreport öffnen ↗“ mit dem Schlüssel
  zum Kopieren, „Heizlast abrufen“ und „Heizreport-PDF ablegen“; „Verknüpfung
  lösen“ nur mit Begründung. Die Heizlastberechnung selbst (Räume, U-Werte,
  Heizflächen) bleibt im Heizreport-Portal – „Heizlast abrufen“ meldet „noch nicht
  berechenbar“, solange dort nichts erfasst ist.
- **Abgleich mit der verkauften Leistungsklasse:** nach „Heizlast abrufen“ zeigt die
  Aufgabe (und der Heizlast-Block der Akte) einen roten Hinweis, wenn die
  Heizreport-Heizlast laut Paketmatrix in eine andere Leistungsklasse fällt als
  im Steckbrief verkauft – „Auslegung prüfen (Nachtrag oder Freigabe)“. Angebot,
  Steckbrief und Stückliste werden nicht automatisch geändert.
- In der Feinplanungs-Erfassung sind „Heizlast (kW)“ und „Heizlast-Quelle“ nach
  dem Abruf mit dem Badge „aus Heizreport“ vorbelegt (bestätigen oder ändern).
- Ohne Token bleibt alles wie bisher (Link + Upload, Heizlast von Hand).
- Fehlgeschlagene Heizreport-Aufrufe stehen im Fehlerprotokoll (Fehlertyp
  „Heizreport“) – ohne Token.

## Benutzer und Parametrierung

- **Montageteam am Benutzer:** Unter Parametrierung → Allgemein → Benutzer wird das
  Montageteam je Montage-Benutzer über ein Dropdown gewählt („– kein Team –“ oder
  ein aktives Team); bestehende Zuordnungen bleiben erhalten, bei mehreren Teams
  steht je Team ein Dropdown untereinander. Ein weiteres Team gibt es über
  „+ weiteres Team“, „×“ entfernt eines – die Teams selbst werden weiterhin unter
  Parametrierung → Teams angelegt.
- **Parametrierung neu gegliedert:** Die Übersicht zeigt jetzt fünf Bereiche
  (Allgemein · Angebotstool · Projektierung · Lead-Management · System &
  Protokolle) mit Suchfeld; alle bisherigen Adressen bleiben gültig. Die
  Inline-Abschnitte der alten Übersicht liegen auf zwei eigenen Seiten:
  „Angebotstool-Einstellungen“ (Deckungsbeitrags-Ampel, E-Mail-Versand,
  Kombi-Versand, gewerkeübergreifende Artikel, Fern-Signatur, Abgelehnt-Prozess,
  Lösch-Protokoll) und „Logik & Importe“ (eingelesene Logik, Fragen,
  Angebotsaufbau, KfW-/PV-/KL-Parameter, Klima-Import, „Parametrierung neu
  einlesen“). Kein Formular verhält sich anders als vorher. Die
  Projektierung-Einstellungen haben eine Abschnitts-Navigation und einen festen
  Speichern-Knopf; der Heizreport-Block ist nach Parametrierung → Heizreport
  umgezogen (dort auch der Portal-Link).

## Offen

- Referenzprojekt-Schlüssel und Token liegen nur bei Andreas (nicht im Projekt);
  der Ergebnis-Pfad gilt bis zur Prüfung am Referenzprojekt als Annahme [A-5].
- Kennzahlen-Bedeutungen (Abschnitt 3 der Heizreport-Doku) – bis zur Eintragung
  werden die Felder nicht gesendet.
- Stufe 2: Räume per API, Webhook (öffentliche HTTPS-Adresse), Bilder,
  Wärmepumpen-Check (Angebotsstrang).
- Siehe Gesamtübersicht zur Übergabe und `docs/projektierung-entscheidungen.md`
  Abschnitt PLAN_PROJ_V5 (Annahmen A-1 … A-6).

## Hotfix 06.10.2026 – Datenbank-Verbindungspool

- **Was war:** Auf dem Server meldete das Tool „QueuePool limit of size 5 overflow 10
  reached, connection timed out, timeout 30.00“ – bei mehreren gleichzeitigen Nutzern
  waren alle Datenbank-Verbindungen belegt, Seiten hingen 30 Sekunden und scheiterten.
  Ursache: jede Anfrage hielt zwei Verbindungen (Rollen-Prüfung + Seite), und Seiten mit
  Netzaufrufen (Terminvorschläge mit Routing/Outlook, Heizreport, Mails) hielten ihre
  Verbindung während des Wartens auf den fremden Dienst.
- **Was jetzt gilt:** größerer Pool (20 + 40) mit kurzem Timeout (10 s – die Meldung
  lautet dann „Datenbank-Verbindungen ausgelastet – bitte in einer Minute erneut
  versuchen (Fehler-Nr. …)“), die Rollen-Prüfung gibt ihre Verbindung vor der Seite frei,
  und vor jedem Netzaufruf wird die Verbindung freigegeben (Regel „keine offene Sitzung
  während Netz-I/O“ in CLAUDE.md). Parametrierung → Fehlerprotokoll zeigt oben die
  aktuelle Pool-Belegung; Einträge zu einem erschöpften Pool stehen nur im Datei-Log
  `data\fehler.log`.
- **Nebenbefund:** Zwei Nutzer, die gleichzeitig Terminvorschläge für Leads mit
  derselben Strecke öffneten, bekamen bisher einen 500er (doppelter Cache-Eintrag) –
  behoben.
- Nach dem Pull neu starten – die Pool-Parameter greifen erst beim Start: auf dem Server
  läuft das Tool als Konsolenfenster aus `start.bat` (keine Aufgabe, kein Dienst). Also
  `update.bat` ausführen, das Konsolenfenster schließen und `start.bat` neu starten.
- Diagnose-Nachtrag: die Server-Logs (`data\fehler.log` → `diagnose\fehler-server-2026-10-06.log`,
  DB-Sicherung aus `data\backups\update_<Zeit>` → `diagnose\server-2026-10-06\angebotstool.db`,
  beides gitignored) werden nach dem Update ausgewertet; erstes Auftreten, laufende Version
  und betroffene Routen kommen als Nachtrag in CLAUDE.md, Abschnitt Hotfix.

## Backup-Aufgabe „Friondo Backup“ (Übergangslösung bis PLAN_V17)

> **Überholt durch v27:** Die Sicherung läuft seit v27 im Tool (Scheduler 02:30 mit
> Spiegelung nach `BACKUP_ZIEL`). Die Aufgabe „Friondo Backup“ wird von
> `scripts\dienst-installieren.bat` entfernt bzw. von Hand mit
> `schtasks /Delete /TN "Friondo Backup" /F` – siehe `docs/nach-dem-update-v27.md`.

`scripts\backup-nacht.bat` sichert die Datenbank über die bestehende Funktion
`db.taegliches_backup()` nach `data\backups` (eine Datei je Tag, 30 Tage) und spiegelt
danach `data\backups`, `data\angebote` und `data\projekte` per robocopy nach
`BACKUP_ZIEL` aus der `.env` (Zeile `BACKUP_ZIEL=<Ordner>`, Vorlage in `.env.example`,
Standard `D:\Backup\Angebotstool`; Log `data\backup-nacht.log`).

Einrichtung auf dem Server (Eingabeaufforderung als Administrator; das Tool liegt dort
unter `C:\Users\kdadmin\Desktop\Angebotstool`). Zuerst `BACKUP_ZIEL=` in der `.env` des
Servers eintragen, dann die Aufgabe anlegen – je nach Zielordner:

**Variante A – lokales Laufwerk, Aufgabe als SYSTEM** (`BACKUP_ZIEL=D:\Backup\Angebotstool`):

```bat
schtasks /Create /F /TN "Friondo Backup" /SC DAILY /ST 02:30 /RU SYSTEM /RL HIGHEST /TR "\"C:\Users\kdadmin\Desktop\Angebotstool\scripts\backup-nacht.bat\""
schtasks /Run /TN "Friondo Backup"
```

**Variante B – Netzfreigabe, Aufgabe unter dem eigenen Benutzerkonto**
(`BACKUP_ZIEL=\\<Server>\<Freigabe>\Angebotstool`; SYSTEM hat auf die Freigabe keine
Rechte, das Konto braucht Schreibrecht auf der Freigabe; `/RP *` fragt das Kennwort
einmalig ab, „Unabhängig von der Benutzeranmeldung ausführen“ wird damit gesetzt):

```bat
schtasks /Create /F /TN "Friondo Backup" /SC DAILY /ST 02:30 /RU <Domäne\Konto> /RP * /RL HIGHEST /TR "\"C:\Users\kdadmin\Desktop\Angebotstool\scripts\backup-nacht.bat\""
schtasks /Run /TN "Friondo Backup"
```

Danach prüfen: `data\backup-nacht.log` endet mit „Backup fertig“, im Zielordner liegen
`backups\angebotstool-<Datum>.db`, `angebote\…` und `projekte\…`. Zum Testen von Hand
geht auch `scripts\backup-nacht.bat <Zielordner>` (der Parameter überschreibt
`BACKUP_ZIEL`). Die Aufgabe ersetzt keine Wiederherstellungsübung – einmal testweise
eine Sicherung zurückspielen (Kopie nach `data\angebotstool.db` bei geschlossenem
Konsolenfenster, siehe `rollback.bat`).
