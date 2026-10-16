# Nach dem Update auf v37 – Lead-Management V7: Design v3, Kartei-Review, Termine anpassen, Routing in Kilometern (PLAN_LEAD_V7, Phasen 196–200)

Stand 16.10.2026 (Plan-Kette v36 → v37 → v38, Rollout erst nach der gemeinsamen Rollout-Prüfung am Kettenende – erledigt 17.10.2026, `docs/updates.md` 4g).
Alle Datenbankänderungen sind additiv – der v36-Code läuft auf der v37-Datenbank weiter (`rollback.bat --nur-code`).

## Für den Admin (Reihenfolge nach dem Update)

1. **Routing-Key:** `ORS_API_KEY=<Key von openrouteservice>` in die `.env` auf Server und Dev-PC (Konto
   account.heigit.org, kostenloser Plan), Dienst neu starten; danach Lead-Einstellungen → Abschnitt „Routing“: der
   Prüfpunkt „Routing-Dienst antwortet (Duisburg → Bochum)“ muss grün melden. Die Migration stellt den Anbieter auf
   „ors“, sobald der Key vorliegt (sonst unter Lead-Routing umstellen). Tageskontingent `routing_kontingent_tag`
   (Standard 2000) an den tatsächlichen Plan anpassen – der Free-Plan begrenzt die Matrix-API vermutlich auf 500
   Anfragen je Tag (Rückfrage); ab 80 % warnt die Seite, ab 100 % wird bis Mitternacht geschätzt. Der alte Parameter
   `ors_api_key` bleibt nur Rückfall und sollte leer sein.
2. **Kanäle:** `migrate.py` meldet beim ersten Lauf „Kanaele (v37): 'WELOVEX' deaktiviert …“ und „… 'DAA'
   deaktiviert …“; steht einer der Kanäle in `hv_ausschluss` oder `kanal_ad_regel`, kommt zusätzlich „Kanaele (v37):
   Hinweis - '<Kanal>' steht im Parameter … (nicht geaendert, bitte pruefen)“ – dann die Lead-Einstellungen bzw.
   das AD-Profil prüfen und den Kanal von Hand entfernen. Der zweite Lauf meldet nichts.
3. **Vorlagen:** `{pv_vorhanden}` steht im Vorlagen-Editor zur Verfügung („Sie haben bereits eine PV-Anlage“ oder
   leer); keine Standard-Vorlage wurde geändert.
4. **Design v3 (Lead-Modul):** siehe Abschnitt „Design v3“ unten (Agent L1) – Prüfung in beiden Darstellungen
   (Hell/Dunkel) nach dem Rollout; die Design-Zulieferung (`Friondo Tool Design.html`, Review-Screenshot) lag nicht
   vor, gebaut wurde nach den Startwerten des Plans.

## Für das Team (Lead-Management, Innendienst, Außendienst)

- **Termine anpassen:** In der Kundenkartei hat jeder aktive Vor-Ort-Termin – auch die aus monday – den Knopf
  „Anpassen“ (Datum, Uhrzeit, Vertriebler, Objekt, Bemerkung). Warnungen (Puffer, Arbeitszeit, Outlook) erscheinen im
  Dialog und werden mit dem Häkchen „Konflikte geprüft – trotzdem speichern“ bestätigt; echte Überschneidungen sind
  gesperrt. In der Testphase wird nur im Tool geändert (kein Outlook, keine Kundenmail – die Meldung sagt es).
  monday-Termine: die Änderung gilt im Tool, monday bleibt wie es ist (Hinweis „ursprünglich aus monday: …“); ändert
  jemand das Datum in monday, übernimmt der Sync wieder monday. Die manuelle Neuanlage eines Vor-Ort-Termins bleibt
  in der Testphase gesperrt.
- **Strecken in Kilometern:** Terminvorschläge, Kalender, Ersatzkunde, Karte und „Mein Tag“ zeigen Straßenkilometer
  und Fahrzeit („18,4 km · 24 Min“). Steht „ca. … (geschätzt)“, fehlt der Routing-Key oder der Dienst war nicht
  erreichbar.
- **Objekte:** Bei Großkunden und Vorgängen mit mehr als drei Objekten ist die Objektliste zugeklappt (Kopfzeile zeigt
  Anzahl, Termine, Angebote); auf-/zuklappen merkt sich das Tool je Nutzer.
- **Dashboard:** Die Kachel „Routenplaner“ ist weg (Google-Maps-Route gibt es weiter in „Mein Tag“ über „Route
  starten“).
- **Anmeldung:** der zuletzt verwendete Benutzer ist vorbelegt, nur die PIN ist einzugeben; „Anderer Benutzer“ wechselt.
- **Interessen im Board:** In der Spalte „Interessen“ steht hinter den Badges ein **Plus**. Klick öffnet die Auswahl
  (alle Interessen als Chips, gewählte sind gefüllt) – Klick auf einen Chip wählt ab bzw. an. Gespeichert wird beim
  Schließen (Klick neben die Auswahl, erneut auf das Plus oder „Übernehmen“); **Esc** oder „Abbrechen“ schließt ohne
  zu speichern. Jede Änderung steht als Aktivität in der Kartei.
- **Neues Häkchen „PV vorhanden“** (Kürzel PVV) in Kartei, Board-Auswahl, Schnellanlage, Import und Filter „Sparte“
  – ein Merkmal des Kunden (bestehende PV-Anlage), **keine Sparte**: es gibt keine Erfassung dafür, es zählt nicht
  als Interesse für das Pflichtfeld, Kundenmails nennen es nicht (nur über den Platzhalter `{pv_vorhanden}`). Im
  WP-Bogen ist die Frage „PV-Anlage vorhanden?“ dann mit „Ja“ vorbelegt.
- **Deals-Board:** Die Spalte „Erfassung / Angebot“ und die Knöpfe „Erfassung starten“ / „Bestätigung erneut“ gibt es
  dort nicht mehr. Erfassung starten: Kartei, Leads VOT oder Mein Tag; Terminbestätigung erneut senden: Kartei →
  Block Termine. Wer die Spalte in seiner Spaltenkonfiguration hatte, sieht sie einfach nicht mehr (kein Fehler).
- **Vertriebskanäle WeLoveX und DAA** sind nicht mehr wählbar; bestehende Leads behalten das Label (Dropdown dort
  „(nicht mehr wählbar)“), in den Filtern fehlen sie. Wieder aktivieren: Lead-Management → Mehr … →
  Vertriebskanäle → „Nicht mehr wählbar“ → Aktivieren.

## Design v3 (Lead-Modul) und Kartei-Review

- **Lead-Management sieht anders aus:** Alle Lead-Seiten (Dashboard, Boards, Kartei, Terminassistent, Karte, To-Dos,
  Vorlagen, Lead-Einstellungen) tragen das neue Design v3 – Primärblau statt Dunkelblau für aktive Elemente und
  Knöpfe, runde Pills für Filter und Reiter, Karten mit weichem Schatten, größere Kennzahlen auf dem Dashboard,
  Tabellenzeilen etwas höher (40 px), Eingabefelder leicht getönt. Bedienung, Spalten, Filter, Sammelaktionen,
  gespeicherte Filter und alle Knöpfe sind unverändert. Angebotstool, Projektierung, Vorgangsakte, Kalender und die
  Kopfzeile bleiben wie bisher. Hell/Dunkel wie gewohnt über Menü ☰ → Darstellung.
- **Kundenkartei:** Im Kopf fehlen das Badge „monday“ und der SLA-Chip – die Quelle steht in der Eingangszeile
  „Eingang … (monday)“ und im Kundeninfo-Block, die SLA-Ampel in der Anrufliste. Der Notizblock ist breiter: das
  Textfeld geht über die ganze Spalte, „Senden“ und „Diktieren“ stehen rechts daneben (auf dem Handy darunter).
  Der Vorschlag „Ideal“ im Terminassistenten/Termine-Block ist jetzt orange markiert.
- **Admin:** Keine Einstellung nötig; die Schrift „Inter“ ist nicht installiert – das Tool zeigt die Systemschrift
  (Segoe UI). Liegt Inter später als lizenzfreie woff2 vor, nach `app/static/fonts/inter/` legen und im v3-Block
  von `lead_v2.css` per `@font-face` einbinden. Screenshots zur Abnahme: `docs/design-v37/`.

- **Screenshots** vorher/nachher hell/dunkel (20 Lead-Seiten, nur Demo-Daten): `docs/design-v37/`;
  die Design-Vorlage und der Review-Screenshot von Claudia fehlen – Abweichungen später über den v3-Token-Block
  in `lead_v2.css` nachziehen (Vorlage gewinnt).
