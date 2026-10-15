# Nach dem Update auf v34 – Wallbox-Konfigurator, Angebotstool-Feedback 15.10., Mobil (PLAN_V21, Phasen 178–182)

Stand 15.10.2026. v34 ist PLAN_V21 (im Plan stand v35/183–187 – die Zuordnungstabelle in CLAUDE.md
endete bei v33/177, deshalb die nächsten freien Nummern; PLAN_LEAD_V6 bekommt bei seiner Umsetzung
v35/183–187). Rollout nur im Wartungsfenster Dienstag 22:30–23:30: Wartungsbanner setzen, `update.bat`,
danach `scripts\smoke.bat`. Rückweg `rollback.bat --nur-code` (alle Datenbankänderungen sind additiv).

## Für das Team

### Wallbox: Katalog statt Freitext (Phase 178/179, Stand Nachtrag 15.10.2026)

- Der Außendienst erfasst eine Wallbox jetzt wie WP/PV/KL über den Fragenkatalog: Wallbox (AMTRON 4You
  310 oder 560), Meter Leitungsverlegung (10 m sind enthalten, jeder weitere Meter wird mit der
  lfd.-Meter-Position berechnet), Erdarbeiten ja/nein mit Metern (auch bei Wandmontage möglich),
  Wandmontage oder Säule (Säule = Fundament und Standsäule, pauschal), Anzahl Durchbrüche (2 sind
  enthalten, jeder weitere 169 €), Bemerkung. Anschlussvorbereitung und Netzanmeldung sind immer
  enthalten. Der Innendienst sieht die Erfassung grün und erzeugt das Angebot wie gewohnt; individuelle
  Fälle (andere Wallbox, kein Standardanschluss) bitte weiter über „Freitext-Erfassung“ → TAIFUN.
- Das Wallbox-Angebot enthält immer die Vollmacht-Seite (Netzanmeldung § 14a) und keine
  Zahlungsoptionen-Seite, keinen Förderblock, keine Wirtschaftlichkeit; die Zahlungsklausel ist der
  Standardtext (Anzahlung 50 % spätestens 14 Tage vor Arbeitsbeginn, Rest mit der Schlussrechnung – wie
  im TAIFUN-Muster). Die Herleitung (Leitung/Mehrlänge, Erdarbeiten, Montage, Durchbrüche) steht im
  Protokoll-PDF (Seite „Auslegung“) und im Editor unter „Auslegung (intern)“; eine Leitungslänge über
  100 m wird nur als Hinweis gemeldet; „Erdarbeiten ja“ ohne Meter lässt sich nicht absenden.
- Solange die Wallbox-Preisliste nicht importiert ist, bleibt WB eine reine Erfassung (Hinweis im
  Erfassungsdetail, Angebot in TAIFUN) – die Weiche Katalog | Freitext erscheint trotzdem.
- DB-Ampel für Wallbox-Angebote: Startwerte rot unter 800 €, grün über 1.200 € (Parametrierung →
  Angebotstool-Einstellungen, Zeile WB; mit den WP-Schwellen wäre jedes WB-Angebot rot).

### Angebote: Alternativ-Positionen, Elektroarbeiten ins PV-Angebot, Auslegungszeile, USt (Phase 180)

- **Alternativ-Positionen sehen jetzt anders aus:** Im Angebots-PDF steht vor Alternativ-Positionen ein
  blauer Hinweiskasten („… bereits in Ihrem Angebot AN-C-… (PV) enthalten …“), die Zeile ist grau und
  rechts steht „im PV-Angebot“ statt „Altern.“. Im Editor hat die Zeile einen farbigen Balken links und
  ein Badge mit Link zum anderen Angebot. Eventualpositionen („EP“) sind unverändert. Damit die Nummer im
  PDF erscheint, beim Setzen des Häkchens „Alt.“ das Angebot aus der Vorschlagsliste wählen
  („PV-Angebot AN-C-…“) – bei Freitext bleibt ein allgemeiner Kasten.
- **Neuer Knopf „Elektroarbeiten ins PV-Angebot (0 % USt)“** im Editor eines WP-/KL-/WB-Entwurfs,
  sobald der Vorgang ein PV-Angebot (Entwurf/Versand vorbereitet) hat: verschiebt den Block
  „Elektroarbeiten“ plus die Artikel der Liste „gewerkeübergreifende Artikel“ (Parametrierung) ins
  PV-Angebot (dort 0 % USt), hier bleiben sie als Alternativ sichtbar. Die Meldung nennt die
  Kundenersparnis. Hat das PV-Angebot einen Artikel schon (z. B. Zählerschrank), wird er nicht doppelt
  kopiert, sondern nur als „im PV-Angebot enthalten“ gekennzeichnet. „Elektroarbeiten zurückholen“ macht
  es rückgängig, solange beide Angebote noch nicht versendet sind. **Die steuerliche Zulässigkeit dieser
  Aufteilung ist Entscheidung von Friondo/Steuerberatung – das Tool setzt sie nur um.**
- **Keine Auslegungszeile mehr im Angebot:** Die 0,00-€-Position „Auslegung der Wärmepumpe/
  Klimaanlage/PV-Anlage“ entfällt in neuen Angeboten; der Innendienst findet die Herleitung im Editor
  unter „Auslegung (intern)“ (aufklappbar, unter der Kopfkarte) und im Konfigurationsprotokoll. Beim
  Update entfernt die Migration die Zeile aus allen Entwürfen; versendete Angebote bleiben unverändert,
  beim „Überarbeiten“ entfällt sie in der neuen Version.
- **USt wird kaufmännisch gerundet** (wie TAIFUN): bei manchen Beträgen ändert sich die USt um 0,01 €
  gegenüber der bisherigen Anzeige (z. B. Klima-Muster 1.238,55 € statt 1.238,54 €). Bereits erzeugte
  PDFs bleiben, ein erneutes „PDF anzeigen“ zeigt den gerundeten Wert.

### Versand: Gemeinsam versenden, Mail-Vorlage je Sparte, TAIFUN-PDF (Phase 180)

- **Kombi-Versand – Kasten „Gemeinsam versenden“:** In der Vorgangsakte stehen unter den Angeboten alle
  Angebote des Vorgangs mit Häkchen; wählbar sind Entwürfe, „Versand vorbereitet“ und TAIFUN-Einträge mit
  hinterlegtem PDF – ausgegraute Angebote zeigen beim Zeigen mit der Maus den Grund (z. B. „PDF fehlt“,
  „Bereits versendet“). Entwürfe müssen nicht mehr vorher einzeln vorbereitet werden: der Knopf
  „Kombi-Versand vorbereiten (n Angebote)“ macht sie automatisch versandfertig (Notiz „Versand vorbereitet
  durch Kombi-Versand“ am Angebot und im Vorgangs-Chat) und legt wie bisher EINE Mail mit allen PDFs im
  Postfach angebot@ ab. Mindestens zwei Angebote; ein einzelnes Angebot geht weiter über „Versand
  vorbereiten“ am Angebot. Im Angebots-Editor führt „Mit weiteren Angeboten dieses Vorgangs versenden“
  direkt in den Kasten (Angebot vorgehakt).
- **Mail-Vorlage Klima/PV/Wallbox:** Beim „Versand vorbereiten“ eines Klima-, PV- oder Wallbox-Angebots
  gilt jetzt zuerst die Vorlage der Sparte (Parametrierung → E-Mail-Vorlagen → Reiter PV/KL/WB), erst wenn
  es keine gibt, die Vorlage des Außendienstlers, sonst die Standard-Vorlage. Bei Wärmepumpen-Angeboten
  bleibt alles wie bisher. Die Meldung nach dem Vorbereiten nennt die verwendete Vorlage („Sparten-Vorlage
  KL“). Ursache des alten Verhaltens: die Vorlage des Außendienstlers (Wärmepumpen-Wortlaut) gewann immer,
  sobald eine hinterlegt war. **To-do Innendienst:** die Sparten-Vorlagen PV/KL/WB einmal gegenlesen – sie
  wurden in v27 automatisch aus der Standard-Vorlage abgeleitet und greifen jetzt auch bei Außendienstlern
  mit eigener Vorlage.
- **TAIFUN-PDF per Drag & Drop:** Im Dialog „Extern erledigt“ (Erfassung → In TAIFUN zu schreiben) das
  TAIFUN-Angebots-PDF in die gestrichelte Fläche ziehen oder über „auswählen“ wählen – Angebotsnummer,
  Datum und Endbetrag werden aus dem PDF vorbelegt (Hinweis „aus PDF gelesen – bitte prüfen“); alles
  prüfen, dann „Externen Angebotseintrag anlegen“. Das PDF liegt danach am Eintrag (Kombi-Versand) und in
  der Galerie „Allgemein“. Am TAIFUN-Eintrag (TAIFUN-Seite, Vorgangsakte, Angebotsliste) ersetzt dieselbe
  Fläche den bisherigen Datei-Knopf; ein neues PDF ersetzt das alte nach Rückfrage, dabei können
  Nummer/Datum/Endbetrag per Häkchen aus dem neuen PDF übernommen werden (monday wird nicht automatisch
  nachgezogen – Knopf „Erneut übertragen“). Gescannte PDFs ohne Textebene werden gespeichert, liefern aber
  keine Werte („Kein Text im PDF gefunden“); max. 20 MB, nur PDF. Am Handy gibt es nur „auswählen“.

### Mobil: Anmeldung, Diktieren, Galerie (Phase 181)

- **Anmeldung am Handy (alle Rollen):** Auf Handy oder Tablet gibt es jetzt für jede Rolle das Häkchen
  „Auf diesem Gerät angemeldet bleiben“ – 30 Tage, bis zum nächsten Abmelden. Am PC bleibt es bei
  12 Stunden für Büro-Rollen (Außendienst und Montage wie bisher 30 Tage mit Häkchen). Wer das Tool als
  App auf dem Home-Bildschirm nutzt, meldet sich **in der App** an – die Anmeldung im Safari gilt dort
  nicht (eigener Speicher). Ursache des bisherigen Verhaltens: das Häkchen war nur für Außendienst/
  Montage sichtbar und nur diese Rollen bekamen 30 Tage; Admin und Innendienst wurden am Handy nach
  12 Stunden abgemeldet.
- **Diktieren:** An den Bemerkungsfeldern der Erfassung, in der Freitext-Erfassung, am Notizen-Chat und
  in den Montage-Formularen steht ein Knopf „Diktieren“. Solange das Tool über die http-Adresse im VPN
  läuft, zeigt er „Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden“ – die Mikrofon-Taste der
  Handy-Tastatur funktioniert in jedem Textfeld. Nach einer Umstellung auf HTTPS (IT-Entscheidung,
  `docs/https-intern.md`) startet der Knopf die Spracherkennung des Browsers.
- **Galerie – mehrere Fotos auf einmal:** „Fotos aufnehmen“ öffnet die Kamera, jedes Foto landet erst in
  einer Liste (Knopf heißt dann „Weiteres Foto“); „Dateien wählen“ nimmt mehrere Bilder/PDFs aus der
  Mediathek. Je Foto Ordner und Bemerkung wählen (oder „Für alle übernehmen“), dann einmal „n Fotos
  hochladen“ – ein Balken zeigt den Fortschritt, Fotos werden vorher auf dem Handy verkleinert. Beim
  Verlassen der Seite mit ungesendeten Fotos warnt der Browser. Scheitert eine Datei, bleiben nur die
  fehlgeschlagenen in der Liste (mit Grund). Das gilt in der Vorgangsakte, Projektakte, im Montage-/
  Service-Backend und auf der Seite „Einschätzung“ der Erfassung (dort gehen die Fotos mit „Weiter“ mit).

## Für Andreas / Admin

1. [ ] **Wallbox-Preisliste:** `Artikel-Preislisten\Wallbox\WB Angebot Excel 1.xlsx` (TAIFUN-Export mit EK,
   liegt in Git) – `migrate.py` importiert sie beim Update automatisch (Meldung „WB-Artikel fehlten … Import
   ausgeführt“); nachträgliche Preisänderungen über Parametrierung → Logik & Importe → „Wallbox-Positionslisten
   importieren“ (Vorschau mit Protokoll). Position 008 Fundament/Standsäule steht im Export mit Einheit „m“ –
   das Tool rechnet 1 × pauschal (Blatt „WB-Artikel“); in TAIFUN ggf. auf psl. korrigieren.
2. [ ] **Mennekes-Datenblatt** AMTRON 4You nach `anlagen\` (Dateiname laut Blatt „Anhänge“); bis dahin
   meldet die Betriebs-Seite die fehlende Anhang-Datei.
3. [ ] Musterangebot AN251131 liegt nur lokal unter `Artikel-Preislisten\Wallbox\Beispielangebot.pdf`
   (gitignored, Kundendaten) – der TAIFUN-PDF-Leser erkennt daraus Nummer, Datum, Endbetrag 4.315,24 € und
   Sparte Wallbox (geprüft).
4. [ ] Nach dem Rollout: Parametrierung → Angebotstool-Einstellungen → Liste „gewerkeübergreifende
   Artikel“ prüfen (sie steuert, was zusätzlich zum Block Elektroarbeiten ins PV-Angebot wandert;
   Standard 014, 015, 016, 017, 104, Z22, 152, Z23 – Fit for Future 014–017 wandern laut Plan mit).
5. [ ] **Login-Probe mit dem Handy:** Safari/Chrome am Handy → `http://192.168.35.4:8000/login` →
   Häkchen sichtbar → anmelden → Browser schließen und am nächsten Tag öffnen → noch angemeldet. Danach
   dasselbe in der Home-Bildschirm-App (dort anmelden).
6. [ ] Entscheidung HTTPS im VPN (`docs/https-intern.md`, Option A empfohlen) – bis dahin
   Tastatur-Diktat.
7. [ ] Projektierer: Foto-Upload/Verschieben/Löschen in der Projektakte funktioniert jetzt auch mit der
   Rolle Projektierung (vorher Umleitung nach `/projektierung`) – Nebenbefund, bewusst behoben.
8. [ ] Textentwürfe gegenlesen (Innendienst): Wallbox-Vortext/-Nachtext (Parametrierung → Textblöcke
   „Friondo WB Standard/Enni/SWD/Sparkasse DU“) – dabei den Absatz „Komplettpaket Wallbox inkl. Montage“
   mit dem vollständigen Text der Excel-Textzeile ergänzen (das Import-Protokoll zeigt sie); Mail-Vorlage WB.
9. [ ] DB-Ampel Wallbox: Parametrierung → Angebotstool-Einstellungen → Zeile WB prüfen (Startwerte
   800 € / 1.200 €, [ANNAHME]).
10. [ ] GUID-Rückschreibung in die Logik-Excel ist standardmäßig aus (`wb_guid_nachfuehren = 0`) – auf dem
    Server so lassen (die Excel ist git-versioniert, ein lokal geänderter Stand bricht `update.bat`/`git pull`);
    auf dem Entwicklungs-PC bei Bedarf auf 1 setzen.
11. [ ] Lesesicht: Parametrierung → „Wallbox-Logik (WB)“; Artikel → Filter „Sparte WB“.

## Entscheidungen zu den Rückfragen 1–7 des Plans (Vorschläge des Plans, Andreas bestätigt oder ändert)

| Nr. | Frage | Umgesetzt |
|---|---|---|
| 1 | Preis Anschlussvorbereitung WB003 | 1.297,20 € (Wallbox Artikel Excel); 1.597,20 € aus Extraleitung.xlsx wird als Konflikt im Import-Protokoll genannt |
| 2 | Montagekanal | immer zusammen mit der Mehrlänge (WB005 + WB006 je weiterer Meter) |
| 3 | Zahlungsklausel WB | v30-Standard wie WP/KL (`{zahlungsbedingungen}`) |
| 4 | Vollmacht bei WB | immer (Nachtext D, Netzanmeldung §14a) |
| 5 | Auslegungszeile im Bestand | per Migration aus allen Entwürfen entfernt |
| 6 | Mail-Vorlage | PV/KL/WB: Sparten-Vorlage → AD-Vorlage → Standard; WP unverändert |
| 7 | USt-Rundung | kaufmännisch (ROUND_HALF_UP) wie TAIFUN |

## Technik

- Neue Spalten (additiv): `angebote.wb_json`, `angebote.auslegung_text`,
  `angebotspositionen.uebernommen_von_angebot_id/_position_id`. Migrationen: `migration_v34_auslegung`
  (Auslegungszeile aus Entwürfen), *(Wallbox-/Text-Seeds werden nach dem Bericht von Agent W ergänzt)*.
- Neue Abhängigkeit `pypdf` (reines Python, `requirements.txt`; `update.bat` installiert sie über
  `pip install -r requirements.txt`).
- Keine neuen Hintergrundläufe, keine neuen Netzaufrufe (Inventar in `docs/betrieb.md`).
