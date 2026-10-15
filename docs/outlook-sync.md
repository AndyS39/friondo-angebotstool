# Outlook-Sync je Mitarbeiter (v33, PLAN_V20 Phase 170)

Stand 14.10.2026 (Agent O). Jeder Tool-Termin steht als **Kopie im persönlichen
Outlook-Kalender jeder eingeteilten Person**, weil die bestehende Synchronisation
Outlook → TAIFUN genau diese persönlichen Kalender liest. Änderungen in Outlook
(verschieben, löschen) fließen in das Tool zurück; **Einträge ohne das Kennzeichen des
Tools fasst das Tool nie an** (TAIFUN-Termine, private Termine, Besprechungen) – sie
werden nur als Belegtzeit gelesen. Technik: `app/outlook_sync.py` (Warteschlange, Läufe,
Cache), `app/kalender.py` (VOT), `app/outlook_kalender.py` (Projekt-Termine), Tabellen
`outlook_ereignisse`, `outlook_auftraege`, `outlook_belegt`. Graph-Einrichtung (Modus
„anwendung“, Zugriffsgruppe): `docs/graph-einrichtung.md`.

## 1. Vorab-Abgleich TAIFUN (nur lesend) – noch offen

Bevor die Kopien im Echtbetrieb geschrieben werden, soll im Kalender **eines Monteurs mit
laufendem Outlook→TAIFUN-Abgleich** ein TAIFUN-Termin gelesen werden, um Betreff-Muster,
Kategorie und Kennzeichen zu notieren. Daraus folgt die Regel, ob Tool-Termine für TAIFUN
sichtbar sein sollen. **Stand 14.10.2026: Der Monteur-Name wurde nicht genannt und auf dem
Entwicklungsrechner gibt es keinen Graph-Zugang – der Abgleich wurde deshalb nur vorbereitet
(Handlauf unten), nicht ausgeführt.**

### Vorgehen (Admin auf dem Server, Graph verbunden)

1. Monteur-Postfach (UPN, z. B. `vorname.nachname@friondo.de`) und einen Zeitraum wählen,
   in dem ein TAIFUN-Termin liegt (Standard: heute + 14 Tage).
2. Handlauf ausführen (nur `GET …/calendarView`, keine Speicherung, kein Schreiben):

   ```
   venv\Scripts\python scripts\outlook_abgleich.py --postfach monteur@friondo.de --tage 14
   venv\Scripts\python scripts\outlook_abgleich.py --postfach monteur@friondo.de --tage 14 --muster
   venv\Scripts\python scripts\outlook_abgleich.py --postfach monteur@friondo.de --tage 14 --erweiterungen 5
   ```

   Der Abruf nutzt `$select=id,subject,categories,showAs,isAllDay,start,end,organizer,
   createdDateTime,lastModifiedDateTime,singleValueExtendedProperties` und `$expand` der
   Friondo-Eigenschaft (`friondoTerminId`). `--muster` ersetzt Buchstaben/Ziffern im
   Betreff durch `a`/`0`, damit nur das Muster sichtbar ist (keine Kundendaten im Protokoll);
   `--erweiterungen N` liest zusätzlich die offenen Erweiterungen (`/events/{id}/extensions`)
   der ersten N Einträge – dort hinterlegen Fremdsysteme oft ihr Kennzeichen.
3. Für den TAIFUN-Termin notieren: **Betreff-Muster**, **Kategorie(n)**, **Kennzeichen**
   (Erweiterung / erweiterte Eigenschaft / Betreff-Präfix), **Ersteller** (`organizer`;
   schreibt TAIFUN selbst oder der Monteur?), Frei/Belegt (`showAs`), ganztägig oder mit Uhrzeit.
4. Ergebnis in die Tabelle unten eintragen und Andreas die Entscheidung vorlegen.

### Ergebnis (Platzhalter – nach dem Abruf ausfüllen)

| Feld | TAIFUN-Termin (Beobachtung) | Tool-Termin (aktuell, [ANNAHME]) |
|---|---|---|
| Betreff-Muster | *offen* | `<Art>: <Kunde>, <PLZ Ort> (<Nummer>)` – z. B. `Montage (WP): Müller, 47139 Duisburg (PR-260012)` |
| Kategorie | *offen* | `Friondo-Tool` |
| Kennzeichen | *offen* | erweiterte Eigenschaft `String {7f3a2c1e-5b64-4d8e-9a1f-2c6b8e4d9f10} Name friondoTerminId` = `<art>:<termin_id>:<benutzer_id>` |
| Ersteller | *offen* | Anwendung (Modus anwendung) bzw. angemeldetes Konto (delegiert) |
| showAs | *offen* | `busy` (sichtbar als belegt) |
| Ganztägig/Uhrzeit | *offen* | ganztägige Projekt-Termine als `isAllDay`, sonst mit Uhrzeit |

### Regel-Ableitung

- **TAIFUN soll die Tool-Termine sehen** (gleicher Betreff-Aufbau wie TAIFUN-Termine oder
  TAIFUN liest alle Einträge): Betreff-Muster, Kategorie und `showAs` an das beobachtete
  Muster angleichen (`outlook_sync.betreff_bilden`, `KATEGORIE`, `SHOW_AS`); das
  Friondo-Kennzeichen bleibt zusätzlich.
- **TAIFUN soll die Tool-Termine NICHT sehen** (TAIFUN filtert z. B. nach Kategorie oder
  Präfix): eigene Kategorie `Friondo-Tool` behalten und ggf. `showAs: free` oder ein
  Präfix wählen, das TAIFUN ausschließt.
- **[ANNAHME bis zur Entscheidung Andreas]:** sichtbar, Betreff `<Art>: <Kunde>, <PLZ Ort>
  (<Nummer>)`, Kategorie `Friondo-Tool`, `showAs: busy`. Alle drei Werte stehen als
  Konstanten oben in `app/outlook_sync.py` und sind ohne Datenbankänderung umstellbar.

## 2. Was das Tool schreibt

| Quelle | Personen | Art im Betreff |
|---|---|---|
| VOT-Termine (`vot_termine`, Typ vot/telefon/online) | der Vertriebler (`ad_id`) | `VOT <Sparten>`, `Telefongespräch`, `Teams` |
| Projekt-Termine Montage (WP) / Elektro-Montage / Sub-Einsatz / Service-Einsatz | jede Person der Besetzung `termin_besetzung` (ohne Besetzung: `person_id`) | `Montage (WP)`, `Elektro-Montage`, `Sub-Einsatz`, `Service <Anlass>` (z. B. `Service Wartung`) |
| Feinplanung VOT / Abnahme / Sonstiges | die Person (`person_id`) | `Feinplanung VOT`, `Abnahme`, `Sonstiges` |
| Team-Kalender | nur zusätzlich, wenn `teams.outlook_adresse` gesetzt ist [ANNAHME optional] | wie oben |
| Abwesenheiten/Krankheit, Sperrzeiten der HV | keine Kopie (kommen aus Outlook bzw. nur Tool-Kalender) | – |

**Postfach je Person:** `AdProfil.kalender_postfach`, sonst `Benutzer.email`.
**Handelsvertreter** bekommen nur eine Kopie, wenn `kalender_postfach` gesetzt ist oder ihre
E-Mail in der Friondo-Domain liegt – sonst kein Auftrag und der Hinweis **„HV ohne
Postfach“** am Termin (Terminassistent, Meine Termine, Kartei). **Demo-/Test-Termine**
(`vot_termine.demo`) gehen weiter in das Testpostfach (Parameter `kalender_testpostfach`;
fehlt er, gibt es keinen Auftrag, Hinweis „Testpostfach fehlt“). Der Schalter
`kalender_sync` (Lead-Einstellungen) gilt weiter für VOT-Termine und den Belegt-Abgleich
des Terminassistenten [ANNAHME O]; Projekt-Termine kennen keinen Schalter (wie v15).

**Ereignis-Inhalt:** Betreff nach Regel (Abschnitt 1) – `<Art>: <Kunde>, <PLZ Ort> (<Nummer>)`
mit Nummer = Projektnummer (Projekt-Termine) bzw. TAIFUN-Kundennummer, sonst `V-<Vorgangs-ID>`
(VOT); Service-Einsätze am Vorgang ohne Projekt ohne Nummer (Vorschlag S). Kunde und
Ausführungsort kommen über `projektierung.termin_kunde` / `termin_adresse` (auch bei
`projekt_id 0`). Body mit Kunde, Telefon, Adresse (Ausführungsort), Sparte, Anlass (Service),
Besetzung, Notiz, Steckbrief-Kurzfassung und Link in die Projekt-/Vorgangs-/Lead-Akte
(`BASIS_URL`), `location`, `categories: ["Friondo-Tool"]`, `singleValueExtendedProperties`
`friondoTerminId` = `<vot|projekt>:<termin_id>:<benutzer_id>` (GUID fest im Code),
`showAs: busy`, Zeitzone „W. Europe Standard Time“; ganztägige Projekt-Termine als `isAllDay`.

## 3. Warteschlange und Lauf `outlook-sync` (60 s)

Buchen, Verschieben, Besetzung ändern, Absagen/Stornieren/Löschen laufen **ohne
Graph-Aufruf im Request**: `outlook_sync.auftrag_einreihen(session, aktion, termin_art,
termin_id, benutzer_ids=None)` legt je Kopie einen `OutlookAuftrag` an
(`aktion` anlegen | aendern | loeschen, Status offen | erledigt | fehler) und pflegt die
Zeilen in `outlook_ereignisse` (Stand `ausstehend`). `kalender.termin_schreiben /
termin_aendern / termin_loeschen` und `outlook_kalender.event_senden / event_loeschen`
behalten ihre Signaturen und reihen nur noch ein. Besetzungswechsel: Personen, die nicht
mehr eingeteilt sind, bekommen `loeschen`, neue Personen `anlegen`, bleibende `aendern`.

Der Lauf `outlook-sync` (Scheduler, aktiv nur mit Graph-Konfiguration) liest je Durchlauf bis
zu 50 offene Aufträge in einer kurzen Sitzung (Ereignis-Inhalt wird dabei gebaut), schließt die
Sitzung, ruft je Auftrag Graph (`POST /users/<upn>/events`, `PATCH …/events/{id}`,
`DELETE …/events/{id}`; Modus delegiert: dieselben Pfade über das Token der Anmeldung) und
schreibt in einer neuen kurzen Sitzung: Ereignis `ok` (Event-ID, Zeiten) bzw. Auftrag
`erledigt`; nach **3 Fehlversuchen** Auftrag und Ereignis `fehler` mit Text, Zeile im
Fehlerprotokoll (Quelle „Outlook-Sync“), bei Projekt-Terminen zusätzlich
`projekt_termine.outlook_fehler` („erneut senden“ in der Akte reiht neu ein). HTTP 404 beim
PATCH = Kopie in Outlook schon gelöscht → Stand `in_outlook_geloescht` (Abschnitt 4); 404 beim
DELETE gilt als erledigt. **HTTP 403** = Postfach nicht in der Zugriffsgruppe → der Auftrag
steht sofort auf `fehler` (Text „… nicht in der Zugriffsgruppe …“, Vertrag mit der
Verbindungs-Seite, Abschnitt 6); der Lauf versucht solche Aufträge **stündlich erneut, bis zu
sieben Tage** – sobald die IT das Postfach aufgenommen hat, laufen sie ohne erneutes Speichern
durch. Ein erneutes Speichern des Termins überholt ältere Fehler-Aufträge derselben Kopie (kein
Doppeleintrag). Aufträge für inzwischen gelöschte Termine gelten als erledigt (eine schon
angelegte Kopie wird dabei entfernt); ebenso Aufträge, deren Person nicht mehr eingeteilt ist –
der Lauf prüft das je Auftrag gegen die aktuelle Besetzung, weil SQLite die ID eines gelöschten
Termins neu vergeben kann, und räumt Ereignis-/Auftragszeilen gelöschter Termine stündlich ab
(`verwaiste_aufraeumen`). Ein Altbestand (`outlook_event_id` ohne Ereigniszeile, Stand vor der
Migration) wird beim Einreihen als Kopie aufgenommen, damit Änderung und Löschung ihn erreichen.
Ohne Token (Zustandstext je Modus aus `graph_versand.nicht_verbunden_text`) bleiben die Aufträge
offen – kein Versuch verbraucht. Für Tests und Handläufe: `fremde_auftraege_abschliessen(session,
termin_ids)` markiert offene Aufträge anderer Termine als erledigt. Das alte Feld `outlook_event_id` (vot_termine: `postfach|id`, projekt_termine:
`id`) spiegelt die **erste Kopie** mit Stand ok; Wahrheit ist `outlook_ereignisse`.

**Anzeige:** Makro `templates/_outlook_status.html` (`outlook_status(stand)`, Stände
ausstehend · ok · Fehler · gelöscht · in Outlook gelöscht · kein Eintrag) über
`outlook_sync.status_fuer(session, termin_art, termin_id) -> {stand, text, kopien}` bzw.
`status_map` / Template-Global `outlook_status_map` – Terminassistent (Block „Outlook“),
Meine Termine, Projektierung → Termine, Projektakte (Agent S), Deals-Board (Fußzeile).

## 4. Rücklesen – Lauf `outlook-ruecklesen` (300 s)

Je Person mit Terminen in den nächsten **8 Wochen** (VOT-Termine, Besetzung/Person der
Projekt-Termine, bekannte Kopien) liest der Lauf `GET /users/<upn>/calendarView?startDateTime
&endDateTime&$top=500&$select=id,start,end,subject,showAs,isCancelled,isAllDay,
singleValueExtendedProperties&$expand=singleValueExtendedProperties($filter=id eq '…')`
(seitenweise über `@odata.nextLink`), danach in einer kurzen Sitzung je Person:

- **Tool-Kopie mit verändertem Zeitraum** → Tool-Termin nachziehen (`vot_termine.beginn/ende`
  bzw. `projekt_termine.beginn/ende/dauer_tage`, Fälligkeiten bei Feinplanung/Montage),
  Verlauf bzw. Aktivität **„Termin aus Outlook übernommen von <Name>: alt → neu“**; bei
  mehreren Personen gewinnt die erste Änderung, die übrigen Kopien werden per Auftrag
  `aendern` angeglichen. Kundenmails (Terminänderung) werden dabei **nicht** ausgelöst.
- **Tool-Kopie fehlt** (in Outlook gelöscht oder abgesagt) → Ereignis `in_outlook_geloescht`,
  Termin im Tool bleibt bestehen und wird markiert (VOT: `grund_text` + Aktivität; Projekt:
  `outlook_fehler = "in Outlook gelöscht"` + Verlauf) und **Glocke** an den
  Projektverantwortlichen/Ersteller (Art `kommentar`) bzw. den Leadmanager (Art
  `terminaenderung`, nur wenn in `glocke_lead_arten` erlaubt – die Aktivität bleibt immer).
  Kein stilles Löschen; wer den Termin wirklich absagen will, tut das im Tool.
- **Fremde Einträge** (ohne Kennzeichen, nicht `free`, nicht abgesagt) → nur Belegtzeit im Cache
  `outlook_belegt` (Person, von, bis, Event-ID, Stand); der Block je Person wird je Lauf ersetzt.
  Betreffs fremder Einträge werden nicht gespeichert.
- **403** → Postfach in der Liste `postfaecher_ohne_zugriff` (Abschnitt 6), Person wird
  übersprungen. Andere Fehler zählen als `fehler` im Lauf-Ergebnis.

Die alte Funktion `outlook_kalender.ruecklesen()` (Teilschritt des Laufs `mail-sync`) ruft den
neuen Lauf auf (Rückgabe: Anzahl geänderter Termine) und überspringt, wenn der registrierte
Lauf gerade arbeitet.

## 5. Belegt-Cache

`outlook_sync.belegt(session, benutzer_ids, von, bis) -> {benutzer_id: [(von, bis), …]}`
liest ausschließlich `outlook_belegt` (Vertrag für `/kalender`, Phase 169).
`kalender.frei_belegt(session, ad, von, bis)` bleibt als Funktion erhalten und liest denselben
Cache (`outlook_sync.belegt_fuer`: None bei `kalender_sync = aus` oder HV ohne Postfach); der
Terminassistent (`lead_termin.vorschlaege`, `konflikte`, `kalender_woche`, `kalender_json`)
nutzt den Cache direkt – **kein Graph-Aufruf im Request** mehr. Der Cache ist höchstens
fünf Minuten alt (Intervall des Rücklese-Laufs); ohne Graph-Verbindung ist er leer (Assistent
rechnet nur mit Tool-Terminen, wie bisher ohne Berechtigung).

## 6. Zugriffsgruppe pflegen (403)

Liefert ein Postfach HTTP 403, ist es nicht in der Exchange-Zugriffsgruppe
`friondo-tool-zugriff@` (Modus anwendung, `docs/graph-einrichtung.md`). `graph_versand`
schreibt das einmal je Postfach und Stunde ins Fehlerprotokoll;
`outlook_sync.postfaecher_ohne_zugriff(session) -> [{benutzer_id, name, postfach, zeit}]`
listet die betroffenen Personen für die Verbindungs-Seite (`/versand`, Agent G, mit
Kopierliste für die IT). Quellen der Liste: die Aufträge in `outlook_auftraege` mit Status
`fehler` und dem Text „nicht in der Zugriffsgruppe“ (dauerhaft, auch nach einem Neustart;
letzte sieben Tage), die 403 des Rücklese-Laufs (im Speicher, füllt sich alle fünf Minuten neu)
und die 403-Liste von `graph_versand` (andere Module). Ein späterer erfolgreicher Auftrag
desselben Postfachs nimmt es aus der Liste; die fehlgeschlagenen Aufträge werden stündlich
erneut versucht (Abschnitt 3), „erneut senden“ / erneutes Speichern reiht sofort neu ein.

## 7. Altbestand (Migration `outlook_sync.migration_v33_outlook`)

`migrate.py` spiegelt vorhandene `outlook_event_id`-Werte als `outlook_ereignisse` mit Stand
ok: VOT-Termine (Person = `ad_id`, Postfach aus `postfach|id`), Projekt-Termine als Kopie im
bisherigen Team-/Sammelkalender (`benutzer_id 0`, Adresse aus `teams.outlook_adresse` bzw.
`outlook_kalender_adresse`). So kennen Rücklesen und Änderungen die alten Einträge; beim
nächsten Speichern eines alten Projekt-Termins bekommen die eingeteilten Personen zusätzlich
ihre persönlichen Kopien. Die Migration ist idempotent (zweiter Lauf ohne Meldung); Einträge
ohne zuordenbares Postfach (Team ohne Outlook-Adresse) werden gezählt, nicht gespiegelt.

## 8. Betrieb

- Läufe: `outlook-sync` 60 s (Start +60 s), `outlook-ruecklesen` 300 s (Start +330 s), beide
  „inaktiv (Graph nicht eingerichtet)“ ohne `GRAPH_CLIENT_ID`; Betriebs-Seite „jetzt ausführen“.
  Pool-Invariante mit 16 Läufen: 64 Threads + 16 + 5 = 85 ≤ 90 (Pool 20 + 70).
- Parameter: `kalender_sync` (VOT-Schalter, Lead-Einstellungen), `kalender_testpostfach`
  (Demo-/Test-Termine), `outlook_kalender_modus`/`outlook_kalender_adresse` (nur noch für den
  Altbestand), `teams.outlook_adresse` (optionale Team-Kopie), `glocke_lead_arten`
  (Glocke „in Outlook gelöscht“ an den Leadmanager).
- Prüfpunkte nach dem Update: Verbindungs-Seite grün, Betriebs-Seite beide Läufe „ok“,
  Deals-Board-Fußzeile „0 Aufträge offen“, in der Projektakte ein frisch angelegter Termin nach
  einer Minute „Outlook: ok (n Kopien)“; TAIFUN-Termine im selben Kalender bleiben unberührt.
- Störungen: Stand „Fehler“ am Termin → Fehlerprotokoll (Quelle „Outlook-Sync“) lesen,
  Ursache beheben (Postfach in die Gruppe, E-Mail am Benutzer), Termin erneut speichern bzw.
  „erneut senden“. Stand „in Outlook gelöscht“ → Termin im Tool prüfen und bewusst verschieben
  oder absagen; erneutes Speichern legt die Kopie neu an.

## 9. Tests

`tests/test_v33_outlook.py` (Graph gemockt: `graph_versand._token` und `_graph_aufruf`):
Montagetermin mit zwei Monteuren → zwei Aufträge → zwei Ereignisse mit Kennzeichen; Monteur
getauscht → eine Kopie gelöscht, eine neu; Verschieben im Tool → alle Kopien PATCH; Verschieben
in Outlook → Tool-Termin nachgezogen, zweite Kopie angeglichen, Verlauf; Löschen in Outlook →
Stand + Glocke; fremder Termin → nur Belegtzeit, nie PATCH/DELETE; VOT-Demo → Testpostfach; HV
ohne Postfach → kein Auftrag + Hinweis; 403 → Liste; Läufe registriert; Migration zweimal;
Sitzungsdisziplin (keine Pool-Verbindung während der gemockten Graph-Aufrufe, Wächter-AST
`tests/test_v27_sitzungen.py`, `tests/test_pool_hotfix_mail.py`).
