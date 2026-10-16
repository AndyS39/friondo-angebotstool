# TAIFUN-Kundenübergabe (XML-Export nach ADRESSEN.xsd) – v35, PLAN_LEAD_V6 Phase 183

Stand 16.10.2026 (Agent T; Nachtrag 3 nach dem Screenshot-Review von Claudia Castro, PLAN_LEAD_V6_1).
Bei der **Terminierung** eines Leads schreibt das Tool den Kunden **automatisch** als XML-Datei in den
Import-Ordner von TAIFUN. TAIFUN liest die Datei (Import „Adressen“) und legt den Kunden an. Einen
manuellen Knopf „An TAIFUN übergeben“ in der Kundenkartei gibt es seit dem Nachtrag 16.10.2026 **nicht
mehr**; eine Wiederholung nach Fehler oder eine erneute Übergabe läuft ausschließlich über die
**Übergabeliste** (`/lead-management/taifun-uebergaben`, Knopf „Erneut übergeben“ je Zeile).
Technik: `app/taifun_export.py` (Generator, Validierung, Datei, Übergabeliste, Scheduler-Lauf),
`app/routers/lm_taifun.py` (Routen), Schema `docs/taifun/ADRESSEN.xsd`, Beispiel
`docs/taifun/beispiel_LM.xml`, Tabelle `taifun_uebergaben`, Vorgangsfelder
`vorgaenge.taifun_export_am/_von/_datei/_status/_grund`. Die Spalte `kunden.taifun_kundennr` (v35)
bleibt additiv in der Datenbank, wird aber nicht mehr angezeigt oder gelesen (kein Kartei-Feld mehr,
Rückgabe der Kundennummer bleibt OFFEN 2).

**Schalter:** Lead-Einstellungen → „TAIFUN-Übergabe“ → `taifun_export_aktiv`, Standard **aus**
(Andreas 15.10.2026), bis der Import-Weg mit dem TAIFUN-Betreuer geklärt ist. Mit „aus“ erzeugt
die Terminierung keine Datei (nur die Aktivität „TAIFUN-Übergabe nicht aktiv“), die Übergabeliste
zeigt keine „Erneut übergeben“-Knöpfe; **„Testdatei schreiben“ funktioniert immer.**

## 1. Datei

| Punkt | Regel |
|---|---|
| Ordner | Parameter `taifun_import_ordner`, Standard `C:\Users\kdadmin\Desktop\LM Datenimport` |
| Dateiname | `LM_<Vorgang>_<JJJJMMTT-HHMMSS>.xml`, z. B. `LM_V4711_20261015-101500.xml` (nur A–Z, 0–9, `_`, `-`); Testdatei `LM_TEST_<Zeit>.xml` |
| Inhalt | XML-Deklaration `encoding="windows-1252"` (Parameter `taifun_export_encoding`, Alternative `utf-8`), Wurzel `<TAIFUN:AdList xmlns:TAIFUN="urn:taifun-software.de:schema:TAIFUN">`, **genau ein** `<TAIFUN:Ad>` je Datei, Elemente in Schema-Reihenfolge, leere Felder weggelassen, Umlaute/ß als Zeichen |
| Validierung | vor dem Schreiben gegen `docs/taifun/ADRESSEN.xsd` (lxml); Fehler → Status `fehler`, nichts geschrieben |
| Schreiben | atomar: `<Datei>.tmp` im Zielordner, dann Umbenennen; eine vorhandene Datei wird nie überschrieben |
| Kopie | `data/taifun_export/<Datei>` als Protokoll (12 Monate, Löschlauf im Scheduler-Lauf) |
| Längen | Name 60 · Straße 60 · Hausnummer 20 · PLZ 10 · Ort 60 · Briefanrede 200 · E-Mail 80 · Telefon/Mobil 30 – längere Werte werden gekürzt, Hinweis in Karteikarte und Aktivität |

## 2. Feldzuordnung Lead → Ad

| Element | Quelle im Tool | Regel |
|---|---|---|
| `KdUse` | – | immer `true` (Kunde) |
| `Name3` | `kunden.vorname` + `kunden.nachname` | „Vorname Nachname“; nur Nachname ohne Vorname; **Firma** (`kunden.firma`) bei Firmen-/Großkunden [ANNAHME] |
| `AnschriftStr` / `AnschriftHNr` | Straßenfeld der Adresse | Trennung mit der Parser-Logik (letzter Block Ziffer + Zusatz: „36“, „12a“, „63-65“); nicht sicher erkennbar → Hausnummer leer, ganzes Feld in `AnschriftStr`, Hinweis in der Karteikarte |
| `AnschriftPLZ` / `AnschriftOrt` | **abweichende Rechnungsadresse** (MFH: `kunden.rechnung_*` bei „Rechnungsadresse identisch? = Nein“, bzw. `vorgang_objekte.rechnung_*` eines weiteren Objekts), sonst Hauptobjekt = Kundenadresse | [ANNAHME: TAIFUN-Kunde = Rechnungsempfänger; Objektadressen stehen in der Karteikarte] |
| `Anrede` | Briefanrede (`mail_vorlagen.briefanrede`) | „Sehr geehrter Herr Schliwa,“ / „Sehr geehrte Frau …,“ / „Sehr geehrte Familie …,“ / Fallback „Sehr geehrte Damen und Herren,“ |
| `EMail` | `kunden.email` | nur wenn `vorgaenge.email_status` nicht `ungueltig` (v29 Bounce); sonst leer + Hinweis |
| `Telefon` / `Funk` | `kunden.telefon` | deutsche Mobilvorwahl 015x/016x/017x (bzw. +4915/16/17) → `Funk`, alle anderen → `Telefon`; national formatiert „0203 3965710“ / „0171 1234567“ [ANNAHME Schreibweise]; zwei Nummern im Feld („0203 …, 0171 …“) → beide |
| `Kartei` | zusammengesetzt | mehrzeilig (LF), Reihenfolge: „Übergabe aus dem Friondo-Tool am TT.MM.JJJJ HH:MM durch <Benutzer>“ · „Lead/Vorgang: V<ID>“ · „Vertriebskanal: …“ · „Interessen: <Langnamen>“ · „Objekt[ n]: <Objektart (Parteien)>, <Adresse>“ je Objekt · „Vertriebler: …“ · „Vor-Ort-Termin: [vorgemerkt: ]TT.MM.JJJJ HH:MM (<Objekt>)“ je Termin · „Quelle: <Quelle / Kampagne>“ · „Großkunde: ja“ · „Hinweis: …“ (Kürzungen, Parser, E-Mail). Keine Notizen, Anrufprotokolle oder Preise. |

Beispiel (Demo-Lead, keine Kundendaten): `docs/taifun/beispiel_LM.xml`

```xml
<?xml version="1.0" encoding="windows-1252"?>
<TAIFUN:AdList xmlns:TAIFUN="urn:taifun-software.de:schema:TAIFUN">
  <TAIFUN:Ad>
    <TAIFUN:KdUse>true</TAIFUN:KdUse>
    <TAIFUN:Name3>Max Mustermann</TAIFUN:Name3>
    <TAIFUN:AnschriftStr>Musterstraße</TAIFUN:AnschriftStr>
    <TAIFUN:AnschriftHNr>1</TAIFUN:AnschriftHNr>
    <TAIFUN:AnschriftPLZ>47051</TAIFUN:AnschriftPLZ>
    <TAIFUN:AnschriftOrt>Duisburg</TAIFUN:AnschriftOrt>
    <TAIFUN:Anrede>Sehr geehrter Herr Mustermann,</TAIFUN:Anrede>
    <TAIFUN:EMail>max.mustermann@example.com</TAIFUN:EMail>
    <TAIFUN:Telefon>0203 1234567</TAIFUN:Telefon>
    <TAIFUN:Funk>0171 1234567</TAIFUN:Funk>
    <TAIFUN:Kartei>Übergabe aus dem Friondo-Tool am 15.10.2026 10:15 durch Max Innendienst
Lead/Vorgang: V4711
Vertriebskanal: Website
Interessen: Wärmepumpe
Objekt: Einfamilienhaus, Musterstraße 1, 47051 Duisburg
Vertriebler: Horst Beispiel
Vor-Ort-Termin: vorgemerkt: 22.10.2026 10:00
Quelle: Website/Förderrechner</TAIFUN:Kartei>
  </TAIFUN:Ad>
</TAIFUN:AdList>
```

## 3. Auslöser, Rückfragen, Status

- **Terminierung** (Kundenkartei, Knopf oben rechts): nach erfolgreicher Pflichtfeldprüfung (inkl.
  vorgemerktem Termin, Kanal nicht „?“) wird die Datei geschrieben – **auch in der Testphase**
  (`terminierung_aktiv = aus`): der Knopf ist dann aktiv mit Tooltip „Testphase: nur Übergabe an
  TAIFUN, keine Buchung, keine Mail“; Buchung, Outlook, Mail, Phase Terminiert und Leads VOT bleiben
  gesperrt. Bei freigeschalteter Terminierung laufen Export und Buchung in einem Klick; ein
  Export-Fehler blockiert die Buchung nicht [ANNAHME].
- **Kein manueller Knopf in der Kartei** (Nachtrag 16.10.2026): die Übergabe läuft nur automatisch bei
  „Terminierung“. Wiederholung/erneute Übergabe ausschließlich in der **Übergabeliste** (Innendienst/
  Leadmanagement/Admin): Knopf **„Erneut übergeben“ je Zeile** mit Rückfrage „Letzte Übergabe am
  TT.MM.JJJJ HH:MM – trotzdem erneut übergeben? Doppelte Kunden in TAIFUN vermeiden.“ (Route
  `POST /lead-management/lead/{id}/taifun` mit `bestaetigt=1`, Rücksprung über das Formularfeld `zurueck`
  auf die Liste; ohne JavaScript zeigt die Liste den Rückfrage-Balken „Trotzdem übergeben“).
- **Dubletten-Hinweis** vor jedem Export: externer TAIFUN-Eintrag mit Nummer (v7) oder Bestandsimport
  (v18) – **nicht mehr** die manuelle Kundennummer → „Kunde ist vermutlich schon in TAIFUN angelegt
  (<Beleg>). Trotzdem übergeben?“. Die Terminierung überspringt den automatischen Export in diesem Fall,
  schreibt eine Aktivität und eine Zeile **„übersprungen (Rückfrage)“** in die Übergabeliste; dort steht
  „Trotzdem übergeben“ (bewusste Entscheidung, [ANNAHME N6: ohne Zeile gäbe es keinen Weg mehr, den
  Dubletten-Hinweis zu übergehen]).
- **Nach Erfolg:** grünes Badge „TAIFUN <Datum>“ im Kartei-Kopf (ohne Kundennummer), Aktivität
  „An TAIFUN übergeben: <Datei>“, Spalte „TAIFUN-Übergabe“ (Boards, Standard ausgeblendet), Filter-Chip
  „an TAIFUN übergeben“. Keine Glocke, keine Kundenmail.
- **Fehler** (Ordner fehlt, keine Rechte, Validierung): `taifun_export_status = fehler` mit Grund,
  rotes Label „TAIFUN-Übergabe fehlgeschlagen“ in Notiz-Spalte (Rang 0) und Kartei (Hinweisbalken
  mit dem Link „Zur Übergabeliste“, Filter „Fehler“), Zähler in den Lead-Einstellungen.
- **Übergabeliste** `/lead-management/taifun-uebergaben`: Datum, Vorgang, Datei, Benutzer, Auslöser,
  Status `geschrieben · abgeholt · fehler · manuell importiert · übersprungen (Rückfrage)`, Knöpfe „XML“,
  „Als importiert markieren“, „Erneut übergeben“ bzw. „Trotzdem übergeben“. Der Scheduler-Lauf
  `taifun-uebergaben` (alle 15 Minuten) setzt `abgeholt`, sobald die Datei nicht mehr im Ordner liegt
  (ein nicht erreichbarer Ordner markiert nichts), und löscht Kopien älter als 12 Monate.
- **Kundennummer:** kein Feld in der Kartei mehr (Nachtrag 16.10.2026); die Rückgabe der TAIFUN-Kundennummer
  ins Tool bleibt OFFEN 2.

## 4. Ordner und Rechte des Dienstkontos (OFFEN 3, IT)

Das Tool läuft auf dem Server als **Dienst `FriondoAngebotstool` unter dem Konto SYSTEM** (v27,
`scripts\dienst-installieren.bat`). Der Standardpfad `C:\Users\kdadmin\Desktop\LM Datenimport`
liegt im Benutzerprofil `kdadmin`:

1. Liegt der Ordner **auf dem Server selbst**, braucht SYSTEM Schreibrecht auf den Ordner
   (NTFS: `SYSTEM` → Ändern) – „Ordner prüfen“ in den Lead-Einstellungen bestätigt das.
2. Liegt der Ordner **auf einem anderen Rechner** (TAIFUN-Arbeitsplatz), muss er freigegeben und als
   UNC-Pfad eingetragen werden (`\\<Rechner>\LM Datenimport`); das Computerkonto des Servers
   (`<SERVER>$`) bzw. ein Dienstkonto braucht Schreibrecht auf Freigabe und NTFS. Ein als SYSTEM
   laufender Dienst sieht keine gemappten Laufwerksbuchstaben – immer UNC.
3. Nach jeder Änderung: Lead-Einstellungen → „Ordner prüfen“ (schreibt und löscht
   `LM_PRUEF_<Zeit>.tmp`) und „Testdatei schreiben“, dann die Datei in TAIFUN importieren.

Prüfpunkte Go-live (Lead-Einstellungen): Ordner erreichbar · Testdatei in TAIFUN importiert
(Häkchen) · Encoding bestätigt (Häkchen) · keine Übergaben mit Fehler. Erst danach Schalter „an“.

## 5. Fragen an den TAIFUN-Betreuer (OFFEN 1)

1. Liest TAIFUN den Ordner **automatisch** (Dienst/Zeitplan) oder startet ein Mitarbeiter den
   Import von Hand? Wird die Datei nach dem Import gelöscht/verschoben (das Tool wertet eine
   verschwundene Datei als „abgeholt“)?
2. **Dubletten:** Was passiert, wenn der Kunde (Name + Adresse) schon existiert – neue Adresse,
   Aktualisierung, Abbruch? Gibt es ein Schlüsselfeld für den Abgleich?
3. **Kundennummer zurück:** Kann TAIFUN die vergebene Kundennummer zurückgeben (Export-Datei,
   Abfrage)? (Ein manuelles Feld gibt es seit dem Nachtrag 16.10.2026 nicht mehr; die Spalte
   `kunden.taifun_kundennr` bleibt ungenutzt in der Datenbank.)
4. **Kodierung:** Erwartet der Import `windows-1252` (wie die XSD) oder UTF-8? Bleiben Umlaute/ß
   nach dem Import korrekt? (Parameter `taifun_export_encoding`.)
5. **Original-XSD:** Bitte die Original-`ADRESSEN.xsd` liefern – `docs/taifun/ADRESSEN.xsd` ist eine
   Rekonstruktion aus dem Plan (Reihenfolge, Längen) und wird 1:1 ersetzt.
6. Gibt es ein **Muster-XML** eines erfolgreichen Imports (Telefon-Schreibweise, Zeilenumbrüche in
   der Karteikarte, Mehrfach-Ad je Datei)?
7. Darf eine Datei mehrere `Ad`-Einträge enthalten (heute: genau einer je Datei)?

## 6. Betrieb (Inventar `docs/betrieb.md`)

| Modul | Auslöser | Intervall | Netz/Datei-I/O | Sitzung | Maßnahme |
|---|---|---|---|---|---|
| `taifun_export.exportieren` (Routen `…/terminierung` automatisch; `POST /lead-management/lead/{id}/taifun` nur aus der Übergabeliste „Erneut übergeben“) | Innendienst/LM/Admin | je Übergabe | Datei schreiben (Zielordner, ggf. UNC) + Kopie | Request-Sitzung vor dem Schreiben freigegeben (`verbindung_freigeben`), danach kurze Schreibtransaktion | def-Route, atomar, nie überschreiben |
| `taifun_export.scheduler_lauf` – Lauf `taifun-uebergaben` | Scheduler | 900 s (Start +240 s) | `Path.exists()` je offener Übergabe, Kopien > 365 Tage löschen (03:00–03:20) | `db.kurz(schreibend=False)` lesen → Datei-I/O ohne Sitzung → `db.kurz()` je Block ≤ 50 | Pool-Invariante: 17 Läufe → 64 + 17 + 5 = 86 ≤ 90 |
| `POST /lead-management/taifun/testdatei`, `…/ordner-pruefen` | Admin | manuell | Testdatei bzw. `LM_PRUEF_*.tmp` | Sitzung vorher freigegeben | – |
