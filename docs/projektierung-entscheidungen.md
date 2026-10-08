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
  UGL 4.0 (200 Byte, cp850 (seit Phase 93, siehe unten), CRLF, Anfrageart BE) – beim ersten echten
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

### Phase 92 – BzA: Link, BzA-ID, Kundenmail, KfW-Felder

- Neuer Aktionstyp **bza** (Blatt Aufgabenpakete): Auftragseingang Schritt 4
  „BzA erstellen und an Kunden senden“ zeigt Portal ↗ · Datenblatt · BzA
  erfassen; aktion_wert `kfw` = Montagevorbereitung Schritt 4
  „KfW-Antragsnummer/Zusage eingetragen“ (pflicht N, Eingabefelder, kein
  Wächter – CEO-Review Entscheidung 2 offen). Die Portal-URL bleibt unter
  dem bestehenden Parameter **url_bza_portal** (der Plan nennt `url_bza`);
  fehlt sie, führt der Knopf zu den Projektierung-Einstellungen.
- **Gefördert?** Tool-Angebot mit KfW-Daten und nicht ausgeblendetem
  Förderblock = gefördert; ohne = „entfällt (nicht gefördert)“ statt der
  Buttons. **TAIFUN-Aufträge:** das Auftragsdaten-Feld „gefördert“ (PLAN_PROJ_V3
  Phase 84) existiert nicht → Status „unbekannt“: Buttons UND
  „entfällt“-Knopf werden angeboten.
- **Galerie-Ordner „Förderung“** ist neuer Standardordner aller Sparten
  (direkt hinter Montagedokumente); das BzA-PDF landet dort (Pflicht, .pdf).
- **Kundenmail „BzA“:** Vorlage (Betreff/Text) in den Projektierung-
  Einstellungen, Startinhalt laut Plan; Platzhalter {briefanrede} {kunde}
  {projektnummer} {bza_id} {link_kfw} {foerderbetrag}
  {ansprechpartner_friondo}. Ohne bekannten Förderbetrag (TAIFUN, ungefördert)
  entfallen alle Textzeilen mit {foerderbetrag}. Betrag = Zuschuss aus dem
  Förder-Editor (kfw.ergebnis_fuer_angebot). Versand über Graph wie die
  Sub-Mails (projektierung@, Fallback angebot@, CC Projektleiter), Eintrag im
  Mail-Verlauf des Projekts, Aufgabe → erledigt, `bza_gesendet_am`.
- **Demo-/Pilot-Sperre:** eine „bestehende Sendesperre/Testadresse der
  Projektierung“ gab es nicht (gehört zu PLAN_PROJ_V3). Neu: Parameter
  **projekt_testadresse**; solange das Modul im Demo-Modus
  (`freigabe_modus = admin`) steht, geht die BzA-Mail ausschließlich an diese
  Adresse – ist sie leer, wird nicht versendet (Hinweis in der Vorschau).
- Anzeige des BzA/KfW-Stands im Steckbrief-Block „Förderung“ (Akte und
  Vorgangsakte über dasselbe Makro), im Steckbrief-PDF und auf dem
  BzA-Datenblatt (Gruppe „Stand BzA / KfW“, nicht als „fehlend“ gewertet).
- Migration `migration_bza_v4`: bestehende BzA-Link-Aufgaben → Typ bza mit
  neuem Titel (Status bleibt); KfW-Schritt an offene Gewerke mit aktiver
  Montagevorbereitung.

### Phase 93 – Heizreport-API, UGL, Docs

- **Heizreport – Recherche:** `https://heizreport.de/api/` antwortet mit
  HTTP 400 „kein JSON Object empfangen“ (JSON-POST erwartet); die Hilfeseiten
  zur API sind ohne Login 404, lesbar ist nur die Webhook-Hilfe (`event`,
  `authenticate`, `projektKey`). **Keine öffentliche Doku** – Details und
  Anfragetext in docs/heizreport-api.md.
- **Heizreport – Client:** generisch (Basis-URL, Auth-Art header/bearer/basic/
  **body**, Header-/Feldname, drei Endpunkte mit Methode, Mapping hin/zurück
  als JSON). Auth-Art „body“ ergänzt, weil die Recherche auf `apiKey` im
  JSON-Body deutet. Der Schlüssel wird im Formular nie angezeigt; leeres Feld
  = unverändert, eigenes Häkchen zum Entfernen. „Verbindung testen“ übernimmt
  zuerst die Formularwerte der Heizreport-Felder und zeigt HTTP-Code +
  Antwortauszug (auch 4xx gilt als „erreichbar“). Neue Gewerk-Spalten
  `heizreport_projekt_key`, `heizlast_quelle` („Heizreport API“ bzw.
  „manuell“ bei Handeingabe). Webhooks nicht angebunden (Tool nicht
  öffentlich erreichbar).
- **UGL – Format:** gegen „UGL Version 4 – Beschreibung Datenaustausch“
  neu geschrieben (Feldtabelle docs/ugl-format.md). Abweichungen vom Plan /
  Annahmen: **POT statt POZ** (POZ = Zuschläge laut Spezifikation), Zeichensatz
  **cp850**, Dokumentdatum `JJJJMMTT` (Spezifikation: „JJJMMTT“ bei 8 Stellen),
  Dateiname `PR-….ugl` / `PR-…-2.ugl` statt `A<JJJMMTT>.<nnn>` (manueller
  Upload; Umstellung trivial). Lieferantennummer (KOP 14–23) als neuer
  Parameter `collin_lieferantennummer`, optional. Mengen je Artikelnummer
  über alle Positionen summiert; POT nennt die Herkunftspositionen.
  `.gitattributes`: `*.ugl binary`, damit CR/LF und cp850 im Repo byte-genau
  bleiben.
- **UGL – Bestellungen:** neue Tabelle `ugl_bestellungen` (nr, Datei,
  Lieferdatum, -adresse, Bemerkung, hochgeladen_am). Erzeugen setzt die
  Aufgabe auf „in Arbeit“, erst „✓ hochgeladen“ erledigt sie. Jede weitere
  Datei = Nachbestellung (`-2`, `-3` …, Verlaufseintrag,
  „Nachbestellung“ im Auftragstext und Endesatz).
- **Stücklisten-Pflege:** Liste = aktive Artikel mit Positionsnummer ohne
  Z-Pakete (339 im Dev-Stamm) + Stücklisten zu Positionen außerhalb des
  Stamms. Neue Spalte F `mengeneinheit` im Blatt (Standard ST). Bearbeitet
  wird immer eine Position im Editor oben (`?pos=`), damit die Seite nicht
  340 Formulare lädt. Rückschreiben: Blatt komplett neu (sortiert), Backup in
  `data/backups`, Cache neu laden. Zugriff Admin/Innendienst/Projektierung
  (Pfad in PROJEKTIERUNG_PFADE ergänzt); das Go-live-Häkchen setzt nur Admin.
  Parameter `stueckliste_standard_lieferant` (Vorbelegung neuer Zeilen).
- **Go-live-Prüfpunkte:** Die Go-live-Checkliste aus PLAN_PROJ_V3 Phase 86
  existiert nicht – die beiden Prüfpunkte („Stücklisten ≥ 90 % zugeordnet“
  automatisch, „Testdatei von Collin bestätigt“ als Häkchen mit Datum/Name,
  Parameter `ugl_testdatei_bestaetigt`) stehen deshalb oben auf der
  Stücklisten-Seite; beim Bau von V3 dorthin verlinken.
- **RISIKO Server-Update:** `projektierung_logik_v1.xlsx` ist git-verfolgt.
  Speichern in der Stücklisten-Pflege (wie schon der Excel-Upload) ändert die
  Datei auf dem Server; `update.bat` (`git pull --ff-only`) bricht dann ab,
  sobald ein Update dieselbe Datei mitbringt. Vorgehen: vor dem Update die
  Server-Datei sichern/herunterladen und in den Master übernehmen oder
  `git checkout -- projektierung_logik_v1.xlsx` vor dem Pull und danach die
  Stücklisten per CSV-Import zurückspielen. Langfristig: Stücklisten aus
  der Excel in eine DB-Tabelle verlagern (Excel nur noch Import/Export).
- **IDS-Connect** bleibt Schalter ohne Funktion.
- **Bestandsimport:** Phase 85 existiert nicht; die Phasenwerte für einen
  späteren Import sind in docs/projektierung.md dokumentiert.

## PLAN_PROJ_V3 (30.09.2026) – Umsetzung durch Claude Code (v18)

Gebaut NACH V4; Abgleich im Plan-Vorspann (PLAN_PROJ_V3_GOLIVE.md).

### Phase 84 – Auftragsdaten TAIFUN

- **Feldliste:** Die Steckbrief-Felder stehen weiter im Code
  (`STECKBRIEF_FELDER`, Anzeige-Reihenfolge); das Blatt „Steckbrief“ definiert
  das Formular über zwei neue Spalten F `eingabe` und G `bezeichnung` auf
  eigenen Zeilen mit `quelle_typ = auftragsdaten` (werden bei der Ableitung
  übersprungen). Zusatzfelder aus dem Blatt (serie_modell, puffer_l,
  unterverteilung, wallbox, anzahl) erscheinen automatisch im Steckbrief
  (vor „Besonderheiten“).
- **Vorrang:** manuell (✎) > FP-Erfassung > Auftragsdaten > übrige Ableitung.
  Auftragsdaten-Werte überschreibt nur eine `fp_frage`-Regel; danach ist die
  Herkunft wieder leer. Das Formular zeigt manuell geänderte Felder gesperrt.
- **„gefördert“** ist kein Steckbrief-Feld, sondern `angebote.kfw_gefoerdert`
  (dieselbe Quelle nutzt PLAN_V14 Phase 96 im „Extern erledigt“-Dialog).
- **Pflicht:** Die Seite ist Pflicht im Ablauf (Weiterleitung nach der
  Anlage, Badge „Auftragsdaten fehlen“ bis zum ersten Speichern,
  `gewerke.auftragsdaten_am`); einzelne Felder sind nicht Pflicht, nur das
  PDF, wenn noch keins am Eintrag liegt.
- **Pakete:** IMMER-Pakete kommen wie bei Tool-Angeboten mit der
  Gewerk-Anlage. Schritte mit `steckbrief:`-Bedingung, die mangels
  Steckbrief fehlten, legt `steckbrief_schritte_nachziehen` nach dem
  Speichern an (bestehende Aufgaben bleiben).

### Phase 85 – Bestandsimport

- Phasenwerte `abnahme`/`freigabe` (V4); „Abnahme & Freigabe“ wird mit
  Hinweis abgewiesen. Pflicht: Nachname, PLZ, Sparte, TAIFUN-Nr.,
  Auftragswert, Auftragsdatum, Phase; Projektleiter Pflicht, außer ein
  Standard-Projektleiter ist gesetzt. Unbekannte Vertriebler = Hinweis.
- **Dubletten:** Kunde über Nachname + Vorname + PLZ (erster Treffer). Die
  Server-DB enthält echte Namensdubletten (#1–#3) – vor dem echten Import
  zusammenführen oder bewusst akzeptieren.
- **Projekt-Zuordnung:** offenes Projekt des Vorgangs, außer dort existiert
  schon ein offenes Gewerk derselben Sparte → neues Projekt (Befund aus dem
  Trockenlauf).
- **Pauschal erledigt** werden nur Pflichtaufgaben aus Paketen mit
  Paket-Rang < Phasen-Rang (`paket_rang`), erledigt_von = importierender
  Admin, Verlaufseintrag je Gewerk. Montagetermin nur, wenn noch keiner
  existiert (zweiter Lauf verschiebt ihn); Team-Reihenfolge Montage >
  Elektro > Sub.
- **Keine Glocken-Flut:** `gewerk_anlegen(..., benachrichtigen_an=False)`.
- **Rückgängig:** nur Gewerke, die DIESER Import angelegt hat und die
  unverändert sind (gleiche Phase, gleicher `bestand_import_id`, keine
  späteren Aufgaben-Erledigungen/Verlaufseinträge/Handablagen). Projekt,
  Vorgang, Angebot, Kunde nur, wenn vom Import angelegt und leer.
  Nummernkreis PR wird nicht zurückgedreht.

### Phase 86 – Go-live-Hilfen

- `pilot`: Sichtbarkeit = Admin, Hauptrolle Projektierung/Montage (wie
  bisher immer) + Pilotliste. Glocke folgt `modul_sichtbar`.
- **Sendesperre:** nur im Demo (`admin`) an `projekt_testadresse`; im Pilot
  echter Versand (Stufe 1 laut Plan mit echten Sub-Mails/Kundenterminen).
- **Checkliste:** Testmail bewusst ohne Fallback auf angebot@ (sonst wäre
  ein fehlendes „Senden als“ unsichtbar). Stücklisten-Punkt verlangt ≥ 90 %
  UND keine `BEISPIEL-`Artikelnummern. Die alte Route
  `/parametrierung/stuecklisten/golive` bleibt als Kompatibilität bestehen,
  die Stücklisten-Seite verlinkt auf die Checkliste.


## PLAN_PROJ_V5 (06.10.2026) – Umsetzung durch Claude Code (v26)

Heizreport über die öffentliche Kunden-API v2, Montageteam-Dropdown,
Parametrierung neu gegliedert (Phasen 122–126). Projektierung bleibt im
eingestellten `freigabe_modus`.

### Annahmen A-1 … A-6 und ihre Auflösung

| Nr. | Annahme (PLAN_PROJ_V5) | Umsetzung |
|---|---|---|
| A-1 | Ein Team je Montage-Benutzer (Mehrfach bleibt möglich) | Dropdown `team_ids` mit „– kein Team –“; bei mehreren Teams je Team ein Dropdown untereinander, „+ weiteres Team“ / „×“; Speichern über die bestehende Route (leere Werte ignoriert, Dubletten dedupliziert). Nicht-Montage-Benutzer mit alter Zuordnung sehen ihre Dropdowns weiter (Aufräumen durch den Admin). |
| A-2 | Trennung Straße/Hausnummer | `heizreport_api.strasse_trennen`: letzter Block aus Ziffer + optionalem Buchstaben/Zusatz (`12`, `12a`, `12-14`) = Hausnummer, Rest = Straße; nicht trennbar → alles in `strasse`. |
| A-3 | Keine Verbrauchsumrechnung ohne bestätigte Einheit | `projektJahresverbrauch` nur bei `verbrauch_einheit[A01] = "kWh"`; bei `l`/`m3` wird A03 weggelassen, der Klartext steht in `bemerkungen`. |
| A-4 | Kein Deep-Link ins Heizreport-Projekt | Button „Heizreport öffnen ↗“ auf `url_heizreport`, daneben der Schlüssel zum Kopieren. |
| A-5 | Gesamtheizlast = Gebäudewert, ersatzweise Summe der Räume | Punktpfad `heizreport_pfad_heizlast` (Vorbelegung `results.summary.heatLoad` – **nicht am Referenzprojekt geprüft**, Schlüssel lag nicht vor), dann bekannte Kandidaten, dann Summe aus `results.roomHeatLoads`, zuletzt FBH-Räume; nichts gefunden → Meldung mit den Ergebnisschlüsseln, Gewerk unverändert. |
| A-6 | FP-L01/FP-L02 aus Heizreport vorbelegen | Nach „Heizlast abrufen“ werden leere FP-L01 (kW, eine Nachkommastelle) und FP-L02 („Heizreport“) vorbelegt, Badge „aus Heizreport“ (bisher nur „vom Vertrieb“); beantwortete Felder bleiben. |

### Entscheidungen beim Bau

- **Modus-Schalter** `heizreport_modus` (v2 | generisch): der v17-Client bleibt
  vollständig erhalten (Modus generisch, aufklappbar); `konfiguriert()` = Token
  gesetzt (v2) bzw. Basis-URL + Schlüssel (generisch). Alter Test
  `test_projektierung_v4.py::Phase93Heizreport` setzt deshalb den Modus
  „generisch“ und nutzt die neue Testroute `/parametrierung/heizreport/test`.
- **HTTP-Nahtstelle** `heizreport_api._roh_anfrage` (eine Funktion für alle
  v2-Aufrufe und den PDF-Download) – Tests mocken sie; die Uhr der Warteschlange
  (`_uhr`, `_schlafen`) ist ebenfalls austauschbar.
- **Fehlerprotokoll ohne Request:** neue Funktion `fehlerprotokoll.eintragen_text`
  (Quelle als Fehlertyp, Meldung, Detail, Pfad) – Tokenwert wird vor dem Eintrag
  maskiert, der Authorization-Header nie geloggt.
- **Abgleich-Hinweis** als Verlaufseintrag `art = hinweis` am Gewerk (angezeigt an
  der Aufgabe und im Heizlast-Block der Akte); keine neue Spalte, kein Eingriff in
  Angebot/Steckbrief/Stückliste. Der letzte Hinweis bleibt sichtbar, bis ein
  neuer Abruf „passt“ ergibt (dann wird kein neuer Hinweis geschrieben, der alte
  bleibt im Verlauf lesbar – Anzeige zeigt den jeweils letzten `hinweis`-Eintrag).
- **Leistungsklasse aus der Paketmatrix-Heizlastspalte** (`klasse_fuer_heizlast`,
  dieselbe Zuordnung wie `konfigurator.leistungsklasse`): 8,0–9,9 kW → 7 kW,
  10,0–12,9 kW → 10 kW usw. Die Kontrollwerte des Plans (9 200 W → „10 kW“,
  6 500 W bei 7 kW → „passt“) widersprechen dieser Spalte – die Tests verwenden
  die Werte der Steuerdatei (11 200 W → 10 kW ≠ 7 kW → Hinweis; 9 200 W → 7 kW
  → passt); siehe Rückfrage. Eine separate „Unterdimensionierungs-Matrix“ gibt
  es im Code nicht (CLAUDE.md v8: sie ist die Heizlast-Spalte).
- **PDF-Dateiname** `Heizreport-<PR>-<Sparte>-<JJJJMMTT>.pdf`, zweites Dokument
  am selben Tag `…-2.pdf` (Zähler über die Galerie-Einträge des Ordners); Link
  nur `https://heizreport.net/…` (oder relativ), fremde Hosts werden abgelehnt;
  Download ohne Authorization-Header, Link nicht gespeichert.
- **Verknüpfung lösen** leert Schlüssel und `heizreport_angelegt_am`, nicht
  `heizreport_pdf_am` (die Sicherheitsabfrage bleibt – konservativ).
- **Parametrierung → Heizreport** in eigener Router-Datei
  (`app/routers/konfiguration_heizreport.py`); Änderungsprotokoll im Parameter
  `heizreport_protokoll` (letzte 30 Zeilen, Token nur als „gesetzt/entfernt“).
  Die Kennzahlen-Eingabe wird validiert (JSON-Objekt, Codes Zahl/null, Einheiten
  kWh/l/m3); Ungültiges wird nicht gespeichert.
- **migrate.py** legt die Parameter `heizreport_modus = v2`,
  `heizreport_kennzahlen` (leer), `heizreport_pdf_ordner = Montagedokumente`,
  `heizreport_pfad_heizlast` an; die Spalten `heizreport_angelegt_am`,
  `heizreport_pdf_am` kommen über `db._NACHTRAEGLICHE_SPALTEN`.
- **Montageteam-Dropdown:** Route `benutzer.py` unverändert (Dedup/Leerwerte
  waren schon abgedeckt); „×“ beim einzigen Dropdown ausgeblendet; Zusatzrollen-
  Häkchen ohne `ben-chip` (Plan-Test „Chips kommen nicht mehr vor“).

### Offen nach v26

- Ergebnis-Pfad und Kennzahlen am Referenzprojekt/Testprojekt bestätigen
  (Schlüssel, Token und Lizenz bei Andreas).
- Bedeutung der „Umkreisprüfung“ bei Berechnungen/PDF (Heizreport) erfragen.
- Stufe 2: Räume per API, Webhook, Bilder, Wärmepumpen-Check.
- Verwaiste CSS-Regeln `.ben-chip`/`.chips` in style.css (nur noch
  `docs/projektierung-prototyp.html` zeigt die Chips).

## PLAN_PROJ_V6 (08.10.2026) – Umsetzung durch Claude Code (v28), Teil P1: Phasen 133, 134, 135, 139

Pilot-Feedback 1: Wächter „warnen“, Aufgabe „entfällt“ mit Grund, Bedingungen
`foerderung:`/`steckbrief:` als Laufzeitbedingung, Board in voller Breite mit
Spalten-Scroll und Drop-Dialog, EIN Termin-Dialog mit Besetzung je Termin,
Terminvorschläge Stufe 1, Stücklisten-Konvention. Phasen 136–138 (Notizen-Chat,
Lightbox, Montage-Backend, Formulare) stehen im Abschnitt von Agent P2.
Umgesetzt und getestet gegen die DB-Kopie `diagnose/v28_patches/db_P1.db`
(`migrate.py` zweimal: zweiter Lauf „keine Änderungen nötig“).

### Annahmen und ihre Auflösung (Phasen 133/134/135/139)

| Nr. | Annahme | Umsetzung |
|---|---|---|
| P1-1 | Board-Spalten `flex: 1 1 0; min-width: 240px` (Plan) | So in `projektierung_v28.css`; Messwerte je Breite in `diagnose/v28_patches/p1_kontrollwerte.json` (bei 1 920 px mindestens sieben Spalten, bei 2 560 px alle neun). |
| P1-2 | `main.breit` volle Breite nur auf Projektierungs-Seiten | Der Plan verlangt `main.breit { max-width: none }` UND „Angebotstool- und Lead-Seiten bleiben wie bisher“ – beide nutzen `main.breit` (Portal, Hauptboard, Kundenkartei …). Gelöst über die Zusatzklasse `pj-voll` (`main.breit.pj-voll` in `projektierung_v28.css`, nur in den Projektierungs-Templates); `style.css` bleibt unverändert. Soll die volle Breite doch überall gelten: eine Zeile in `style.css` (`main.breit { max-width: none; padding: 2rem 16px; }`). |
| P1-3 | Vorschläge beginnen montags; Startadresse Firmensitz (Plan) | `kern.naechster_montag`, Parameter `montage_startadresse` (Standard Arnold-Overbeck-Str. 63-65, 47139 Duisburg); Fahrzeiten nur mit Routing-Anbieter (`routing_anbieter` ors/google mit Schlüssel), sonst Umweg „–“ und Hinweis. |
| P1-4 | Personen-Liste im Termin-Dialog = Projektierung + Innendienst + Admin | `kern.PERSON_ROLLEN`; Außendienst nicht enthalten (Rückfrage, siehe unten). |
| P1-5 | Go-live-Quote nur WP + spartenübergreifend | `stuecklisten._zaehlt_fuer_quote`: PV…/KL…-Positionen ohne Stücklisten-Zeile zählen nicht im Nenner; mit Zeile zählen sie wie alle anderen. |
| P1-6 | Bestehende Aufgaben tragen die Bedingung nicht | `migration_v28` trägt `sichtbar_wenn` (steckbrief:/foerderung:/`<paket>.<nr>=`) aus der Logik an bestehenden Aufgaben nach, ändert aber keinen Status – „entfällt“ setzt erst der nächste Nachzieh-Lauf (`abhaengige_pruefen` bei Auswahl-Klick, Auftragsdaten, Förder-Hook). Aktionstyp/Optionen bestehender Aufgaben bleiben unverändert (Regel „Änderungen wirken auf neue Aktivierungen“). |
| P1-7 | Von Hand gesetztes „entfällt“ hat Vorrang | `abhaengige_pruefen` öffnet nur Aufgaben wieder, deren Grund leer ist oder mit „Bedingung nicht erfüllt“ beginnt. |
| P1-8 | Aufgabenbezogene Kommentare bleiben im Projektverlauf | Das Kommentarfeld des Reiters Verlauf schreibt in den Notizen-Chat des Vorgangs (Vertrag mit P2); Kommentare mit `aufgabe_id` (💬-Zähler an der Aufgabe) bleiben `ProjektVerlauf` mit `art = kommentar`. |
| P1-9 | Besetzung bei Alt-Formularen | Kommt kein Feld `besetzung_gesetzt`, wird die Besetzung aus den Team-Mitgliedern vorbelegt (Bestandsimport, `team-termin`-Alias). |

### Phase 133 – Wächter „warnen“, „entfällt“, Bedingungen

- `kern.waechter_modus(session)` liest `waechter_modus` (warnen | sperren, Standard
  warnen; Parametrierung → Projektierung-Einstellungen → „Board & Wächter“, Änderung
  im Einstellungs-Protokoll). `phase_wechseln` behält Signatur und Rückgabe:
  warnen = Wechsel immer möglich, Verlauf „… – mit offenen Punkten: <Liste>“ bzw.
  „… – Begründung: <Text>“; sperren = bisheriger Override-Text. Rückwärts in beiden
  Modi nur mit Begründung; „abgeschlossen“ in beiden Modi nur über „Rechnung
  freigeben“ (vorher war ein Override mit Begründung möglich – bewusst geschlossen).
- Wächter-Logik in `waechter_bloecke` (Text + Aufgaben je Block); `waechter_pruefen`
  bleibt die Textliste, `waechter_details` liefert das JSON der Route
  `GET /projektierung/gewerk/{id}/waechter?ziel=` (`modus`, `rueckwaerts`, `offen`
  [{text, aufgabe_id, pflicht, gruppe}], `begruendung_pflicht`, `hinweis`, `sperre`).
  Die Prüfung bleibt kumulativ (alle Stufen bis zur Zielphase, wie seit v15).
- „entfällt“: `kern.aufgabe_entfaellt` / `aufgabe_wieder_aufnehmen`, Routen
  `POST /projektierung/aufgabe/{id}/entfaellt` (Grund Pflicht, 400 „Bitte einen
  Grund angeben.“) und `…/wieder-aufnehmen`; Status-Dropdown „Entfällt“ nimmt ein
  Feld `grund` an (sonst „ohne Grund (Status-Auswahl)“); Auswahl-Optionen ohne `*`
  tragen die Option als Grund; der BzA-Knopf „entfällt (nicht gefördert)“ schreibt
  „nicht gefördert“ bzw. „Förderstatus unbekannt (TAIFUN)“. Paket-Zähler zählt
  „entfällt“ wie erledigt und nennt es („alle erledigt · 1 entfällt“).
- Bedingungen: `_schritt_sichtbar` kennt `foerderung:ja|nein` (`bza.ist_gefoerdert`,
  None = sichtbar); `_laufzeit_bedingung` speichert jetzt auch `steckbrief:` und
  `foerderung:` an der Aufgabe; `abhaengige_pruefen(session, gewerk, benutzer=None)`
  liefert `{entfaellt, offen}` und setzt den Grund „Bedingung nicht erfüllt
  (<Bedingung>)“ mit Verlaufseintrag; `bedingungen_nachziehen` (= Hook
  `foerderung_schritte_nachziehen`, Rückgabe `{neu, entfaellt, offen}`) legt fehlende,
  jetzt erfüllte Schritte an und trägt Bedingungen am Altbestand nach;
  `steckbrief_schritte_nachziehen` ruft es und liefert weiter die Anzahl neuer
  Schritte. „Logik prüfen“ (`projektierung_logik.sichtbar_wenn_pruefen`) meldet
  unbekannte `sichtbar_wenn`-Formen als Hinweis (Schritt bleibt sichtbar).
- Hook-Aufrufe: `routers/projektierung.auftragsdaten_speichern` (über
  `kern.auftragsdaten_speichern`); der Angebots-Editor (`routers/angebote.py`,
  `kfw_gefoerdert` bei TAIFUN-Einträgen, Förderblock) ist eine fremde Datei –
  Vorschlag im Ergebnisbericht P1.

### Phase 134 – Board

- Volle Breite über `main.breit.pj-voll` (siehe P1-2); `.pj-board` mit
  `--pj-board-h` (JS: Viewport − Position − Hinweistext, min. 480 px),
  `.pj-col` scrollt senkrecht, Kopf sticky; Dummy-Scrollbalken `#pj-hscroll`
  über dem Board synchron in beide Richtungen; Shift + Mausrad als Fallback;
  WebKit-Scrollbalken 12 px, `scrollbar-gutter: stable`.
- Drag & Drop öffnet `dlg-phase-board` (einmal je Seite, Inhalt per
  `…/waechter?ziel=`), Senden per fetch an `POST …/phase-drop` (JSON `{ok,
  meldung, phase, projekt_status}`); bei ok wandert die Karte in die Zielspalte
  (bei Mehr-Gewerk-Karten in die Spalte des neuen Projektstatus), Spaltenzähler
  und Kacheln werden angepasst, der Gewerk-Chip zeigt die neue Phase. Karten mit
  mehreren offenen Gewerken fragen weiter „Welches Gewerk verschieben?“. Drop
  unterminiert → terminiert öffnet den gemeinsamen Termin-Dialog (Art Montage),
  der umgekehrte Weg zeigt den Hinweis „Termin in der Projektakte löschen (Block
  Termine)“ als Meldung. Neu: Knopf „📅 Termin“ an unterminierten Karten.
- Kontrollwerte ohne Playwright: `diagnose/v28_patches/p1_screenshots.py` (Chrome
  headless/DevTools, 30 Demo-Karten in Planung, Drop planung → montagevorbereitung
  mit 3 offenen Punkten), Ergebnisse in `diagnose/v28_patches/p1_kontrollwerte.json`,
  Bilder in `docs/design-v28/` (board-nachher-1920.png, board-nachher-1366.png,
  akte-termine-nachher.png, phase-dialog.png). Ein „board-vorher.png“ aus dem
  alten Code ist ohne Git-Zugriff im Agentenlauf nicht herstellbar – Vorschlag im
  Bericht (Orchestrator: Worktree auf HEAD, Skript mit `--vorher`).

### Phase 135 – Termine

- Makro `termin_dialog(td, dialog_id, gewerk, termin, art, zurueck, sparte,
  besetzung, titel)` in `templates/projektierung/_termin_dialog.html` (+
  `termin_loeschen_dialog`); Kontext `td` aus
  `routers/projektierung._termin_dialog_kontext`. Arten (`kern.TERMIN_ARTEN`):
  montage → montage/wp, elektro → montage/elektro, sub → sub/sub, feinplanung,
  abnahme, sonstige; Art beim Bearbeiten gesperrt. Verhalten (Art-Umschaltung,
  Team → Besetzungs-Chips, Ende = Beginn + (Standarddauer − 1) Arbeitstage,
  Terminvorschläge, Senden per fetch, bei Erfolg Neuladen mit Meldung) in
  `static/projektierung.js`.
- `kern.termin_speichern(session, gewerk, daten, benutzer, termin=None)` ist die
  einzige Anlage-/Bearbeiten-Funktion; `team_termin_zuweisen` (Bestandsimport,
  Alias `team-termin`) ruft sie. Routen `POST …/gewerk/{id}/termin` (alle Felder,
  versteht auch `typ`/`zweck`/datetime-local), `POST …/termin/{id}/bearbeiten`,
  `POST …/termin/{id}/loeschen` (Pflichtgrund, Outlook-Storno best effort über
  `outlook_kalender.event_loeschen`, Besetzung mit; maßgeblicher Montagetermin →
  „Montageteam zuweisen“ wieder offen; Elektro-Termin → „Elektro-Montageteam
  zuweisen“). JSON `{ok, meldung, konflikte, termin_id}` bei Accept
  application/json (400 bei Fehlern), sonst Redirect (`zurueck` oder Akte
  `#termine`). Outlook-Sync macht die Route nach dem Commit (`event_senden` gibt
  die Sitzung vor dem Netzaufruf frei).
- Besetzung: `besetzung_ids`, `besetzung_map`, `besetzung_namen(kurz=True → „A.
  Müller, B. Schmidt +2“)`, `besetzung_setzen` (ersetzt, Verlauf), Vorlage =
  `team_mitglieder_ids`; `montage_benutzer` (Rolle Montage) für die
  Mehrfachauswahl, `personen_benutzer` für „Person“. Kalender-Drag
  (`termin_verschieben`): Teamwechsel belegt neu, wenn die Besetzung leer war
  oder der alten Vorlage entsprach, sonst Verlauf „Besetzung beibehalten (von
  Hand gesetzt)“; das Zuweisungsfeld am Gewerk folgt dem Team.
- `terminstatus_map` wertet nur `typ = montage` mit `zweck in ("wp", "")` aus;
  `person_konflikte` warnt je Person („<Name> ist am 12.11. bereits bei PR-…“),
  Team-Konflikte wie bisher – kein Verbot.
- Terminvorschläge Stufe 1 `kern.terminvorschlaege(session, gewerk, team_id,
  dauer_tage, heute)` → Route `GET …/gewerk/{id}/terminvorschlaege.json`:
  frühester Beginn = max(heute + `vorschlag_vorlauf_wochen`, Lieferdatum der
  letzten UGL-Bestellung + 1 Arbeitstag) → nächster Montag; je aktivem
  Montage-Team bis zu 5 freie Fenster (26 Wochen), Umweg aus `routing.fahrzeit`
  (vorheriger/nächster Einsatz des Teams, ersatzweise Startadresse; Geocoding
  über `geocoding.geokodieren` – beide geben die Sitzung vor dem Netzaufruf frei,
  zusätzlich `verbindung_freigeben` vor dem Block); Sortierung Beginn, Umweg.
  `vorschlag_outlook` ist nur angelegt.
- `migration_v28(session)`: `zweck` für Montagetermine ohne Zweck (wp/elektro/
  sub nach Zuweisungsfeld, sonst wp), Besetzung aus Team-Mitgliedern für Termine
  ohne Besetzung, Bedingungen am Altbestand (P1-6). Zweiter Lauf: keine Meldung.
- Akte: Block „Termine“ je Gewerk (Tabelle Art · Datum/Uhrzeit · Team/Person ·
  Besetzung · Kunde · Outlook · Aktionen) ersetzt die Zeilen Montage/weitere
  Termine; Zählerwechsel bleibt darunter; Terminübersicht und Kalender zeigen die
  Besetzung als Tooltip; Terminübersicht legt über Gewerk-Wahl + Dialog an.

### Phase 139 – Stücklisten

- `docs/stuecklisten_v26.csv` eingespielt am 08.10.2026 über
  `diagnose/v28_patches/p1_stuecklisten_import.py` (`stuecklisten.csv_import`,
  Backup der Excel in `data/backups`): 121 Zeilen, 80 Positionen, Logik-
  Validierung ohne Fehler (Ergebnis im Bericht P1). Die CSV bleibt liegen.
- Konvention Lieferant (`stuecklisten.art_fuer_lieferant`, Standard aus
  `stueckliste_standard_lieferant` = Collin): Collin = bestellen · Lager/LAGER =
  Lagerware · „–“/„-“/KEIN-MATERIAL = Leistung ohne Material · anderer Name =
  Fremdlieferant. `ugl.material_fuer_gewerk(…, mit_uebrigen=True)` liefert die
  übrigen Zeilen für den Block „nicht bestellt (Lager / Leistung /
  Fremdlieferant)“ der Bestell-Vorschau; nur „bestellen“ kommt in die UGL;
  Positionen mit ausschließlich Lager-/Leistungs-Zeilen gelten als zugeordnet.
  Stücklisten-Seite: Spalte „Art“, Konventionstext, Fortschritt nach P1-5.
  Die Anleitung des privaten `docs/Stuecklisten-Entwurf.xlsx` wurde nicht
  angefasst – die Konvention steht hier und auf der Seite.

### Offen / Rückfragen P1

- Soll die volle Breite (`main.breit`) auch für Portal/Lead-Seiten gelten (P1-2)?
- Außendienst als „Person“ an Feinplanungsterminen (P1-4)?
- `board-vorher.png` (alter Stand) vom Orchestrator aus HEAD erzeugen.
- Hook `foerderung_schritte_nachziehen` im Angebots-Editor (fremde Datei).
- Besetzung je Sub-Einsatz mit Subunternehmer (ohne Subteam) bleibt leer – reicht
  der Subunternehmer als „Mannschaft“?

## PLAN_PROJ_V6 (08.10.2026) – Umsetzung durch Claude Code (v28), Teil P2: Phasen 136, 137, 138

### Phase 136 – Notizen, Lightbox
- Der Vorgangs-Notizen-Chat ist die einzige Notizspur Lead → Montage; Projektakten-
  Kommentare schreiben hinein (`herkunft = projektierung`), Systemeinträge bleiben im
  Projektverlauf. Projekte ohne Vorgang (Altbestand) behalten den alten Weg. Migration:
  Kopie der alten Kommentare mit `herkunft = "projektierung (migriert)"`, Dubletten-
  schlüssel vorgang_id + zeit + text, Original bleibt.
- Kennzeichen aus `herkunft`: projektierung → Projektierung, montage → Montage,
  lead/anruf → Lead, vertrieb/erfassung/angebot/kombi-versand → Vertrieb, freie Texte
  (z. B. „Galerie“) als grauer Badge, leer = kein Badge. Neue Einträge: Rolle bestimmt
  die Herkunft (Projektierung/Leadmanagement/Montage), sonst Vertrieb; Seiten können sie
  über `herkunft=` festlegen (Kundenkartei → lead).
- Rechte: ID/Admin überall, AD eigene Vorgänge (wie Akte), Projektierung bei Vorgängen
  mit Projekt, Leadmanagement bei sichtbarem Lead-Modul, Montage nur lesen. Keine
  Bearbeitung/Löschung.
- Aufgabenbezogene Kommentare (💬 an einer Aufgabe, Zähler je Aufgabe) bleiben im
  Projektverlauf [ANNAHME P1-8/P2 – Rückfrage]; das Verlaufs-Kommentarfeld geht in den
  Notizen-Chat.
- Sofort-Download: Ursache war `Content-Disposition: attachment` der Datei-Route; Bilder
  und PDFs kommen inline, Download nur über `?download=1`. Lightbox gruppiert je
  Vorgang/Sparte/Ordner.

### Phase 137 – Montage-Backend
- Steckbrief: alle Felder aus `steckbrief_felder(sparte)` inkl. Auftragsdaten-Felder,
  leere „–“; Ableitung wird nur nachgeholt, wenn ein Gewerk gar keine Werte hat. Ursache
  des Befunds vom 06.10.: Template blendete leere Felder aus, `steckbrief_daten` liefert
  nur gespeicherte Werte (Bestandsimport ohne Ableitung), CSS-Raster mit `nowrap`.
- Besetzung entscheidet die Sichtbarkeit; Fallback für Termine ohne Besetzung = Team-
  Mitglied/Person. Admin und Projektierung sehen alles (Team-Umschalter) [ANNAHME].
- Kurzbericht beim Beenden optional [ANNAHME] → *Nachtrag 08.10.2026: entfällt ganz
  (Bemerkungen im Montagebericht)*; Abnahmeprotokoll beendet die Montage
  automatisch (Verlauf „Montage beendet mit Abnahme“). Block „Offene Montage-Aufgaben“
  entfällt; im Blatt gibt es keine Aufgaben mit rolle = montage, alte V1-Instanzen
  werden weiter über den Formular-Abschluss erledigt.
- „Gerät & Positionen (ohne Preise)“ eingeklappt zwischen Steckbrief und Teams &
  Termine [ANNAHME]; Heizlast bleibt im Kopf.

### Phase 138 – Formulare
- Typen: datum · text (Option gross = Textarea 6 Zeilen) · ja_nein · auswahl · zahl ·
  foto (Ordner, mehrere Dateien, Wert galerie:<id>:<name>|…, neue Fotos werden ergänzt
  [ANNAHME]) · unterschrift · wiederhol (optionen = Einzelfeld, JSON-Liste); Optionsform
  pflicht_wenn:<feld>≠<wert> bzw. =<wert> (text/zahl/auswahl/ja_nein/datum; leeres
  Bezugsfeld zählt bei ≠ als Pflicht). „Logik prüfen“: unbekannte Typen/Optionsformen,
  gross außerhalb text, unbekannte Bezugsfelder = Fehler (Upload abgelehnt). Lesehilfe:
  Blatt „Lesehilfe“ der Live-Excel (v28, vom Orchestrator angelegt).
- `ib_kaeltemittel` bleibt als freiwillige Angabe [ANNAHME des Plans – Rückfrage] →
  **Antwort Andreas 08.10.2026: Nein** – Zeile aus dem Blatt „Formulare“ entfernt
  (Inbetriebnahmeprotokoll 30 Felder).
- Ordner der Montagebericht-Fotos: Zählerschrank → Elektro, Außengerät → Außengerät,
  Innengerät/Heizungsraum und Neue Anlage → Neue Anlage [ANNAHME des Plans].
- Seitenname „Abweichungen & Bemerkungen“ [ANNAHME des Plans].
- Restarbeiten aus Frage 10 ohne Frist/Foto, „keine“/„keine.“/„-“/„–“/„—“ → nichts,
  Dubletten (wörtlich gleiche offene Restarbeit) übersprungen – gilt jetzt auch für die
  Mängelliste des Abnahmeprotokolls.
- PDF: Zeilen des Wiederholfelds „<Einzelfeld> n: <Wert>“ („Seriennummer 1: …“)
  [ANNAHME]; zwei Unterschriften nebeneinander, Beschriftung = Bezeichnung ohne
  „Unterschrift “-Präfix.
- Bestehende Entwürfe mit alten Schlüsseln werden ignoriert (Renderer/PDF kennen nur die
  Blattfelder); abgeschlossene PDFs bleiben.

### Offen / Rückfragen P2
1. `ib_kaeltemittel` als freiwillige Angabe belassen?
2. Ordner der Montagebericht-Fotos (Elektro / Neue Anlage) oder eigene Ordner?
3. Seitenname „Abweichungen & Bemerkungen“ bestätigen.
4. Aufgabenbezogene Kommentare im Projektverlauf belassen oder in den Vorgangs-Chat?
5. Kurzbericht beim Beenden ganz entfallen lassen?
6. Projektierung lesend im Montage-Backend (Team-Umschalter) gewollt?
7. PDF-Zeilenpräfix des Wiederholfelds („Seriennummer n“ vs. „Systemkomponente n“).
8. Alte Formular-Entwürfe beim Update leeren? (heute ignoriert)

### Antworten Andreas 08.10.2026 auf die Rückfragen des Durchlaufs (Projektierung)

| Rückfrage | Antwort | Umsetzung |
|---|---|---|
| P1-1 Volle Breite auch für Portal- und Lead-Seiten? | Ja | `main.breit` in `style.css` auf `max-width: none` (16 px Innenabstand) für alle breiten Seiten; Sonderregel `.pj-voll` entfällt |
| P1-2 1 366 × 768: Board-Mindesthöhe vs. „kein Seiten-Scroll“ | Entscheidung Claude | Mindesthöhe 480 px nur ab 900 px Viewport-Höhe, darunter 320 px – bei 1 366 × 768 kein Seiten-Scroll |
| P1-3 Außendienst als „Person“ an Feinplanungsterminen? | Nein, nur Innendienst | Personen-Liste bleibt Projektierung + Innendienst + Admin (kein Außendienst) |
| P1-4 Sub-Einsatz mit Subunternehmer ohne Subteam | Entscheidung Claude | bleibt: Subunternehmer reicht, Besetzung darf leer bleiben, Monteure bleiben wählbar |
| P2-1 `ib_kaeltemittel` behalten? | Nein | Zeile aus dem Blatt „Formulare“ entfernt (30 Felder), Tests angepasst |
| P2-2 Foto-Ordner der neuen Montagebericht-Felder | Entscheidung Claude | bleibt: Zählerschrank → Elektro, Außengerät → Außengerät, Innengerät/Heizungsraum → Neue Anlage |
| P2-3 Seitenname „Abweichungen & Bemerkungen“ | Entscheidung Claude | bleibt |
| P2-4 Aufgabenbezogene Kommentare im Projektverlauf belassen? | Ja | bleibt (Verlaufs-Kommentarfeld → Notizen-Chat, 💬 an der Aufgabe → Projektverlauf) |
| P2-5 Kurzbericht beim „Montage beenden“ ganz entfallen? | Entscheidung Claude | entfällt – Feld aus der Auftragsseite entfernt (Bemerkungen stehen im Montagebericht); ein mitgeschicktes Feld wird nur noch in den Verlauf übernommen |
| P2-6 Projektierung lesend im Montage-Backend? | Entscheidung Claude | bleibt (Projektleiter sieht, was der Monteur sieht) |
| P2-7 PDF-Präfix „Seriennummer n“ | ok | bleibt |
| P2-8 Alte Formular-Entwürfe beim Update leeren? | Ja | `montage_formulare.migration_v28_entwuerfe` (migrate.py): Entwürfe mit alten Schlüsseln werden geleert |

