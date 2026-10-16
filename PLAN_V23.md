# Umsetzungsplan v23: Foto-Upload (Pop-up, Offline-Zwischenspeicher, Mehrfach-Löschen), Erfassung (Zwischenspeichern, Korrektur nach Senden), Leads VOT (Kanal-Pfeil, Gruppe „Vergangene Termine"), Mobil (Reiter „Vergangene Termine", Erfassungsliste mit Objekt, Dialog „Termin nicht stattgefunden")

> **Prüfvermerk 16.10.2026 (Claude Code, Vorprüfung der Plan-Kette):** Der Entwurf nannte **v37 und Phasen 192–196**
> – beides war belegt (v37 = PLAN_LEAD_V7 mit 196–200, 192–195 = PLAN_V22 Teil B). Nach der Plan-Regel „nächste freie
> Nummern, durchgängig ersetzen“ gilt **v38 mit Phasen 201–205** (auch `docs/design-v38/`, `docs/nach-dem-update-v38.md`,
> `tests/test_v38_*.py`, `config.VERSION = "v38"`). Reihenfolge laut Andreas: nach PLAN_LEAD_V7 (v37). Die Objektfotos
> aus PLAN_LEAD_V6 sind mit dessen Nachtrag 16.10. entfallen – der Regressionstest in Phase 205 entfällt (Rückfrage).

**Fassung 16.10.2026, Entwurf Claudia Castro (Planungs-Chat Angebotstool) aus
den Punkten von Andreas und ihren Entscheidungen vom 16.10.2026.**

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand
16.10.2026 (Vorprüfung der Plan-Kette): v34 (PLAN_V21) und v35 (PLAN_LEAD_V6) sind gebaut, v36
(PLAN_V22) und v37 (PLAN_LEAD_V7) stehen in der Kette davor. **Dieser Plan kommt nach v37**
(Reihenfolge laut Andreas) und setzt auf dessen committetem Stand auf. Er braucht aus v31/v35 die
Objekte am Vorgang (PLAN_LEAD_V5/V6 – die Objekt-Ordner der Galerie sind mit dem Nachtrag 16.10.
zu PLAN_LEAD_V6 entfallen), aus
v33 „Mein Tag" nach Design-Entwurf, die untere Leiste und die Leads-VOT-
Tabelle mit Gruppen (PLAN_V20, Phasen 173/174) und aus v34 den Galerie-
Mehrfachupload mit Upload-Liste, Knopf „n Fotos hochladen" und Kamera-Serie
(PLAN_V21, Phase 181). **Nichts davon wird hier neu gebaut, nur erweitert.**
Vor der Übergabe fragt der Planungs-Chat erneut ab, ob v33 bis v37 committet,
gepusht und auf dem Server sind. CLAUDE.md und `konfigurator_logik_v5.xlsx`
sind Live-Master im Projektordner `C:\Users\a.scheelen\Tools\Angebotstool`
(Git-Arbeitskopie). ALLE PHASEN DIESES PLANS IN EINEM DURCHLAUF UMSETZEN
(Reihenfolge einhalten, jede Checkbox nach Umsetzung und Test abhaken, am
Ende Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche
Rückfragen gebündelt). **Ein gemeinsamer Commit am Ende**, migrate.py
idempotent, **nur additive Migrationen** (v37-Code muss auf der v38-Datenbank weiterlaufen, Rückweg `rollback.bat --nur-code`). **Kein git push vor
Freigabe.**

CLAUDE-Abschnitt: **„Neu in v38"** (geprüft 16.10.2026: v34 = PLAN_V21, v35 = PLAN_LEAD_V6, v36 =
PLAN_V22, v37 = PLAN_LEAD_V7 – v38 ist die nächste freie Nummer). Phasen **201 bis 205** (geprüft:
188–195 gehören zu PLAN_V22 und 196–200 zu PLAN_LEAD_V7; die im Entwurf genannten 192–196 waren
belegt und sind durchgängig ersetzt). Die
v27-Regeln gelten (`def`-Routen, keine offene Datenbanksitzung während
Datei- oder Netz-I/O, `_speichern`-Muster für schreibende Routen, Wächter-
Test `tests/test_v27_sitzungen.py` grün, Inventartabelle `docs/betrieb.md`),
die v30-Regeln für Oberflächen (Tokens Hell/Dunkel, Token-Wächter
`tests/test_v30_design.py`, `tojson | forceescape` in on*-Attributen,
Zurück-Leiste aus `base.html`) und die v33-Tabellenregeln für Listen.

Geltungsbereich: Angebotstool. Galerie (`_galerie.html`, `app/galerie.py`,
Upload-Liste aus v34) in Vorgangsakte, Projektakte, Montage-Backend und
mobiler Erfassung; Erfassungsbogen (`/erfassung/…`, `pruefen`, `absenden`)
und Erfassungsliste (`/erfassungen`, mobil und Desktop); Leads VOT Desktop
(`routers/leads.py`, Template aus v33 Phase 174) und „Mein Tag" mobil
(`mein_tag.py`, untere Leiste aus v33 Phase 173). **Nicht berührt:**
Konfiguratoren, Angebots-PDF, Versand, monday-Sync, Lead-Management-Boards,
Terminassistent, Kaskade, Projektierung, Cloover (v36). **Außendienst sieht
weiterhin nie EK oder DB.** Live-Kamera im Browser, Diktat per Browser und
jede Funktion, die HTTPS braucht, bleiben außerhalb dieses Plans
(Entscheidung Andreas/IT, `docs/https-intern.md`).

## Entscheidungen (Claudia Castro, 16.10.2026)

- **Großkunden, Fotos je Objekt:** waren in PLAN_LEAD_V6 (v35, Phase 186) gebaut und sind mit dem
  Nachtrag 16.10. zu PLAN_LEAD_V6 (PLAN_LEAD_V6_1, Screenshot-Review Claudia Castro) wieder
  entfallen – der hier vorgesehene Regressionstest entfällt damit (Vorprüfung der Plan-Kette
  16.10.2026, Rückfrage in der Gesamtübersicht).
- **Kamera-Serie ohne Rückkehr ins Tool:** ohne HTTPS nicht möglich (die
  Kamera-App des Handys gibt nach jedem Foto zurück). Arbeitsweise bleibt wie v34: Fotos in der Kamera-App am Stück aufnehmen, danach alle per
  Galerie-Mehrfachauswahl hochladen. Keine Änderung in diesem Plan.
- **Upload-Bestätigung:** Knopf „Hochladen" (ersetzt die Beschriftung „n
  Fotos hochladen" aus v34, Zähler bleibt als Zusatz „(3)"), danach Pop-up
  mit geschätzter Dauer, am Ende Erfolgs- oder Fehlermeldung.
- **Offline:** Schlägt der Upload wegen fehlendem Netz fehl, bleiben die
  Fotos im Browser-Speicher des Handys; beim nächsten Öffnen der Seite mit
  Netz erscheint „n Fotos warten auf Upload" mit Knopf „Jetzt hochladen".
  Die Erfassung selbst lässt sich ohne Netz nicht öffnen (kein Service
  Worker ohne HTTPS).
- **Mehrfach-Löschen:** Kästchen je Foto, Knopf „n Fotos löschen" mit
  Sicherheitsabfrage, Rechte wie heute (Hochladender, Innendienst, Admin),
  überall, wo die Galerie ist [ANNAHME bestätigt].
- **Erfassung zwischenspeichern:** Claude Code stellt zuerst fest, was heute
  beim Verlassen des Bogens passiert (Befund in die Gesamtübersicht), und
  sorgt danach dafür, dass keine Antwort verloren geht und ein sichtbarer
  Weg „Zwischenspeichern und später fortsetzen" existiert.
- **Korrektur nach „Senden":** Außendienst nur eigene Erfassungen,
  Innendienst und Admin alle. Jede Korrektur erzeugt einen Eintrag im
  Notizen-Chat des Vorgangs „Erfassung nachträglich geändert" mit den
  geänderten Fragen. Zeitgrenze [ANNAHME]: bis das zugehörige Angebot
  „Versand vorbereitet" ist; existiert schon ein Angebotsentwurf, erscheint
  der Hinweis „Angebot neu berechnen".
- **Kanalspalte Leads VOT:** Dropdown entfällt, stattdessen kleiner Pfeil
  rechts neben dem Farblabel, der die Auswahl öffnet. Vorerst nur in Leads
  VOT (Kundenliste und Kundenkartei unverändert).
- **Vergangene Termine:** Desktop Leads VOT bekommt eine eigene auf- und
  zuklappbare Gruppe „Vergangene Termine" (letzte 180 Tage). Mobil bekommt
  die untere Leiste den Reiter „Vergangene Termine" **statt** „Kunden"
  (die allgemeine Suche bleibt über die Lupe im Hauptmenü, v32 Phase 164
  erreichbar). Das rote Label „überfällig" und die Einsortierung
  überfälliger Termine in „Heute" (v32/v33) entfallen; vergangene Termine
  stehen nur noch in der neuen Gruppe bzw. im neuen Reiter.
- **Erfassungsliste mobil:** jede Erfassung zeigt Objektbezeichnung (v31
  `vorgang_objekte`) und Objektadresse, vor allem bei Großkunden mit
  mehreren Objekten.
- **Termin nicht stattgefunden (Nachtrag 16.10.2026):** Der Vertriebler
  kann an jedem Termin „Termin nicht stattgefunden" melden, mit Grund
  (Kunde nicht angetroffen, Kunde hat sich anders entschieden, Sonstiges).
  Wünscht der Kunde einen neuen Termin, geht ein To-Do an den dem
  Vorgang zugewiesenen Innendienstler zur neuen Terminfindung. Möchte der
  Kunde keinen neuen Termin, disqualifiziert der Vertriebler den Kunden
  direkt; dabei geht keine E-Mail an den Kunden (eine Mail gibt es nur bei
  „nicht erreicht" nach dem letzten Anrufversuch). Nur diese zwei Wege.

## Phase 201: Foto-Upload mit Bestätigung, Pop-up, Offline-Zwischenspeicher, Mehrfach-Löschen

Baut auf der Upload-Liste aus v34 (Phase 181) auf: Vorschauliste mit
Ordner-Dropdown je Datei, ein Request `POST /vorgaenge/<id>/galerie/upload`
mit `dateien[]`, `ordner[]`, `bemerkung[]`, client-seitige Verkleinerung
auf 2.000 px, Teilerfolg je Datei. Gilt in Vorgangsakte, Projektakte,
Montage-Backend und mobiler Erfassung (auch ohne Auftrag).

- [ ] **Knopf „Hochladen":** Der Knopf der Upload-Liste heißt **„Hochladen
      (n)"** (n = Anzahl Fotos in der Liste, bei 0 deaktiviert). Vor dem
      Senden erscheint ein Pop-up (Makro `galerie_upload_dialog`, Design-v2-
      Tokens, auch unter 390 px lesbar) mit: Titel „Fotos werden hochgeladen",
      Fortschrittsbalken je Datei und gesamt, Zeile **„Voraussichtlich noch
      ca. 20 Sekunden"**. Schätzung: vor dem Senden aus der Gesamtgröße der
      verkleinerten Dateien und einem Startwert von 500 KB/s [ANNAHME];
      nach der ersten fertigen Datei wird die gemessene Geschwindigkeit
      genommen und die Anzeige alle 2 Sekunden aktualisiert; unter 5
      Sekunden steht „gleich fertig". Das Pop-up hat keinen Schließen-Knopf,
      solange der Upload läuft (Abbrechen-Knopf bricht den Request ab, die
      Liste bleibt erhalten wie in v35).
- [ ] **Erfolgs- und Fehlermeldung im Pop-up:** Nach Antwort des Servers
      wechselt das Pop-up auf **„3 Fotos hochgeladen"** (Erfolgsfarbe, Knopf
      „Schließen", schließt nach 3 Sekunden auch von selbst und leert die
      Upload-Liste) oder **„2 von 3 Fotos hochgeladen"** (Warnfarbe) mit der
      Liste der fehlgeschlagenen Dateien samt Grund aus der Teilerfolgs-
      Antwort (z. B. „Datei zu groß", „Dateityp nicht erlaubt"), Knöpfe
      „Erneut versuchen" (sendet nur die fehlgeschlagenen) und „Schließen".
      Bricht die Verbindung ab (Netzfehler, Timeout, Status 0), erscheint
      **„Kein Netz. Die Fotos bleiben gespeichert und werden später
      hochgeladen."** mit Knopf „Schließen" (siehe nächste Checkbox). Die
      Galerie-Ansicht aktualisiert sich nach Erfolg ohne Seitenneuladen
      (Vorschaukacheln anhängen).
- [ ] **Offline-Zwischenspeicher:** Fehlschlag wegen Netz → die verkleinerten
      Dateien (Blob), Ordner, Bemerkung, Vorgangs-ID, Objekt-ID und
      Zeitstempel werden in **IndexedDB** des Browsers abgelegt (Datenbank
      `friondo_galerie_puffer`, Store `wartend`, `static/galerie_puffer.js`;
      funktioniert über http, braucht kein HTTPS; max. 50 Fotos oder 100 MB
      je Browser [ANNAHME], darüber Hinweis „Zwischenspeicher voll, bitte
      zuerst hochladen"). Beim Öffnen einer Seite mit Galerie **desselben
      Vorgangs** mit Netz erscheint oberhalb der Galerie ein Hinweiskasten
      **„3 Fotos warten auf Upload (seit 14.10., 16:32)"** mit Knöpfen
      **„Jetzt hochladen"** (nutzt den normalen Upload mit Pop-up) und
      „Verwerfen" (Sicherheitsabfrage). Wartende Fotos anderer Vorgänge
      zeigt die Startseite der mobilen Erfassung (`/erfassung`) als Zeile
      „Wartende Fotos: Vorgang Müller (3), Vorgang Schmidt (1)" mit Link auf
      die jeweilige Galerie. Nach erfolgreichem Upload werden die Einträge
      aus IndexedDB gelöscht; fehlt der Vorgang inzwischen (archiviert,
      gelöscht), bleibt der Eintrag mit Hinweis „Vorgang nicht mehr
      vorhanden" und kann verworfen werden. **Kein automatischer Upload im
      Hintergrund** (kein Service Worker); Hinweis in `docs/betrieb.md`,
      dass der Puffer nur im jeweiligen Browser des Geräts liegt.
- [ ] **Mehrfach-Löschen in der Galerie:** In jedem Ordner (und in der
      Sammelbox) ein Knopf **„Auswählen"**,
      der je Vorschaukachel ein Kästchen einblendet; Kopfleiste „n
      ausgewählt · Alle · Keine" und Knopf **„n Fotos löschen"**
      (Gefahrfarbe) mit Sicherheitsabfrage „3 Fotos endgültig löschen?
      Das lässt sich nicht rückgängig machen." Kästchen erscheinen nur an
      Dateien, die der Benutzer löschen darf (Rechte wie Einzel-Löschen:
      Hochladender, Innendienst, Admin); andere Kacheln ohne Kästchen.
      Route `POST /vorgaenge/<id>/galerie/loeschen` mit `datei_ids[]`,
      `_speichern`-Muster, prüft jede ID gegen Vorgang und Rechte, löscht
      Datei und Datensatz, antwortet mit gelöschten und abgelehnten IDs;
      Eintrag im Notizen-Chat „3 Fotos gelöscht (Ordner Zählerschrank)"
      [ANNAHME: wie beim Einzel-Löschen, falls dort ein Eintrag entsteht,
      sonst keiner]. Bestehendes Einzel-Löschen und Lightbox unverändert.
- [ ] Tests `tests/test_v38_galerie.py`: Teilerfolgs-Antwort mit Grund je
      Datei; Mehrfach-Löschen drei IDs (zwei erlaubt, eine fremd → eine
      abgelehnt, zwei gelöscht, Dateien weg); Rechte je Rolle; Headless-
      Chrome (Muster `test_v30_navigation.py`): Upload-Pop-up zeigt Dauer
      und Erfolgsmeldung; simulierter Netzfehler → Eintrag in IndexedDB,
      Hinweiskasten nach Neuladen, „Jetzt hochladen" leert den Puffer.

## Phase 202: Erfassung zwischenspeichern und nachträglich korrigieren

- [ ] **Befund Abbruch des Bogens:** Reproduzieren (Playwright, Mobile-
      Emulation, Rolle Außendienst): Bogen starten, fünf Fragen beantworten,
      Seite verlassen (Zurück, Tab schließen, Menü), Bogen über die
      Erfassungsliste erneut öffnen. Feststellen und in der Gesamtübersicht
      benennen: (1) werden Antworten je Frage sofort serverseitig gespeichert
      oder erst beim Weiter/Absenden; (2) ob die Erfassung in der Liste
      sichtbar ist, mit welchem Status; (3) ob der Bogen bei der letzten
      beantworteten Frage weitermacht oder von vorn beginnt; (4) ob
      `beforeunload` greift. Danach die folgenden Punkte so umsetzen, dass
      das Soll gilt, ohne bereits Vorhandenes doppelt zu bauen.
- [ ] **Soll Zwischenspeichern:** Jede Antwort wird beim Weiter sofort
      serverseitig gespeichert (ist das schon so, nur Test). Erfassungen ohne
      Absenden tragen den Status **„Entwurf"** [ANNAHME: Statuswert
      `entwurf`, additiv; falls ein gleichbedeutender Status existiert, den
      nehmen] und stehen in der Erfassungsliste (mobil und Desktop) mit
      Badge „Entwurf · Frage 12 von 31". Im Bogen oben rechts ein Knopf
      **„Später fortsetzen"** (Speichert den Stand, führt zur
      Erfassungsliste, Meldung „Erfassung gespeichert. Sie können jederzeit
      weitermachen."). Öffnen eines Entwurfs springt zur ersten
      unbeantworteten Frage mit Hinweis „Fortgesetzt bei Frage 12". Beim
      Verlassen des Bogens mit ungespeicherter Eingabe im aktuellen Feld:
      Browser-Hinweis (`beforeunload`), nicht bei „Später fortsetzen" und
      nicht nach Absenden. Entwürfe älter als 30 Tage [ANNAHME] erscheinen
      in der Liste mit Warnfarbe, werden nicht automatisch gelöscht.
- [ ] **Korrektur nach „Senden":** In der Erfassungsansicht (Prüfen-Seite
      `/erfassung/{id}/pruefen` und Vorgangsakte, Karte Erfassung) ein Knopf
      **„Antworten korrigieren"**. Rechte: Außendienst nur bei
      `erfassungen.ad_id` = eigener Benutzer [ANNAHME: Feldname wie beim
      Freitext-Editieren aus v13 übernehmen], Innendienst und Admin bei
      allen. Sperre [ANNAHME]: Knopf deaktiviert mit Tooltip „Angebot ist
      bereits versandfertig", sobald ein verknüpftes Angebot den Status
      „Versand vorbereitet" oder „Versendet" hat; bei Status „Entwurf" des
      Angebots nach dem Speichern Hinweis **„Antworten geändert. Bitte das
      Angebot neu berechnen."** mit Link zum Angebot (keine automatische
      Neuberechnung). Der Korrekturmodus öffnet den Bogen mit allen
      bisherigen Antworten vorbelegt, Sprung direkt zu einer Frage über die
      Prüfen-Seite (Klick auf die Frage), Knopf „Korrektur speichern"
      (statt Absenden), AMPEL und Pflichtfragen werden erneut geprüft.
      Status der Erfassung bleibt unverändert (nicht wieder „Entwurf").
- [ ] **Änderungsnotiz:** Jede gespeicherte Korrektur erzeugt einen Eintrag
      im Notizen-Chat des Vorgangs (Makro `notizen_chat`, Herkunft System):
      **„Erfassung nachträglich geändert von <Name> am TT.MM.JJJJ HH:MM:
      A04 Aufstellort: Keller → Dachgeschoss; B02 Heizlast: 8 kW → 9 kW"**
      (je Frage Kürzel, Fragetitel, alter und neuer Wert; bei mehr als fünf
      Änderungen „… und 3 weitere", Vollständiges im Eintrag aufklappbar).
      Zusätzlich an der Erfassung ein Badge **„nachträglich geändert
      (TT.MM.)"** in Liste, Prüfen-Seite und Vorgangsakte. Der bestehende
      Freitext-Editor (v13) bleibt und schreibt künftig denselben Eintrag.
- [ ] Tests `tests/test_v38_erfassung.py`: Entwurf nach Abbruch sichtbar und
      fortsetzbar an der richtigen Frage; „Später fortsetzen"; Korrektur als
      AD an eigener Erfassung erlaubt, an fremder 403; ID an allen;
      gesperrt bei „Versand vorbereitet"; Notizen-Chat-Eintrag mit altem
      und neuem Wert; Badge; Hinweis „Angebot neu berechnen" bei Entwurf.

## Phase 203: Leads VOT Desktop: Kanal-Pfeil, Gruppe „Vergangene Termine"

Grundlage ist die Tabelle aus v33 Phase 174 (Gruppen „Heute" und je
Folgetag, auf- und zuklappbar, Chip-Filter, Spaltenwähler).

- [ ] **Kanalspalte ohne Dropdown:** Die Zelle zeigt nur das farbige Kanal-
      Badge (`kanal_badge`, Farben aus `kanal_farben`) und rechts daneben
      einen kleinen Pfeil nach unten (Symbol aus `_symbole.html`, 16 px,
      gedämpfte Farbe, `aria-label="Vertriebskanal ändern"`). Erst ein Klick
      auf den Pfeil öffnet die bisherige Auswahl als kleines Menü unter der
      Zelle (gleiche Werte wie das heutige Dropdown, aktueller Wert
      markiert); Auswahl speichert sofort über die bestehende Route
      (manuelle Änderung mit Vorrang vor Sync, v13), Badge wechselt ohne
      Seitenneuladen. Escape und Klick außerhalb schließen das Menü. Keine
      Änderung in Kundenliste, Kundenkartei und Lead-Boards.
- [ ] **Gruppe „Vergangene Termine":** Neue Gruppe **unterhalb** der
      Folgetage [ANNAHME: unten, damit „Heute" oben bleibt], Kopf
      **„Vergangene Termine · 7"**, standardmäßig zugeklappt, Zustand je
      Benutzer gemerkt (wie die übrigen Gruppen, `localStorage`). Inhalt:
      alle Termine aus `vot_termine` ohne abgeschlossene Erfassung mit
      Beginn vor heute und innerhalb der **letzten 180 Tage**, neueste
      zuerst; Spalte Termin in gedämpfter Farbe mit Zusatz „vor 12 Tagen".
      Außendienst sieht nur eigene, Innendienst/Admin alle; Chip-Filter
      (Vertriebler, Status, Priorität) wirken auch hier. Termine älter als
      180 Tage erscheinen nicht (kein eigener Filter).
- [ ] **„Überfällig" streichen:** Das rote Label „überfällig" und die
      Einsortierung vergangener Termine in „Heute" (v32 Phase 161, v33
      Phase 173) entfallen auf Desktop und mobil. „Heute" enthält nur
      Termine mit Beginn am heutigen Tag. Die Startseiten-Kachel-Zähler und
      die Statistik „Offene Leads" bleiben unverändert [ANNAHME].
- [ ] Tests `tests/test_v38_leads_vot.py`: Kanal-Änderung über die neue
      Route liefert neues Badge; Termin gestern ohne Erfassung → in
      „Vergangene Termine", nicht in „Heute", ohne Label „überfällig";
      Termin vor 181 Tagen → nirgends; Termin gestern mit abgeschlossener
      Erfassung → nirgends; AD sieht nur eigene.

## Phase 204: Mobil: Reiter „Vergangene Termine", Erfassungsliste mit Objekt

- [ ] **Untere Leiste:** Der vierte Eintrag **„Kunden"** (v33 Phase 173)
      wird durch **„Vergangene Termine"** ersetzt (Symbol Uhr/Verlauf aus
      `_symbole.html`; Beschriftung unter 360 px „Vergangen"). Reihenfolge:
      „Mein Tag" · „Kalender" · „Wiedervorlage" · „Vergangene Termine".
      Die allgemeine Suche (v32 Phase 164) bleibt über die Lupe im
      Hauptmenü erreichbar; `docs/nach-dem-update-v38.md` nennt das dem
      Außendienst.
- [ ] **Seite „Vergangene Termine" mobil:** Route [ANNAHME] `GET /leads/
      vergangene` (Rolle Außendienst, Datenbestand identisch zur Desktop-
      Gruppe aus Phase 203, 180 Tage, nur eigene): Zurück-Pfeil „Mein Tag",
      Titel „Vergangene Termine" mit Zähler „7 ohne Erfassung", Suchfeld
      „Nach Name suchen" (filtert beim Tippen wie die Wiedervorlage-Seite),
      Liste gruppiert je Tag mit Datumskachel links (wie „Kommende Tage"),
      neueste zuerst; je Termin Uhrzeit, Kundenname, Sparte/Termintyp,
      **Objektbezeichnung und Objektadresse** (bei Ein-Objekt-Vorgängen nur
      Adresse), Hauptaktion rechts **„Erfassung starten"** (übergibt Termin
      und Objekt wie in „Mein Tag"), Zweitlink „Akte". Leerzustand „Keine
      vergangenen Termine ohne Erfassung" mit Zeile „Alles erfasst." Untere
      Leiste mit aktivem Eintrag. Für Innendienst/Admin entfällt die Seite
      (sie nutzen die Desktop-Gruppe).
- [ ] **Erfassungsliste mobil mit Objekt:** In der Liste der Erfassungen des
      Außendienstlers (`/erfassungen`, Darstellung unter 600 px) zeigt jede
      Erfassung unter dem Kundennamen eine Zeile **„<Objektbezeichnung> ·
      <Straße Nr., PLZ Ort>"** aus `vorgang_objekte` (Objekt, das der
      Erfassung zugeordnet ist, v31); bei Ein-Objekt-Vorgängen nur die
      Adresse; fehlt die Zuordnung, die Kundenadresse mit Zusatz „(Kunde)".
      Bei Großkunden mit mehreren Erfassungen desselben Kunden ist so jede
      Erfassung unterscheidbar. Desktop-Tabelle: neue Spalte „Objekt"
      (über den Spaltenwähler, Standard sichtbar) mit demselben Inhalt
      [ANNAHME]. Suchfeld der Liste findet auch die Objektbezeichnung.
- [ ] **Dialog „Termin nicht stattgefunden":** Knopf (Zweitaktion neben
      „Erfassung starten") an jeder Termin-Karte in „Mein Tag" (Blöcke „Als
      Nächstes" und „Heute"), auf der Seite „Vergangene Termine" mobil und
      als Zeilenaktion in der Desktop-Tabelle Leads VOT (alle Gruppen). Der
      Dialog (Makro `termin_ausgefallen_dialog`, Design-v2-Tokens, mobil
      als Vollbild-Sheet) fragt: **Grund** als Auswahl „Kunde nicht
      angetroffen" · „Kunde hat sich anders entschieden" · „Sonstiges" mit
      Pflicht-Freitext bei Sonstiges, optionale Bemerkung (Diktat-Knopf aus
      v34); danach **„Was soll passieren?"** mit zwei Knöpfen: **„Neuen
      Termin vereinbaren lassen"** und **„Kunde möchte keinen neuen
      Termin"**. Vorbelegung: bei „Kunde nicht angetroffen" ist „Neuen
      Termin vereinbaren lassen" vorausgewählt, bei „Kunde hat sich anders
      entschieden" die zweite Option [ANNAHME]. Route [ANNAHME] `POST
      /leads/termin/{termin_id}/ausgefallen` (`_speichern`-Muster), Rechte:
      Außendienst nur eigene Termine (`vot_termine` des eigenen Vorgangs),
      Innendienst/Admin/Leadmanagement alle.
- [ ] **Folge „Neuen Termin vereinbaren lassen":** `vot_termine.status` =
      `no_show` [ANNAHME: Wert wie der bestehende No-Show-Weg der AD-Sicht
      aus v12/v23, sonst neuer Wert], Grund und Bemerkung am Termin
      gespeichert; Lead-Phase wie beim bestehenden No-Show zurück auf
      **„Kontaktiert"** (v25); Outlook-Ereignis des AD (v33) wird abgesagt,
      falls vorhanden. **To-Do an das Leadmanagement** (bestehende To-Dos
      am Vorgang, v25/v29): Titel **„Neuen Termin vereinbaren: <Kunde>"**,
      Text „Termin am TT.MM. HH:MM nicht stattgefunden (Grund: Kunde nicht
      angetroffen). Bemerkung: …", fällig heute, zugewiesen an den
      **dem Vorgang zugewiesenen Innendienstler (Leadmanager, v31)**; fehlt
      die Zuweisung, bleibt das To-Do ohne Person und steht im Lead-Dashboard
      unter „Offene To-Dos" mit Hinweis „kein Leadmanager zugewiesen"
      [ANNAHME: kein Team-Fallback]; Glocke benachrichtigt (v29: Glocke nur
      für To-Dos). Zusätzlich
      Wiedervorlage des Vorgangs auf heute [ANNAHME: `vorgaenge.
      wiedervorlage_am`, damit der Lead im Dashboard des Leadmanagements
      unter „Fällig heute" steht]. Der Termin verschwindet aus „Heute",
      „Vergangene Termine" und der Desktop-Gruppe; Meldung an den AD
      „Weitergegeben an das Leadmanagement". Eintrag im Notizen-Chat
      **„Termin am TT.MM. nicht stattgefunden (Grund) · neue Terminfindung
      durch Leadmanagement"**. Keine automatische E-Mail an den Kunden
      [ANNAHME; Vorlage `terminabsage` bleibt dem Leadmanagement
      vorbehalten].
- [ ] **Folge „Kunde möchte keinen neuen Termin":** Zweite Abfrage
      **„Kunden disqualifizieren?"** mit Grund-Auswahl aus den bestehenden
      Disqualifizierungs-Gründen (v23/v25, Pflicht) und Knopf „Disqualifizieren";
      Termin wird `abgesagt`, Lead-Phase **„Disqualifiziert"** über denselben
      Weg wie im Lead-Management (Verlauf, Board-Zuordnung, Kennzahlen),
      Outlook-Ereignis abgesagt. **Keine E-Mail an den Kunden**: Bei einer
      Disqualifizierung geht grundsätzlich keine Mail; die Vorlage
      „Disqualifiziert, nicht erreicht" (Kaskaden-Ende v31) bleibt dem
      Fall „nicht erreicht" nach dem letzten Anrufversuch vorbehalten
      (Entscheidung Claudia 16.10.2026). Eintrag im Notizen-Chat
      **„Termin am TT.MM. nicht stattgefunden (Grund) · Kunde
      disqualifiziert durch <AD-Name>: <Disqualifizierungsgrund>"**. Das
      Leadmanagement sieht den Vorgang danach im Hauptboard unter
      „Disqualifiziert"; ein Zurückholen bleibt wie heute möglich.
      „Abbrechen" im Dialog lässt alles wie zuvor. **Keine dritte Option**
      (entschieden 16.10.2026): Ist der Kunde unentschieden, wählt der
      Vertriebler „Neuen Termin vereinbaren lassen" und schreibt das in
      die Bemerkung.
- [ ] Tests `tests/test_v38_mobil.py`: Leiste enthält „Vergangene Termine"
      und nicht „Kunden"; Dialog „Termin nicht stattgefunden": Option 1 →
      Termin `no_show`, Phase „Kontaktiert", To-Do mit Titel und Fälligkeit
      heute, Benachrichtigung beim zugewiesenen Innendienstler, Termin nicht mehr in den
      Listen, Notizen-Chat-Eintrag; Option 2 mit Grund → Phase
      „Disqualifiziert", keine Mail versendet, Eintrag mit AD-Name; AD an
      fremdem Termin → 403; Seite listet Termin gestern mit Objektname und
      Adresse; Erfassungsliste zeigt bei Vorgang mit zwei Objekten je
      Erfassung das richtige Objekt; Screenshots 390 px hell/dunkel nach
      `docs/design-v38/` (Upload-Pop-up, Hinweiskasten wartende Fotos,
      Auswählen-Modus, Seite „Vergangene Termine", Erfassungsliste mit
      Objekt, Bogen mit „Später fortsetzen"), nur Demo-Daten.

## Phase 205: Tests, Rollout-Vorbereitung, Doku, CLAUDE.md v38

- [ ] **Regressionstest Fotos je Objekt:** entfällt – die Objektfotos sind mit dem Nachtrag 16.10.
      zu PLAN_LEAD_V6 (PLAN_LEAD_V6_1) gestrichen (Vorprüfung der Plan-Kette 16.10.2026, Rückfrage).
- [ ] **Tests gesamt:** `test_v38_galerie.py`, `test_v38_erfassung.py`,
      `test_v38_leads_vot.py`, `test_v38_mobil.py`; angepasste Alt-Tests
      (Label „überfällig", Knopfbeschriftung „n Fotos hochladen", untere
      Leiste) mit Begründung; `pytest tests -q` komplett grün, Wächter v27
      und Token-Wächter v30 grün; Außendienst-Sichtprüfung (kein EK/DB,
      Korrektur nur an eigenen Erfassungen).
- [ ] **Rollout-Vorbereitung** nach Grundregel: Server-DB-Kopie nach
      diagnose\, migrate.py zweimal (zweiter Lauf ohne Änderungen; additiv:
      Status `entwurf` falls neu, `erfassungen.geaendert_am` und
      `erfassungen.geaendert_von` [ANNAHME: Felder für das Badge],
      `erfassungen.aktuelle_frage` [ANNAHME: für die Fortsetzung, falls
      nicht ableitbar]), Rückweg-Probe v37-Code auf v38-DB, Voll-Crawl
      (admin, innendienst, aussendienst, montage, projektierung) hell/dunkel,
      Abnahmeskript, Smoke, Lasttest Profil `normal` (Mehrfach-Löschen,
      Route `/leads/vergangene` und Dialog „Termin nicht stattgefunden"
      ins AD-Profil); additiv auch `vot_termine.ausfall_grund`,
      `vot_termine.ausfall_bemerkung` [ANNAHME], Screenshots nach
      `docs/design-v38/`, nur Demo-Daten.
- [ ] **Doku:** CLAUDE.md Abschnitt „Neu in v38 – Foto-Upload, Erfassung
      Zwischenspeichern/Korrektur, Vergangene Termine (abgestimmt
      16.10.2026)" nach „Neu in v37", Zuordnungstabelle `| v38 | PLAN_V23.md
      | 201–205 |`, Titelzeile „(v38)"; in „Neu in v32" und „Neu in v33"
      die Sätze zu „überfällig" und zum Reiter „Kunden" als *überholt, siehe
      v38* markieren; „Neu in v34" (Knopf „n Fotos hochladen") ebenso;
      „Fachliche Regeln" um „Korrektur nach Senden mit Änderungsnotiz".
      `docs/nach-dem-update-v38.md` (Außendienst: Knopf „Hochladen" mit
      Pop-up, wartende Fotos bei fehlendem Netz, Auswählen zum Löschen,
      „Später fortsetzen", „Antworten korrigieren", Reiter „Vergangene
      Termine" statt „Kunden", Suche über die Lupe, Dialog „Termin nicht
      stattgefunden"; Leadmanagement: To-Do „Neuen Termin vereinbaren" und
      Disqualifizierung durch den Vertriebler; Innendienst: Kanal-
      Pfeil, Gruppe „Vergangene Termine", Badge „nachträglich geändert" im
      Notizen-Chat beachten); `docs/betrieb.md` (IndexedDB-Puffer je Gerät,
      Mehrfach-Löschen); `docs/updates.md`; `config.VERSION = "v38"`.
- [ ] **Gesamtübersicht am Ende:** erledigte Phasen, Testergebnisse
      (Gesamtzahl), angepasste Alt-Tests mit Begründung, **Befund Abbruch
      des Bogens** (Phase 202), [ANNAHME]-Liste, Rückfragen gebündelt. **Ein
      Commit** „v38: Foto-Upload Pop-up/Offline/Mehrfach-Löschen, Erfassung
      Entwurf/Korrektur, Leads VOT Kanal-Pfeil/Vergangene Termine, Mobil
      (PLAN_V23, Phasen 201-205)"; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Galerie mobil: drei Fotos in der Upload-Liste → Knopf „Hochladen (3)" →
  Pop-up mit „Voraussichtlich noch ca. … Sekunden" → „3 Fotos hochgeladen",
  Liste leer, drei neue Kacheln ohne Neuladen.
- Upload mit einer 12-MB-Datei (über Limit) und zwei gültigen → „2 von 3
  Fotos hochgeladen", Fehlerzeile mit Grund, „Erneut versuchen" sendet nur
  die eine.
- Flugmodus während des Uploads → Meldung „Kein Netz …", nach Neuladen mit
  Netz Hinweiskasten „3 Fotos warten auf Upload", „Jetzt hochladen" → drei
  Dateien im richtigen Ordner, Puffer leer.
- Galerie, Ordner Zählerschrank mit vier Fotos (zwei eigene, zwei vom
  Innendienst), Rolle Außendienst: „Auswählen" zeigt zwei Kästchen,
  „2 Fotos löschen" nach Abfrage → zwei Dateien weg, zwei bleiben.
- Bogen: fünf Fragen beantwortet, „Später fortsetzen" → Liste zeigt
  „Entwurf · Frage 6 von …", Öffnen startet bei Frage 6.
- Abgesendete Erfassung, AD eigene: „Antworten korrigieren" → A04 geändert
  → Notizen-Chat-Eintrag mit „Keller → Dachgeschoss", Badge „nachträglich
  geändert (16.10.)"; fremde Erfassung → kein Knopf, Route 403; Angebot
  „Versand vorbereitet" → Knopf deaktiviert.
- Leads VOT Desktop: Kanalzelle zeigt Badge + Pfeil, kein Dropdown; Klick
  auf Pfeil → Menü, Auswahl „Sparkasse Duisburg" → Badge wechselt sofort.
- Termin von gestern ohne Erfassung → nur in Gruppe „Vergangene Termine ·
  1" (zugeklappt), nicht in „Heute", kein Label „überfällig"; Termin vor
  200 Tagen → nicht sichtbar.
- Handy 390 px, Rolle Außendienst: untere Leiste „Mein Tag · Kalender ·
  Wiedervorlage · Vergangene Termine"; Seite zeigt den gestrigen Termin
  mit Objektbezeichnung und Adresse, „Erfassung starten" öffnet den Bogen
  mit dem richtigen Objekt.
- Erfassungsliste mobil bei Großkunde mit Objekten „Halle Nord" und
  „Verwaltung": beide Erfassungen mit eigener Objektzeile und Adresse.
- „Mein Tag", Termin 09:30 Müller → „Termin nicht stattgefunden", Grund
  „Kunde nicht angetroffen", „Neuen Termin vereinbaren lassen" → Termin
  weg aus „Heute", Leadmanager sieht To-Do „Neuen Termin vereinbaren:
  Müller" (fällig heute) mit Glocke, Vorgang unter „Fällig heute", Phase
  „Kontaktiert", Notizen-Chat-Eintrag.
- Seite „Vergangene Termine", Termin Schmidt → Grund „Kunde hat sich
  anders entschieden", „Kunde möchte keinen neuen Termin", Grund
  „Kein Interesse mehr" → Phase „Disqualifiziert", Hauptboard zeigt ihn
  dort, kein Mailversand, Eintrag „disqualifiziert durch <AD>".
- `pytest tests -q` grün, Abnahmeskript grün, Voll-Crawl ohne Absturz,
  Lasttest normal innerhalb der Zielwerte, 0 „database is locked".

## Zulieferungen / bewusst offen

- **Bestätigung der [ANNAHME]-Stellen (Claudia/Andreas):** Startwert 500
  KB/s für die Dauer-Schätzung; Puffergrenze 50 Fotos/100 MB; Notizen-
  Chat-Eintrag beim Mehrfach-Löschen; Statusname „Entwurf"; Warnfarbe für
  Entwürfe ab 30 Tagen; Korrektur gesperrt ab „Versand vorbereitet";
  Gruppe „Vergangene Termine" unten; Kachel-Zähler unverändert; Spalte
  „Objekt" auch auf dem Desktop; Routenname `/leads/vergangene`;
  Versionsnummer v38 und Phasen 201 bis 205.
- **Befund Phase 202:** Das heutige Verhalten beim Verlassen des Bogens ist
  nicht bekannt; Claude Code stellt es fest und baut nur, was fehlt.
- **Entschieden 16.10.2026 (Claudia):** To-Do an den zugewiesenen
  Innendienstler des Vorgangs; keine Mail bei Disqualifizierung (nur
  „nicht erreicht" nach dem letzten Versuch); keine dritte Option im
  Dialog. Offen bleibt nur das Verhalten ohne zugewiesenen Leadmanager
  [ANNAHME: To-Do ohne Person im Lead-Dashboard].
- **HTTPS im VPN (Andreas/IT, `docs/https-intern.md`):** Voraussetzung für
  Live-Kamera (mehrere Fotos ohne Rückkehr ins Tool), Browser-Diktat und
  echten Offline-Betrieb (Service Worker). Bis dahin: Kamera-App am Stück,
  danach Galerie-Mehrfachauswahl; Puffer nur für fehlgeschlagene Uploads.
- **Nicht Teil dieses Plans:** Kanal-Pfeil in Kundenliste/Kundenkartei,
  automatischer Hintergrund-Upload, automatische Neuberechnung des
  Angebots nach Korrektur, Löschen von Fotos im Montage-Backend durch
  Montage-Benutzer über die heutigen Rechte hinaus.
