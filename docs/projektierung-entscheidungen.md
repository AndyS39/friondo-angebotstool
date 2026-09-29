# Projektierung V1 – Entscheidungen während der Umsetzung (Claude Code)

Dieses Dokument sammelt alle Stellen, an denen der Plan/das Konzept Spielraum
ließ und Claude Code im Sinne des Konzepts entschieden hat (PLAN_PROJ_V1,
Phasen 64–72). Andreas geht die Liste nach V1 durch.

## Phase 64 – Datenmodell

- **Mehrfachrollen als Komma-Liste** (nicht als Zuordnungstabelle): neue Spalte
  `benutzer.rollen` trägt die vollständige Rollenliste; `benutzer.rolle` bleibt
  als **Hauptrolle** bestehen und steuert weiterhin alle bisherigen Sichten
  (Admin/Innendienst/Außendienst) – kein Risiko für bestehende Rollenprüfungen.
  Neue Prüfungen laufen über `Benutzer.hat_rolle("projektierung"/"montage")`.
  Passt zum Bestand (Interessen/Sparten sind ebenfalls Komma-Listen). Die
  Migration befüllt `rollen` einmalig mit der bisherigen Rolle.
- **Sub-Zuordnungen** (Reiter „Subs & Bestellungen", Phase 67) brauchen eine
  eigene Tabelle, die der Plan nicht explizit listet → `projekt_subs`
  (projekt_id, gewerk_id, sub_id, leistung, status, termin, notiz).
- **`aufgaben.faellig_regel`** wird zusätzlich zur berechneten Fälligkeit
  gespeichert (Plan nennt nur die Regel in der Excel): nötig, damit `FP+N`/
  `M-N`-Fälligkeiten beim späteren Anlegen des Termins nachberechnet werden
  können. Ebenso `aufgaben.wartet_frist_tage` (Frist aus der Vorlage; das
  konkrete `wartet_frist_am` wird beim Umstellen auf „Wartet" gesetzt).
- **`aufgabenpaket_instanzen.paket_name`** wird beim Aktivieren eingefroren,
  damit die Gruppierung in der Akte auch nach einem späteren Excel-Import mit
  umbenannten Paketen stabil bleibt.
- **PR-Nummernkreis**: Zähler + Jahr in `projektierung_parameter`
  (`pr_zaehler`, `pr_zaehler_jj`); beim Jahreswechsel startet der Zähler neu
  bei 0001. Kollisionen werden übersprungen (analog Retry beim AN-C-Kreis).
- **Ordnervorlage**: Ebene „gewerk" wird je Sparte unter
  `data/projekte/<PR>/<Sparte>/<Pfad>` angelegt (z. B. `WP/02 Feinplanung &
  Heizlast`), Ebene „projekt" direkt unter `<PR>/` – so kollidieren
  Kombi-Projekte nicht in denselben Foto-Ordnern.
- **Auftragswert** wird in Cent gespeichert (wie alle Beträge im Tool);
  „Auftragswert = Endbetrag brutto" (Konzept Annahme 12).

## Phase 65 – Steuerdatei

- **Datei-basierter Import statt DB-Abbild**: `projektierung_logik_v1.xlsx`
  liegt wie die Konfigurator-Excel im Projektroot und wird mit mtime-Cache
  geparst; der Upload in der Parametrierung sichert die alte Datei nach
  `data/backups/` und ersetzt sie (bei Lesefehlern automatischer Rollback).
  Da Aufgaben nur bei der AKTIVIERUNG eines Pakets entstehen, sind doppelte
  Importe konstruktionsbedingt dublettenfrei und Änderungen wirken – wie im
  Plan gefordert – nur auf neue Aktivierungen.
- **Ordnerstruktur + Sub-Typen** aus der Excel werden beim Einlesen in die
  `projektierung_parameter` übernommen (`ordnervorlage`, `sub_typen`) und
  gelten ab dann für neue Projekte/Formulare.
- **Regel-Duplikate**: Verweisen mehrere IMMER-Regeln auf dasselbe Paket,
  wird es nur einmal aktiviert; Regeln auf unbekannte Pakete erzeugen eine
  Warnung im Import (kein Abbruch).

## Phase 66 – Angebot → Projekt

- **„Offenes Projekt"** = `status_cache != "abgeschlossen"` (auch ein Projekt,
  dessen Gewerke sämtlich storniert sind, gilt als abgeschlossen – so kann
  nach Komplett-Storno ein neues Projekt zum selben Vorgang entstehen).
- **Automatische Dokument-Ablage** (Angebots-PDF, Erfassungsprotokoll) läuft
  in try/except: Ein PDF-Fehler blockiert die Projektanlage nie (Prinzip
  „Fehler blockieren das Tool nie", wie monday/Mail).
- **Versionsfolge**: Der Nachzieh-Hook hängt am zentralen Statuswechsel
  (`angebot_status_setzen` → Wrapper in den Routen Status/Signatur), damit
  auch die Vor-Ort-/Fern-Signatur (Status „Angenommen") das Gewerk nachzieht.

## Phase 67 – Projektakte

- **Aufgaben-Anhänge** laufen in V1 über den Dokumente-Reiter (Ordner je
  Gewerk) statt über eine eigene Anhang-Tabelle je Aufgabe; Kommentare je
  Aufgabe liegen im Projektverlauf (`aufgabe_id`) und werden mit Zähler an
  der Aufgabe angezeigt.
- **Wächter „In Ausführung → Abnahme offen"**: Der Phasenwechsel selbst gilt
  in V1 als Häkchen „Montage fertig" (setzt `montage_fertig_am`); die
  Protokoll-Prüfung kommt mit den Montage-Formularen in V3.
- **„Abgeschlossen"** ist im Phase-Dropdown wählbar, aber vom Wächter
  „Rechnung nicht freigegeben" geschützt – regulär führt nur der
  Freigabe-Dialog dorthin (Override mit Begründung bleibt möglich,
  Konzept Annahme 13: kein hartes Sperren).
- **Benachrichtigung bei Phasenwechsel** geht an Projektleiter, Feinplaner
  und Elektroplaner des Gewerks (= „Benutzer, die zugewiesen sind").
- **Vorgangs-Notizen** (Vertriebsphase) erscheinen in der Akte nur, wenn
  welche existieren (read-only, aufklappbar unter dem Projektverlauf).

## Phase 68 – Kanban, Liste, Startseite

- **Drag & Drop bei blockiertem Wächter**: Das Board zeigt die Wächter-Meldung
  als Hinweis mit Link „→ Projektakte" statt eines eigenen Override-Dialogs auf
  dem Board. Der Override mit Begründung bleibt bewusst in der Akte (dort steht
  der volle Kontext: offene Pflichtaufgaben, Termine). Kein hartes Sperren –
  Konzept Annahme 13 bleibt gewahrt.
- **Startseiten-Shortcut „Meine Aufgaben"**: Die Portal-Karte ist laut finaler
  Portal-Fassung (v9) EIN Klickziel ohne eingebettete Buttons. Der Shortcut
  läuft daher über die Kachel „Überfällige Aufgaben" (Hinweistext „→ Meine
  Aufgaben") und den Kopf-Link „Meine Aufgaben" auf dem Board – kein eigener
  Link im Portal.
- **CSV-Export** mit `utf-8-sig` und Semikolon-Trenner, damit Excel (deutsche
  Locale) die Datei direkt korrekt öffnet – gleiches Muster wie bestehende
  Exporte.

## Phase 69 – Kommunikation und Benachrichtigungen

- **Glocken-Daten je Seitenaufruf**: Die Kopfzeilen-Glocke (Zähler + letzte 20)
  wird in der bestehenden RollenMiddleware befüllt (`request.state.glocke_*`) –
  einzige Stelle, die auf jeder Seite läuft; Fehler dort blockieren die Seite
  nie. `/benachrichtigungen` ist auch für den Außendienst freigeschaltet
  (Plan: „alle Rollen").
- **Demo-Filter schon in Phase 69**: Alle V1-Ereignisarten stammen aus der
  Projektierung; im Demo-Modus (`freigabe_modus=admin`) blendet die Glocke sie
  für Nicht-Admins aus und es gehen keine Mails an Nicht-Admins – das zieht die
  Phase-70-Regel „Glocken-Ereignisse nur Admin" vor, damit die Demo nichts leakt.
- **Mail-Betreff**: PR-Nummer wird aus dem Benachrichtigungstext gelesen
  (Muster `PR-\d{6}`), der Kunde über das Projekt aufgelöst – so braucht
  `benachrichtigen()` keine zusätzlichen Parameter und alle Aufrufer bleiben
  unverändert.
- **Senden-als-Fallback**: schlägt der Versand über das eingestellte Postfach
  fehl, wird einmal mit `angebot@friondo.de` nachversucht; beide Fehler landen
  im Protokoll `mail_protokoll` (letzte 20 Zeilen, projektierung_parameter).
- **Scheduler**: ein Thread prüft alle 5 Minuten; Datums-Schalter
  (`faellig_lauf_datum`, `digest_datum`) stellen sicher, dass Lauf und Digest
  höchstens einmal pro Tag laufen – auch nach einem Neustart mitten am Tag
  (Start nach 07:00 holt den Lauf desselben Tags nach).
- **Profil-Einstellung aus/sofort/digest** liegt in der Benutzerverwaltung
  (Admin) – ein eigenes Selbstbedienungs-Profil gibt es im Tool bisher nicht.

## Phase 70 – Rollen und Sichten

- **„/“ bleibt für die Rollen projektierung und montage erreichbar** und dient
  als Landeplatz im Demo-Modus (das Portal zeigt dann die nicht anklickbare
  Projektierungs-Karte). Ohne diese Ausnahme entstünde eine Umleitungs-
  Schleife (Modul-Gate → „/“, Middleware → „/projektierung“).
- **„Angebote lesend“** für die Rolle Projektierung ist als Pfad-Whitelist
  umgesetzt: nur die Liste (`/angebote`) und das PDF (`/angebote/<id>/pdf`).
  Der Editor selbst bleibt gesperrt (dort stünden EK/DB); in der Liste ist
  die DB-Spalte an `kalkulation_sichtbar` geknüpft und der Öffnen-Knopf
  durch einen PDF-Knopf ersetzt.
- **Fotos für die Rolle Montage** laufen über einen eigenen Lesepfad
  `/montage/dokument/<id>`, weil `/projektierung/...` für die Rolle gesperrt
  ist; der Upload landet im Gewerk-Ordner „03 Fotos/Neue Anlage“.
- **„Montage gestartet“** nutzt den normalen Phasenwechsel mit Begründung
  „Montage gestartet (mobil)“ – ein blockierender Wächter wird damit als
  protokollierter Override passiert (Konzept: kein hartes Sperren).
- **Team-Zuordnung** liegt als Häkchen-Spalte in der Benutzerverwaltung
  (nicht auf der Teams-Stammseite): eine Pflegemaske je Benutzer, die
  Teams-Seite zeigt die Mitglieder nur an.
- **Einsatz-Sichtbarkeit Montage**: Termine der eigenen Teams sowie direkt
  als Person zugeteilte Termine; Admin sieht alle (für die Demo).

## Phase 74 (PLAN_PROJ_V2, 26.09.2026)

- **Schreibweise Terminstatus:** Der Plan schreibt einmal „untermininiert" –
  umgesetzt als `unterminiert` (Anzeigename „Unterminiert").
- **Wächter-Fallbacks bis Phase 78** (die V2-Pakete existieren noch nicht):
  Auftragseingang → Feinplanung VOT prüft das Paket „Auftragseingang" nur,
  wenn eine solche Paket-Instanz am Gewerk aktiv ist (V1-Paket heißt genauso –
  greift also auch für Altbestand). Planung → Montagevorbereitung prüft die
  Pakete „Planung WP / Planung Elektro / (Friondo) Fit for Future"; solange
  keines existiert, gilt wie in V1 die Gesamt-Ampel (alle Pflichtaufgaben).
  Montagevorbereitung → Montage verlangt die Aufgabe „Projekt zur Montage
  freigegeben" nur, wenn sie existiert (kommt mit Paket Montagevorbereitung
  v2 in Phase 78); der Montagetermin mit Team/Person ist immer Pflicht.
- **„Termin ohne Team":** Ein bestätigter Montagetermin ohne Team zählt als
  `unbestaetigt` (gelbes Badge mit Text „Termin ohne Team · Datum") – erst
  Team + Bestätigung ergeben grün, wie im Plan definiert.
- **Maßgeblicher Montagetermin** für den Terminstatus: der früheste
  zukünftige; gibt es nur vergangene, der letzte.
- **Kacheln:** Startportal zeigt laut Plan sechs Phasen + „Unterminiert"
  (die bisherige Überfällig-Kachel entfällt dort). Im Board-Kopf bleiben
  zusätzlich die Überfällig-Kachel (Link „Meine Aufgaben") und neu die
  Unterminiert-Kachel (Link Liste mit Filter) erhalten.
- **„Feinplanung erfasst":** als Häkchen am Gewerk (Spalten
  `feinplanung_erfasst`/`_am`, Route `/projektierung/gewerk/<id>/
  feinplanung-erfasst`, Verlaufseintrag). Phase 80 ersetzt das Häkchen durch
  den Abschluss der Feinplanungs-Erfassung.
- **Migration feinplanung → planung:** Das Plan-Kriterium „Feinplanungs-
  Erfassung abgeschlossen" existiert in V1-Daten nicht; das neue Häkchen ist
  bei Bestandsgewerken immer leer, daher wandern alle „feinplanung"-Gewerke
  nach Auftragseingang (der Sonderweg nach Planung ist implementiert und
  greift, sobald das Häkchen vor einer erneuten Migration gesetzt wäre).
- **Prototyp:** Die Terminstatus-Badges (`.pj-ts g/y/r`, kleine Variante
  `.s`) wurden gemäß Design-Regel zuerst im Prototyp
  `docs/projektierung-prototyp.html` ergänzt und dann in style.css
  übernommen.
- **Montage-Backend:** „Montage gestartet" setzt jetzt Phase `montage`,
  „Montage fertig" setzt `abnahme_freigabe` (vorher in_ausfuehrung/
  abnahme_offen); erlaubt ist der Start aus allen Phasen vor Montage.

## Phase 75 (26.09.2026)

- **Team-Typen:** neu `montage` / `sub`; Alt-Typen (SHK/Elektro/Sonstige)
  bleiben lesbar und zählen im Kalender zu den Montage-Zeilen. Der Seed legt
  „Montageteam 1–10" und „Subteam 1–5" idempotent **je Name** an – umbenannte
  Teams werden bei erneuter Migration nicht neu erzeugt, gelöschte schon
  (gewollt: Stammdaten „fest angelegt").
- **Ende-Vorbelegung** (+4 Arbeitstage) läuft doppelt: im Dialog per JS beim
  Setzen des Beginns und serverseitig, falls Ende leer ankommt.
- **Kalender-Drag:** Drop in eine andere Team-Zeile wechselt zusätzlich zum
  Datum auch das Team des Termins (protokolliert) – der Plan nennt nur das
  Datum, Zeile = Team macht den Teamwechsel aber zur natürlichen Geste.
  „Ende ziehen" nutzt einen eigenen Griff (▐) am Balken.
- **„ohne Team"-Zeile** erscheint nur, wenn es Montagetermine ohne Team gibt
  (Altbestand); Neuanlagen erzwingen seit dieser Phase ein Team.
- **Montagetermin-Pflichtteam** gilt für die Termin-Dialoge der Akte und den
  Zuweisungsdialog; die Terminübersicht (/projektierung/termine) nutzt
  dieselbe Route und erbt die Prüfung.

## Phase 76 (26.09.2026)

- **Galerie ersetzt die Projekt-Ordnerstruktur als führende Ablage:** Der
  Dokumente-Reiter der Projektakte zeigt jetzt die Vorgangs-Galerie; die alte
  Ordnerstruktur bleibt eingeklappt als „Restbestand" sichtbar (nach der
  Migration normalerweise leer). Der Heizlast-/Projekt-Upload existiert
  weiter, neue Ablagen laufen über die Galerie.
- **Migration-Mapping über Teilstrings** („Alte Anlage" → Alte Heizung usw.);
  „02 Feinplanung & Heizlast" wandert nach Montagedokumente, unbekannte
  Ordner (inkl. 01/04/06) nach Allgemein. Angebots-PDFs liegen am Angebot
  und waren nie ProjektDokumente – nichts zu tun.
- **Original behalten** ist ein Parametrierungs-Schalter
  (galerie_original_behalten, Standard aus): an = Original als
  original_<name> neben der 2000-px-Fassung.
- **Erfassungs-Fotoblock** hängt an der Seite „Einschätzung" (Seitenname aus
  der Logik-Excel); der Vorgang wird dafür beim Seiten-Speichern über die
  bestehende vorgang_fuer_erfassung-Logik erzeugt/geholt.
- **Rechteprüfung der Datei-Auslieferung** nutzt dieselbe Regel wie der
  Upload (Vertrieb nur eigene Vorgänge) – Montage folgt in Phase 82.

## Phase 77 (26.09.2026)

- **Regel-Syntax im Blatt „Steckbrief":** `wert_oder_regel` kennt drei Formen:
  fester Text (typisch für Positionsregeln), leer (= Antwort wird 1:1
  übernommen, z. B. Öltank-Größe) und Mapping `Antwort→Text | Antwort2→Text2 |
  *→Text` (Pfeil U+2192, `*` = alles andere; `*→` ohne Text heißt „kein
  Eintrag"). Groß-/Kleinschreibung der Antwort ist egal.
- **Erste passende Regel je Feld gewinnt** (Blattreihenfolge = Priorität);
  z. B. steht Pos. 055 (AWMB) vor dem Bereich 045-049 (AWM), damit die
  Varianten-Position das Paket schlägt. Positionsangaben: Slash-Liste und
  Bereiche („045-056"); nackte Zahlen werden auf 3 Stellen aufgefüllt.
- **Manuell-Schutz:** Jede Änderung über die Akte setzt `manuell` am
  SteckbriefWert; Ableitung (bei Projektanlage und „Neu ableiten")
  überschreibt solche Felder nie. Kennzeichen in der Akte: ✎.
- **Ableitung bei Projektanlage ist fehlertolerant** (try/except): eine
  kaputte Regel darf die Projektanlage nie blockieren.
- **quelle_typ `fp_frage` ist vorbereitet** (Parameter fp_antworten der
  Ableitung), wird aber erst mit der Feinplanungs-Erfassung in Phase 80
  befüllt.
- **Unsicheres in der Blatt-Befüllung (Andreas ergänzt später):**
  - **Folierung** hat keine Quelle in der Vertriebs-Erfassung – Feld bleibt
    leer (manuell bzw. FP-Frage in Phase 80).
  - **PV-Regeln** fehlen bis auf die Dach-Frage: die PV-Positionsnummern sind
    im Tool noch nicht im Einsatz (PV-Aufträge laufen bislang über TAIFUN).
  - **E03-Mapping** (Zählerschrank 2-/3-/4-Feld) nimmt die heutigen
    Antworttexte der Erfassung an („2-Feld", „3-Feld", „4-Feld und mehr") –
    falls die Logik-Excel dort andere Texte nutzt, Blatt anpassen.
  - **Hersteller** ist pauschal „Bosch", solange nur Bosch-Pakete im
    Artikelstamm sind (Positionen 030/031/045-056).

## Phase 78 (26.09.2026)

- **Neue Blatt-Spalten** aktion_typ/aktion_wert/optionen/frist_tage/
  frist_bezug/sichtbar_wenn; frist_tage+frist_bezug werden beim Einlesen auf
  die bestehende faellig_regel-Mechanik abgebildet (aktivierung→+N,
  feinplanung→FP±N, montage→M±N), die Nachberechnung beim Terminanlegen
  greift damit unverändert.
- **Auswahl-Semantik:** Option mit `*` → Aufgabe erledigt; Option ohne `*`
  (z. B. „erfolgt bauseits", „nicht erforderlich") → Status „entfällt"
  (beantwortet, zählt nicht als offene Pflicht); Auswahl leeren → wieder
  offen. Bei „Ja* | Nein*" gelten beide Antworten als erledigt.
- **auswahl + mail kombiniert:** trägt eine Auswahl-Aufgabe in aktion_wert
  `mail:<Sub-Typ>@<Ordner>`, erscheint zusätzlich der Mail-Knopf
  (deaktiviert bis Phase 79).
- **sichtbar_wenn** (`steckbrief:<feld>=<wert>`): nicht erfüllte Schritte
  werden bei der Paket-Aktivierung gar nicht erst angelegt (Folierung).
  Ändert sich der Steckbrief später, Paket entfernen und neu aktivieren
  oder Aufgabe manuell ergänzen.
- **Galerie-Häkchen** prüft beim Öffnen der Projektakte, ob in allen in
  aktion_wert genannten Ordnern mindestens ein BILD des Vorgangs liegt,
  und erledigt die Aufgabe automatisch.
- **Link-/api-Aufgaben:** aktion_wert `param:<schlüssel>` löst auf die neuen
  Parametrierungs-URLs auf (url_bza_portal, url_spotmyenergy,
  url_heizreport); ohne gepflegte URL erscheint ein Hinweis statt Button.
  Der Klick setzt die Aufgabe per fetch auf „in Arbeit". api-Aufgaben
  (heizreport, ugl_collin) rendern bis Phase 80 Link + Galerie-Ablage.
- **Förderung bleibt eigenes WP-Paket** (Antrag/Zusage/BnD) – nur der
  BzA-Schritt ist in den Auftragseingang gewandert; sonst verlöre BnD nach
  Abnahme seine Heimat. Fit for Future wird IMMER aktiviert (die erste
  Auswahl-Aufgabe „HEMS geplant Ja/Nein" ersetzt die alte FP-A05-Regel).
- **V1-Migration:** die Instanzen der ersetzten bzw. inhaltlich geänderten
  Pakete (alte WP-Pakete + auftragseingang/montagevorbereitung/foerderung)
  werden als V1 markiert; unveränderte (abnahme_freigabe, pv/wb/kl_standard)
  behalten ihren Stand. paket_aktivieren ignoriert V1-Instanzen, damit die
  v2-Pakete zusätzlich aktiviert werden können; „V1-Aufgaben entfernen"
  löscht Instanzen samt Aufgaben mit Verlaufseintrag.
- **Paket-Reihenfolge/Aufklappen:** Rang über den Paketnamen (Auftragseingang
  0 … Abnahme & Freigabe 5, unbekannte Pakete 4); aufgeklappt ist das nicht
  fertige Paket, dessen Rang der aktuellen Gewerk-Phase entspricht.
- **Restarbeiten/Reklamationen** als eigene Tabelle am Gewerk; ein Foto
  wandert in die Galerie „Inbetrieb-/Abnahme" (quelle formular) und wird
  verknüpft. Block erscheint ab Phase Montage oder sobald Einträge da sind.
- **Zählerwechseltermin** ist ein Datumsfeld am WP-Gewerk (KV-Zeile) und
  erscheint als violetter Marker (zw) in der Zeile des WP-Teams bzw.
  „ohne Team" im Kalender.
- **BzA-Datenblatt-Knopf** an der Auftragseingangs-Aufgabe folgt mit der
  Datenblatt-Seite in Phase 80 (bis dahin nur der Portal-Link).

## Phase 79 (26.09.2026)

- **Versandweg:** neue generische Funktion graph_versand.
  mail_mit_anhaengen_senden (Entwurf → Einzel-Anhänge als Bytes → /send),
  weil nur so die conversationId für die Antwort-Erkennung bekannt wird.
  Absender ist das Projektierungs-Postfach (Parameter absender_postfach,
  Standard projektierung@friondo.de); schlägt „Senden als" fehl, folgt ein
  zweiter Versuch über das angemeldete Postfach. CC geht an den
  Projektleiter (dessen Benutzer-E-Mail).
- **Foto-Anhänge** werden beim Versand auf 1600 px verkleinert (JPEG 85 %);
  bei Überschreiten der 20-MB-Grenze werden weitere Fotos weggelassen und
  in der Erfolgsmeldung ausgewiesen. Das Steckbrief-PDF (steckbrief_pdf.py,
  eine Seite nach protokoll_pdf-Muster) hängt an, wenn die Vorlage
  anhang_steckbrief=J hat (im Dialog abwählbar).
- **Dialog als eigene Seite** (/projektierung/aufgabe/<id>/sub-mail) statt
  <dialog>, weil Foto-Vorschauen und vorbefüllte Texte je Aufgabe geladen
  werden; erreichbar über „✉ Mail senden" an Auswahl-Aufgaben mit
  aktion_wert mail:<Typ>@<Ordner>. Die Ordner der Vorlage haben Vorrang
  vor dem Ordner aus aktion_wert.
- **Termin-Anfrage-Zeile:** steckt als Satz in den Vorlagen („Bitte
  antworten Sie … mit Ihrem frühesten Termin"), der Montagetermin kommt
  über {montagetermin}; keine eigene Formular-Mechanik.
- **Folgeaktionen des Versands:** ProjektSub (Status angefragt,
  graph_conversation_id, angefragt_am), Eintrag im neuen Projekt-
  Mail-Verlauf (ProjektMail), Verlaufseintrag, und die Aufgabe springt auf
  die mit * markierte „beauftragt"-Option.
- **Antwort-Erkennung:** sub_mail.antworten_abgleichen läuft im
  15-Minuten-Scheduler von mail_sync, liest das Projektierungs-Postfach
  je Konversation der offenen Anfragen (angefragt/beauftragt), legt neue
  Nachrichten dedupliziert in ProjektMail ab und setzt beim ersten
  eingehenden Treffer antwort_am + Benachrichtigung. Die Akte zeigt dann
  „Antwort erhalten – als bestätigt markieren" (Status wird NICHT
  automatisch umgestellt, nur vorgeschlagen).
- **Standard-Sub je Typ** liegt als Parameter sub_standards (JSON
  {typ: sub_id}), gepflegt über eine Standard-Checkbox in der
  Subunternehmer-Tabelle; er belegt die Sub-Auswahl im Mail-Dialog vor.
- **Test ohne M365-Anmeldung:** der Phasentest mockt den Graph-Versand und
  den Konversationsabruf; der echte Testversand an eine Testadresse ist
  beim Server-Rollout mit angemeldetem Konto nachzuholen (Lead-Chat).

## Phase 80 (26.09.2026)

- **FP-Erfassung ohne eigenes Modell:** Antworten/Vorbelegung/Seite/Abschluss
  liegen als Felder am Gewerk (fp_antworten_json usw.) – die Vertriebs-
  Erfassung bleibt unangetastet, die FP-Erfassung ist bewusst leichter
  (keine Ampel, keine Artikel-Aktionen). Fragen-Keys FP-A/E/O/H/L nach
  Seiten; Andreas ersetzt die Startfragen später durch das TAIFUN-Formular.
- **„vom Vertrieb"-Markierung:** Vorbelegte Antworten (Spalte
  vorbelegung_aus) tragen ein Badge; das Speichern der jeweiligen Seite
  gilt als Bestätigung und entfernt die Markierung.
- **fp_frage-Regeln stehen im Steckbrief-Blatt VOR den Vertriebsregeln**
  (erste passende Regel je Feld gewinnt): beim FP-Abschluss überschreiben
  sie nicht-manuelle Vertriebswerte, bei der Projektanlage (ohne
  FP-Antworten) greifen weiterhin die Vertriebsregeln.
- **FP-Abschluss** setzt zusätzlich das Häkchen „Feinplanung erfasst"
  (Wächter), übernimmt FP-L01 in die Heizlast-Felder, erledigt die
  Formular-Aufgabe feinplanung_wp und wertet bedingte Paketregeln
  (bedingung `KEY=Wert` gegen die FP-Antworten) aus – das Blatt enthält
  derzeit nur IMMER-Regeln, die Mechanik steht für später.
- **Heizreport:** heizreport_api.py ist ein sauberer Stub (Parameter
  heizreport_api_url/_key), aktiv erst mit API-Doku; bis dahin Link
  (url_heizreport) + PDF-Upload in „Montagedokumente" + Heizlast-Felder.
- **UGL:** Feldbelegung der Sätze KOP/ADR/POA/END ist vereinfacht nach
  UGL 4.0 (200 Byte, latin-1, CRLF, Anfrageart BE) – beim ersten echten
  Upload in GC Online Plus mit Collin abgleichen. Lieferdatum =
  Montagebeginn − 3 Werktage (ohne Termin: heute + 7 Tage). Z-Positionen
  (Arbeitspakete) werden nicht bestellt; Positionen ohne Stücklisten-
  Zuordnung erscheinen als Warnliste. Die Datei landet in der Galerie
  „Montagedokumente"; die api-Aufgabe springt nur auf „in Arbeit", weil
  die Bestellung in GC Online Plus manuell erfolgt. Stücklisten-Blatt
  enthält BEISPIEL-Artikelnummern – Andreas füllt echte Collin-Nummern.
- **BzA-Datenblatt** zieht Gebäudedaten aus kfw_json (O01/O02/O03/O05,
  K01–K04) mit Fallback auf die Erfassungs-Antworten, die Förderzeilen
  1:1 aus dem Förder-Editor-Ergebnis; Fachunternehmer ist der Parameter
  bza_fachunternehmer (Standard „Friondo GmbH"). Druck/PDF über die
  Browser-Druckfunktion (print-CSS blendet Knöpfe aus).

## Phase 81 (26.09.2026)

- **Outlook-Sync als best effort:** event_senden/loeschen fangen jede
  Exception; der Fehlertext landet am Termin (outlook_fehler) und die Akte
  zeigt „⚠ Outlook erneut senden". Gesynct werden Montage-, Feinplanungs-
  und Abnahmetermine beim Anlegen (Termin-Dialog, Team+Termin-Dialog) und
  beim Kalender-Drag; Rücklesen (Datum/Dauer) alle 15 Minuten im
  mail_sync-Scheduler mit Verlaufseintrag „Termin in Outlook verschoben
  von …" und Fälligkeits-Nachberechnung.
- **Beide Kalender-Wege** (Team-Postfächer über Team.outlook_adresse ODER
  gemeinsamer Kalender mit Kategorie = Teamname) sind implementiert; die
  Wahl steht in der Parametrierung, die Einrichtung in
  docs/graph-einrichtung.md (Calendars.ReadWrite.Shared).
- **Kalendereintrag:** Betreff „PR-… · Kunde · Sparte" (andere Typen mit
  Präfix), Ort = Ausführungsadresse, Text = die ersten 8 gefüllten
  Steckbrief-Felder + Akten-Link über den neuen Parameter basis_url.
- **Terminmail:** Vorlage (Betreff/Text/Vorbereitungs-Hinweis) liegt in der
  Parametrierung mit Platzhaltern wie bei den Sub-Mails; Versand über die
  Phase-79-Graph-Funktion (Konversation wird am Termin gemerkt). Die
  Kundenantwort setzt nur kunden_antwort_am + Benachrichtigung – bestätigt
  wird per Ein-Klick-Vorschlag in der Akte (bestaetigt_quelle=mail);
  das manuelle Häkchen (telefonisch) bleibt daneben bestehen.
- **Test ohne M365:** Graph-Aufrufe und Konversationsabruf sind im
  Phasentest gemockt; echter Rundlauf (Outlook-Eintrag, Verschieben,
  Kundenmail) ist beim Rollout mit angemeldetem Konto zu prüfen.

## Phase 82 (26.09.2026)

- **Startseite:** Team-Auswahl (Teams über TeamMitglied; bei genau einem
  Team direkt die Liste, Admin sieht alle Teams); chronologische Liste in
  Heute / Diese Woche / Danach mit eingeklapptem „Vergangene Einsätze".
  Der Wochenkalender ist mobil als Tagesliste Mo–So gebaut (statt des
  Desktop-Grids) – ein Tag pro Karte, Einsätze als Links, unbestätigte
  schraffiert.
- **Galerie für Montage:** Rolle montage erreicht in der Auth-Middleware
  gezielt nur die zwei Galerie-Routen (Datei ansehen, Upload); die Routen
  prüfen über galerie.darf_hochladen, dass der Vorgang zu einem Einsatz
  der eigenen Teams gehört (Team-Zuweisung am Gewerk oder Termin).
  Verschieben/Löschen bleiben komplett gesperrt.
- **Formulare** laufen generisch über das Blatt „Formulare" (49 Startfelder
  in 3 Formularen, Entwurf laut Plan – Andreas nimmt die Inhalte ab):
  seitenweise mit Zwischenspeichern (MontageFormular je Gewerk+Formular);
  Foto-Felder laden sofort in die Galerie (Zielordner = Spalte optionen),
  Unterschriften als Canvas → PNG-Daten-URL (Muster der Vor-Ort-Signatur).
- **Abschluss** erzeugt das PDF (fpdf2, Unterschriften eingebettet) in der
  Galerie „Inbetrieb-/Abnahme", erledigt die zugehörige Aufgabe im Paket
  Abnahme & Freigabe (Titel-Mapping) und übernimmt beim Abnahmeprotokoll
  jede Mängel-Zeile als Restarbeit (Frist als Textzusatz, Foto am ersten
  Eintrag). Erneutes Abschließen erzeugt ein neues PDF.
- **Kein Preiszugriff:** das Detail zeigt Positionen ohne Preise (V1) und
  bleibt auf /montage beschränkt; Ansprechpartner ist der Projektleiter
  (Name + E-Mail – Benutzer haben kein Telefonfeld).

## Phase 83 (26.09.2026)

- CLAUDE.md auf v15 gehoben (Abschnitt wörtlich aus PLAN_PROJ_V2);
  docs/projektierung.md um den V2-Überblick ergänzt,
  docs/graph-einrichtung.md trägt die Team-Kalender-Einrichtung.
- **Rollout bewusst offen** (Plan: „nach Absprache – Lead-Management-
  Chat!"): git push + update.bat + Migrationslog-Prüfung (Phasen-Umzug,
  Galerie-Umzug, Paket-V1-Kennzeichnung) erst nach Freigabe durch Andreas.
  Beim Rollout zusätzlich prüfen: echter Sub-Mail-Testversand, Outlook-
  Rundlauf, UGL-Datei mit Collin abstimmen, echte Collin-Artikelnummern
  im Blatt „Stücklisten".

## 27.09.2026 – Paket „Förderung" entfällt (Andreas)

- Das eigenständige WP-Paket „Förderung" ist komplett raus (Blatt
  Aufgabenpakete + Paketregel); die Punkte „Förderantrag durch Kunden
  gestellt" und „Zusage liegt vor" entfallen ersatzlos, der BzA-Punkt lag
  ohnehin schon im Auftragseingang.
- **„BnD nach Abnahme erstellt"** ist jetzt Schritt 6 im Paket
  **Abnahme & Freigabe** (M+10, Pflicht; Beschreibung weist darauf hin,
  ihn bei ungeförderten Aufträgen auf „entfällt" zu setzen – das Paket
  gilt für alle Sparten).
- Migration migration_bnd_abnahme: bestehende Förderungs-Instanzen samt
  Aufgaben gelöscht (28 Aufgaben lokal), der BnD-Punkt wurde an die
  aktiven Abnahme-&-Freigabe-Instanzen gehängt (5 lokal) – ein bereits
  erledigter BnD-Status wäre übernommen worden.

## 27.09.2026 – Nachtrag Abnahme & Freigabe (Andreas)

- Neuer Pflicht-Schritt 5 „Abweichungen zum Angebot geprüft, ggf. Nachtrag"
  (M+4) im Paket Abnahme & Freigabe, vor der Rechnungsfreigabe; „Rechnung
  freigegeben" und „BnD nach Abnahme erstellt" rücken auf 6/7. Migration
  migration_abweichung_abnahme ergänzt den Punkt an bestehenden offenen
  Gewerken (4 lokal) und zieht die Reihenfolge nach.

## 27.09.2026 – Galerie je Sparte + Foto-Sammelbox (Andreas)

- **V1-Aufgabenpakete restlos entfernt** (auch abgeschlossene/stornierte
  Gewerke, Migration migration_v1_restlos) – die Doppelung verwirrte.
- **Eigene Galerie je Sparte**: GalerieDatei.sparte (Bestand = WP); die
  Vorgangsakte zeigt Reiter je Sparte (aus Gewerken/Kunden-Interessen),
  Projekt- und Montageakte die Galerie der Gewerk-Sparte. Ordnersets:
  WP wie bisher; PV = Dachfläche · Zählerschrank · Speicher-Standort;
  KL = Innengeräte · Außengerät · Leitungsweg; WB = Stellplatz ·
  Zählerschrank · Leitungsweg; + gemeinsam Montagedokumente ·
  Inbetrieb-/Abnahme · Neue Anlage · Allgemein (Vorschlag – Namen bei
  Bedarf anpassen). Ablage neuer Dateien unter galerie/<sparte>/<ordner>;
  Verschieben nur innerhalb der Sparte.
- **Foto-Sammelbox** (Vorgangs-, Projekt- und Montageakte): mehrere Fotos
  nacheinander aufnehmen ODER mehrfach auswählen, je Foto den Zielordner
  im Vorschau-Raster zuweisen, EIN Upload am Ende (Route nimmt
  datei_ordner je Datei entgegen). Das capture-Attribut mit Sofort-Upload
  war der Grund für „ein Foto pro Upload"; im Erfassungs-Fotoblock wurde
  capture entfernt (Handy bietet dann Kamera UND Mehrfachauswahl).
- **Demo-Projekte** über scripts/demo_projekte.py (idempotent):
  PR „Demo Planung, Petra" (WP in Feinplanung VOT, Steckbrief aus der
  Erfassung, FP-Termin, Galerie-Reiter WP/PV) und „Demo Montage, Bernd"
  (WP in Montage, Montageteam 1 übermorgen bestätigt, FP abgeschlossen,
  Fotos in vier Ordnern – sichtbar im Team-Kalender und unter /montage).

## 27.09.2026 – Team-Zuweisung repariert, Benutzer-Seite neu (Andreas)

- **Bugfix:** Das Team-Dropdown im Dialog „Team + Termin" der Projektakte
  war leer (Variable `teams` fehlte im Kontext) – deshalb ließ sich kein
  Montageteam zuweisen. Die Zuordnung Mitarbeiter→Team unter Benutzer war
  korrekt gespeichert.
- **Benutzer-Seite entrümpelt:** kompakte Hauptzeile (Name, Rolle mit
  sprechenden Namen, E-Mail, Montageteam, Aktiv); PIN, Telefon,
  Benachrichtigungs-Mail, Kalkulation, Leadmanager-Häkchen, Zusatzrollen
  und Löschen liegen in einer aufklappbaren Details-Zeile. Team-Chips
  erscheinen NUR bei der Rolle Montage (live beim Rollenwechsel);
  Zusatzrollen sind als „Zusätzliche Module (Sonderfall)" erklärt.
  Neuer Benutzer: Team-Auswahl erscheint bei Rolle Montage, die
  Anlegen-Route übernimmt sie direkt. Die Änderungs-Route fasst Teams
  nur noch an, wenn das Formular sie mitschickt (teams_dabei) –
  vorher hätte ein Formular ohne Team-Block alle Zuordnungen gelöscht.
  Rollen-Erklärung als aufklappbarer Hilfetext unter der Seite.

## PLAN_PROJ_V4 (29.09.2026) – Umsetzung durch Claude Code

**Vorab – Abhängigkeit PLAN_PROJ_V3:** V4 setzt PLAN_PROJ_V3 (Phasen 84–86:
TAIFUN-Auftragsdaten, Bestandsimport, Go-live-Hilfen) als umgesetzt voraus –
im Code ist V3 **nicht** vorhanden (Plan ungebaut, 0 Häkchen). V4 wurde so
gebaut, dass es ohne V3 läuft; die Berührungspunkte sind je Phase notiert
(Bestandsimport-Vorlage, Auftragsdaten „gefördert“, Go-live-Checkliste,
Pilot-Sendesperre).

### Phase 90 – Kanban, Ampel, Termine, Bedienung

- **Auftragseingang zweigeteilt** nur im Board (Spalten-Schlüssel
  `auftragseingang_unterminiert` / `…_terminiert`); die Gewerk-Phase bleibt
  `auftragseingang`. „terminiert“ = Montagetermin vorhanden, auch
  unbestätigt oder ohne Team (Terminstatus ≠ unterminiert). Maßgeblich ist
  das Gewerk, das die Spalte bestimmt (Phase = Spalte, sonst erstes offenes).
- **Sortierung** überall `kern.sortierschluessel_chrono`: Montagebeginn
  aufsteigend, Unterminierte darunter nach **Gewerk-Anlagedatum**
  (= Auftragseingang im Tool; das Angebotsdatum kann Wochen älter sein).
  Die Liste hat „Montagebeginn“ als neue Standardsortierung; „PR-Nr.“ bleibt
  wählbar.
- **Drop „unterminiert → terminiert“** öffnet den Team-+-Termin-Dialog direkt
  im Board (Route `team-termin` mit `zurueck=/projektierung`); zurück per
  Drag ist gesperrt (Hinweis). Drop in eine der beiden AE-Spalten aus einer
  späteren Phase = Rückwärts-Wechsel nach `auftragseingang` (Begründung
  nötig, wie bisher).
- **Abnahme/Freigabe:** `abnahme_freigabe` bleibt nur als Altwert im
  Namens-Mapping (Anzeige vor der Migration). Migration
  `migration_abnahme_freigabe_split` hängt Aufgaben um; existiert am Gewerk
  bereits eine frisch aktivierte Instanz gleichen Pakets (Server-Update, bei
  dem die V2-Migration zuerst die neuen IMMER-Pakete aktiviert), erbt deren
  gleichnamige Aufgabe Status/Erledigt-Datum/Auswahl/Kommentare und die alte
  wird gelöscht – keine Doppel. Phasenentscheid zählt nur Pflichtaufgaben
  der Abnahme-Instanz (der Titel „Abweichungen zum Angebot geprüft“ existiert
  auch in Feinplanung VOT).
- **Rechnung freigeben** ist nur noch in Phase **Freigabe** möglich und hakt
  die Aufgabe „Rechnung freigegeben“ ab. Montage fertig (mobil) setzt
  `montage_fertig_am` auf die gewählte, gerundete Uhrzeit und wechselt nach
  `abnahme`.
- **Bestandsimport (Phase 85)** existiert nicht – die dortige
  Phasenwert-Anpassung entfällt; beim späteren Bau von V3 bitte „Abnahme“
  und „Freigabe“ als Phasenwerte vorsehen.
- **Vorlauf-Ampel:** Wochen = Kalendertage bis Montagebeginn ÷ 7; grün
  > 8, gelb 4–8 (inkl. Grenzen), rot < 4, unterminiert = rot. Parameter
  `vorlauf_gruen_ab_wochen` / `vorlauf_gelb_ab_wochen` (Migration belegt 8/4
  vor; Pflege unter Parametrierung → Projektierung-Einstellungen). Termin in der Vergangenheit bei Phase
  ≤ Montagevorbereitung = rot. Kachel „Unterminiert“ zeigt zusätzlich
  „+ n rot (< 4 Wochen)“ = terminierte Gewerke mit roter Ampel.
- **15-Minuten-Takt:** `step="900"` an allen Datum-Uhrzeit-Feldern der
  Projektierung (Termin-Dialog Akte, Terminübersicht) und neue Uhrzeit-Felder
  „Montage gestartet/fertig“ im Montage-Backend; Vorbelegung auf das nächste
  Viertel und Client-Rundung in `static/projektierung.js`, serverseitig
  `kern.viertelstunde` (kaufmännisch, 7:52 → 7:45, 7:53 → 8:00).
  Ganztägige Montagetermine (Team + Termin, Kalender-Drag) bleiben
  tagesgenau; Zählerwechsel ist ein Datum (unverändert).
- **Ohne Seitensprung:** fetch mit `Accept: application/json` für Aufgaben-
  Häkchen, Status/Verantwortlicher, Auswahl, Aufgaben-Kommentar, Restarbeiten-
  Häkchen, Steckbrief-Feld, Zuweisung und Heizlast (JSON mit Zeilen-HTML aus
  dem Partial `projektierung/_aufgabe.html`, Paket-Zählern, Planungs-Ampel
  und Wächter-Hinweis „✓ Wächter für … erfüllt“). Alle anderen POSTs der
  Projektierung/Montage: Scroll-Position je URL in sessionStorage (auch für
  `form.submit()` aus onchange-Handlern), Redirects mit Anker
  `#aufgabe-<id>`. Ohne JavaScript bleiben alle Routen per Redirect nutzbar.
  Dokument-Upload bleibt ein klassischer POST (Datei) mit Scroll-Erhalt.
- **Aufgabe „<Team> zuweisen“** (kalender/montage) wird durch „Team +
  Termin“ automatisch erledigt (Titel = „Montageteam zuweisen“ bzw.
  „Elektro-Montageteam zuweisen“).

### Phase 91 – Aufgabenpakete, Feinplanung, Sub-Mails, Fit for Future

- **Sparten-Bedingung für Schritte:** `sichtbar_wenn = sparte:PV|KL|WB` (neu
  neben `steckbrief:`). Damit steht „Auftragsunterlagen prüfen“ für WP als
  Schritt 1 in Planung WP und für PV/KL/WB als Schritt 5 im Auftragseingang
  (zwei Blatt-Zeilen; keine bestehende Zeile gelöscht, nur verschoben).
- **„Montageteam zuweisen“** ist Pflicht (Annahme 2 des Plans) und wird
  durch „Team + Termin“ automatisch erledigt. Migration: WP-Gewerke hängen
  die bestehende Aufgabe mit Status um; Gewerke ohne Planung WP bekommen
  den Schritt nur, wenn sie noch im Auftragseingang stehen (bei weiter
  fortgeschrittenen Gewerken hätte ein neuer offener Pflichtschritt die
  kumulativen Wächter späterer Wechsel blockiert); existiert schon ein
  Montagetermin, wird er gleich erledigt angelegt.
- **Fit for Future:** Steckbrief-Bezug steht im `aktion_wert`
  (`steckbrief:hems`, `param:url_spotmyenergy;steckbrief:imsys` …). Die Akte
  wählt den Steckbrief-Wert vor, erledigt ist die Aufgabe erst nach
  „Übernehmen“; jede Auswahl schreibt ja/nein zurück (Kennzeichen manuell).
- **Laufzeit-Bedingung** `fit_for_future.1=Ja` (HEMS-Inbetriebnahme): der
  Schritt wird immer angelegt (neue Spalte `aufgaben.sichtbar_wenn`) und
  steht auf „entfällt“, solange HEMS = Nein ist; bei Ja zurück auf „offen“.
  Im Board/Wächter zählen entfallene Aufgaben nicht.
- **FP-Fragen:** FP-E05 iMSys / FP-E06 HEMS (vorbelegt aus P02/P01),
  FP-O04 Restöl mit neuer Spalte H `sichtbar_wenn` im Blatt „Fragen FP-WP“
  (`FP-O01=Ja`; ausgeblendete Fragen sind nie Pflicht, live ein-/ausgeblendet).
- **Steckbrief-Zeilen:** neue `quelle_typ` **fest** (Standardwert, wenn
  keine Regel davor griff) und Platzhalter **{menge}** (Summe der voll
  berechneten Positionsmengen) bzw. **{wert}** (Antwort) in Regeln.
- **WIDERSPRUCH Plan ↔ Code, entschieden im Sinne des Konzepts:** Der Plan
  nennt für `erdleitung_m` die Pos. 139/140 und als Fallback D07/D08 – laut
  Artikelstamm und CLAUDE.md sind das die **Dachzentralen-Rohrleitungen**
  (Heizung bzw. Warmwasser). Die Erdleitung Außengerät ↔ Haus ist
  **Pos. 102** (Menge = A05 − 3 m). Umgesetzt: `erdleitung_m ← Pos. 102`
  („{menge} m“), Fallback Erfassung **A05** (volle Grabenlänge). Annahme 8
  des Plans sieht genau diese Anpassung vor; die Zeile ist in der Excel
  änderbar.
- **Stemmarbeiten:** Pos. 126 („ja (Pos. 126, Menge n)“), Fallback A16,
  sonst „nein“. **TAIFUN-Aufträge:** das Auftragsdaten-Formular (Phase 84)
  existiert nicht – beide Felder sind wie alle Steckbrief-Felder in der
  Akte per Klick editierbar.
- **Sub-Mailvorlagen:** GaLa-Bau ergänzt um den Absatz „Erdarbeiten“ +
  Fundament-Hinweis, Entsorgung um {restoel} und {stemmarbeiten}
  (bestehender Text blieb, Absätze eingefügt).
