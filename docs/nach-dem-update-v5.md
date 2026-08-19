# Nach dem Update auf v5 – Checkliste (Phasen 29–36 + Nachtrag)

**Stand 20.08.2026 – Rollout-Paket „v5-Nachtrag“:** Der Server läuft seit
19.08. auf v5 (Phasen 29–36). Dieses Update bringt zusätzlich den Nachtrag
(Leads ausblenden, Vertriebler-Spalte, A09-Validator, vier Broschüren, Logik-
Blatt „Anhänge“) und das Abnahmeskript. Was `update.bat` dabei tut:
`migrate.py` ergänzt drei Spalten an `leads` (ausgeblendet, Grund, Datum) –
idempotent geprüft gegen eine Kopie der Datenbank vor v5 und gegen den
aktuellen Stand; die vier PDFs landen per `git pull` in `anlagen\`; die
Logik v5 wird beim Dienststart neu eingelesen. **Nach dem Update bitte alle
offenen Browser-Tabs des Tools neu laden (Strg+F5).**

Abnahme vor dem Rollout (Entwicklungs-PC, 20.08.): 74/74 Unit-Tests und
43/43 Punkte in `testsbnahme.py` (Kontroll-Szenarien KG/DG/Rabatt inkl. A13,
15 KfW-Fälle gegen den HTML-Rechner, A09-Stahltank, Anhänge-Regeln, Status-Kette
mit Absender/CC/BCC, Lösch-/Archiv-Regeln, Briefanrede im PDF).

Diese Punkte sind **einmalig nach dem Rollout** zu erledigen, teils durch die
IT/M365-Admin, teils durch den Innendienst in der Parametrierung. Reihenfolge
einhalten – ①/② sind Voraussetzung für den Versand mit Absender angebot@.

## ① M365-Admin: „Senden als“ für angebot@friondo.de

Exchange Admin Center → Empfänger → Postfächer → **angebot@friondo.de**
(freigegebenes Postfach, ggf. neu anlegen) → **Postfachdelegierung**:
für **jeden Innendienst-Mitarbeiter** die Rechte **„Senden als“** und
**„Lesen und Verwalten (Vollzugriff)“** vergeben. Greift nach bis zu 60 Min.
Details: `docs/graph-einrichtung.md`, Abschnitt 3a.

## ② IT: Graph-Berechtigungen erweitern + Admin-Zustimmung erneuern

App-Registrierung „Friondo Angebotstool“ → API-Berechtigungen → delegiert
ergänzen: `Mail.Send`, `Mail.ReadWrite.Shared`, `Mail.Send.Shared`
(zusätzlich zu `Mail.ReadWrite`, `Mail.Read`) → **„Administratorzustimmung
für Friondo erteilen“**. Danach im Tool: **Versand → Abmelden → erneut mit
Microsoft anmelden**, damit das Token die neuen Berechtigungen enthält.

## ③ Parametrierung prüfen (Innendienst/Admin)

- **Parametrierung → E-Mail-Versand:** Absender `angebot@friondo.de`,
  Abgleich-Postfach `angebot@friondo.de`, **BCC-Adresse prüfen** (Vorbelegung
  `info@friondo.de`; leer = kein BCC).
- **Parametrierung → monday-Anbindung → Rückspielung:** je Quell-Board Modus
  wählen (Status-Spaltenwert „Angebot versendet“ **oder** Verschieben in die
  Gruppe „Angebot versendet“), Deal-Wert-Spalte (z. B. „Deal-Wert (WP)“) und
  brutto/netto zuweisen. Standard ist **aus** – erst nach bewusster Wahl aktiv.
- **Parametrierung → monday-Anbindung → Spalten-Mapping:** je Board das neue
  Feld **interesse** auf die Spalte „Interessen“ mappen (Board Deals:
  `dropdown_mkyps596`); danach „Jetzt aktualisieren“ in Leads VOT.
- Voraussetzung für beides: `MONDAY_API_TOKEN` in der `.env` auf dem Server.

## ④ E-Mail-Adressen der Benutzer eintragen (Admin)

**Benutzer** → bei jedem Außendienstler die E-Mail hinterlegen (Pflichtfeld für
die Rolle Außendienst) – sie wird beim Versand automatisch als **CC** gesetzt.
Fehlt sie, geht der Entwurf ohne CC raus und das Tool zeigt einen Hinweis.
Bei der Gelegenheit: nicht mehr benötigte Testbenutzer löschen bzw.
deaktivieren.

## ⑤ Vorlagentexte je Außendienstler hinterlegen (Innendienst/Admin)

**Parametrierung → E-Mail-Vorlagen:** Standard-Vorlage prüfen (der bisherige
Festtext ist bereits migriert) und bei Bedarf je Außendienstler eine eigene
Vorlage anlegen (Platzhalter siehe Liste auf der Seite, Vorschau anhand eines
echten Angebots).

## ⑥ Testversand

1. Testangebot an eine **eigene Testadresse** → „Versand vorbereiten“:
   Entwurf in Outlook prüfen – Absender angebot@friondo.de, CC = AD, BCC –
   und senden.
2. Nach spätestens 15 Minuten (oder Server-Neustart) muss der Status
   automatisch auf **„Versendet“** springen; die monday-Rückspielung
   (falls aktiviert) schreibt Status/Deal-Wert an den Test-Deal.
3. Auf die Testmail antworten → in der Angebotsliste erscheint das
   Brief-Symbol mit Zähler, Klick zeigt den Verlauf.
4. Test-Deal in monday zurücksetzen, Testangebot archivieren oder löschen.

## ⑦ Neu in der Logik v5 – bitte beachten

Die Steuerdatei ist jetzt `konfigurator_logik_v5.xlsx`: Im Fragenkatalog gibt
es die neue Frage **A13 „Leitungslänge zwischen Hauseinführung und
WP-Inneneinheit (m)“** (immer, Seite „Alte Anlage“) → Pos. 103 ×
(Eingabe − 5 m, nie unter 0; die ersten 5 m stecken in Pos. 006). Die Fragen
SLS/ÜSS/APZ (E04–E06) werden nicht mehr gestellt. Bereits angelegte
Erfassungen/Angebote bleiben unverändert.

## ⑧ Nachtrag: Leads ausblenden, Vertriebler-Spalte, Anhänge

- **Leads VOT → „Ausblenden“** (mit optionalem Grund) nimmt einen Lead aus der
  Liste, ohne ihn zu löschen; über **Ansicht „Ausgeblendet“** sieht man ihn
  samt Grund und kann ihn **zurückholen**. Der monday-Sync lässt ausgeblendete
  Leads ausgeblendet. Außendienst kann nur eigene Leads ausblenden.
- **Angebotsliste:** neue Spalte **Vertriebler** (über die verknüpfte
  Erfassung), Filter „Alle Vertriebler“ und Sortierung Nummer/Datum/Kunde/
  Vertriebler – kombinierbar mit Suche, Status und Interesse.
- **Versand-Anhänge:** Das Blatt „Anhänge“ der Logik v5 verweist jetzt auf die
  vier Broschüren in `anlagen\`: *Friondo Unternehmenspräsentation.pdf* und
  *Broschüre Ratenkauf.pdf* immer, *Friondo HEMS.pdf* bei P01 = Ja, *Friondo
  SpotDynamic.pdf* bei P03 = Ja. Die PDFs liegen im Repository und kommen mit
  dem Update auf den Server.

## Kurzanleitung Innendienst: Positionen, Preise, Rabatte, bauseits

Im Angebots-Editor (nur Innendienst/Admin):

- **Umsortieren:** Zeile am Griff **☰** ziehen und fallen lassen – das PDF
  folgt exakt der neuen Reihenfolge.
- **Positionsnummer:** Feld „Pos.“ in der Zeile frei ändern (z. B. „010“) und
  mit Enter oder ✓ übernehmen; **„Neu durchnummerieren“** setzt alle Nummern
  wieder auf fortlaufend 001, 002, …
- **Einzelpreis:** Feld „E-Preis“ ändern → Kennzeichen ✎ „manuell geändert“,
  der Originalpreis steht als Tooltip; der Deckungsbeitrag rechnet mit dem
  geänderten Preis.
- **Positionsrabatt:** Wert eintragen und **%** oder **€** wählen; der Abzug
  erscheint unter dem Feld, im PDF als Zeile „abzgl. Rabatt … (− Betrag)“ an
  der Position; er wirkt auf Summen, KfW-Basis und DB. Feld leeren = Rabatt
  entfernen. (Der Gesamt-Rabatt unter der Summe bleibt zusätzlich möglich.)
- **bauseits:** Häkchen in der Zeile → PDF zeigt „bauseits“ statt Preisen,
  die Position zählt weder in Summe noch KfW noch DB (Leistung durch den
  Kunden). Häkchen entfernen macht die Position wieder normal.

---

## Rollout: Entwicklungs-PC → Server

Die Auslieferung läuft über **git push** (PC) und **update.bat** (Server, mit
Backup, getrennten Fehlerpfaden und `rollback.bat`). Der komplette Ablauf
inklusive der einmaligen GitHub-Einrichtung (Repository
`https://github.com/AndyS39/friondo-angebotstool`, PC und Server sind seit
19.08.2026 verbunden) steht in **`docs/updates.md`**. Für dieses Update genügt
auf dem Server: `update.bat` (als Administrator in `C:\Friondo\Angebotstool`).
