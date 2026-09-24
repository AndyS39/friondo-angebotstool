# Umsetzungsplan v12 – Design-Update: schöner, anschaulicher, aus einem Guss

Voraussetzung: v11 komplett umgesetzt UND ausgerollt (nur ein Plan zur Zeit;
Absprache mit PLAN_LEAD/PLAN_PROJ). CLAUDE.md ist Live-Master.

HARTE LEITPLANKEN für dieses Update:
- REINES FRONTEND: nur Templates, CSS und statische Assets. Keine Änderung
  an Routen, Logik, Berechnungen, Datenbank oder migrate.py.
- Das Angebots-PDF (fpdf2, Referenz AN250096) bleibt UNVERÄNDERT.
- Keine externen CDNs oder Webfonts von fremden Servern – alle Assets
  (CSS, Icons, ggf. Schrift) liegen lokal im Projekt; das Tool muss ohne
  Internet funktionieren.
- Alle bestehenden automatisierten Tests bleiben grün; falls das
  Abnahmeskript HTML-Strukturen prüft, Selektoren anpassen, ohne den
  Prüfumfang zu verkleinern.
- Rollen-/Rechteverhalten bleibt exakt gleich (AD sieht weiterhin nie
  EK/DB; Portal weiterhin nur ID/Admin).

## Phase 69 – Design-System (Fundament)
- [x] Zentrales Stylesheet mit Design-Tokens als CSS-Variablen: Farbpalette
      aus dem Friondo-CI (Primärblau aus Logo/„Layout - Logo"-Ordner,
      Dunkelblau der Kopfzeile, neutrale Grautöne, Statusfarben:
      Grün/Orange/Rot wie DB-Ampel, Blau „Versendet", Grau „Entwurf/
      Überholt", Violett o. ä. „Individuell/TAIFUN"), Abstände-Skala,
      Radien, Schatten, Typografie (Systemschriften-Stack, klare
      Größenhierarchie)
- [x] Komponenten-Baukasten (eine CSS-Datei, dokumentiert in
      docs/design-system.md): Buttons (primär/sekundär/gefährlich/Ghost,
      einheitliche Höhen), Status-Badges (EIN Farbschema für alle Status,
      überall identisch), Sparten-Chips (v9-Zustände beibehalten), Ampeln,
      Karten/Kacheln, Tabellen (Zebra, Hover, Sticky-Kopfzeile,
      rechtsbündige Beträge, tabellarische Ziffern), Formulare (Labels,
      Fokus-Zustände, Fehlerdarstellung), Modals/Dialoge, Hinweis-Boxen
      (Info/Warnung/fachlicher Hinweis), Leerzustände („Noch keine …")
- [x] Schlanke lokale Icon-Sammlung (Inline-SVG, z. B. Lucide-Auswahl:
      Brief, Uhr, Wiedervorlage, Suche, Filter, Plus, Stift, PDF, Haken,
      Warnung) statt gemischter Emoji/Text-Symbole; Emojis nur dort
      behalten, wo sie etabliert sind (Hot-Ampel 🔥/🌤/❄ darf bleiben)
- [x] Basis-Layout: Kopfzeile, Menü, Seitenraster, Container-Breiten,
      Abstände vereinheitlichen; dezente Übergänge (Hover), keine
      verspielten Animationen

## Phase 70 – Portal, Angebotstool-Startseite & Listen
- [ ] Portal: die drei Karten auf das neue System heben (Titelgrößen,
      Hover, Kachel-Optik), Coming-soon-Badges einheitlich
- [ ] Angebotstool-Startseite: Shortcuts und „Auf einen Blick"-Kacheln
      als Karten mit Icon, Zahl groß, Beschriftung klein; fällige
      Wiedervorlagen visuell dringlich (rot), aber nicht schreiend
- [ ] Listen (Leads VOT, Erfassungen, Angebote, Warteschlange):
      einheitliche Filterleiste (Suchfeld + Filter-Chips statt verstreuter
      Dropdowns), Sticky-Tabellenkopf, Zebra + Hover, Status-Badges und
      Chips aus dem Baukasten, Beträge rechtsbündig, Aktions-Buttons
      als kompakte Icon-Buttons mit Tooltip; Summenzeile der
      Angebotsliste klar abgesetzt
- [ ] Responsivität der ID-Ansichten bis Laptop-Breite prüfen
      (horizontales Scrollen nur innerhalb von Tabellen)

## Phase 71 – Vorgangsakte (Schwerpunkt „anschaulich")
- [ ] Kopfbereich als Karte: Kundenname groß, Ausführungsort/
      Rechnungsanschrift, Kanal-/Profil-Badge, Sparten-Chips,
      Hot-Ampel + Wiedervorlage prominent (mit Fälligkeits-Farbe),
      Vertriebler; Schnellaktionen rechts (Neue Erfassung, Gemeinsam
      versenden, Notiz)
- [ ] Zweispaltiges Layout (Desktop): links Angebote und Erfassungen
      als Karten – je Angebot: Nummer + Version, Sparten-Badge,
      Endbetrag, TAIFUN-Kennzeichen, und eine STATUS-SCHRITTLEISTE
      (Entwurf → Versand vorbereitet → Versendet → Angenommen/
      Abgelehnt; „Überholt" ausgegraut) als Mini-Pipeline; rechts
      Verfolgung, Mail-Verlauf (Betreffliste mit Brief-Icon) und der
      Notizen-Chat
- [ ] Notizen-Chat in Chat-Optik: Einträge als Zeilen/Blasen mit Name
      fett + Zeitstempel dezent, eigene Einträge leicht abgesetzt,
      Eingabefeld unten fixiert, „neue Notizen"-Punkt sichtbar
- [ ] Fachliche Hinweise (Widerspruch, Förderdaten prüfen …) als
      einheitliche Warn-Karten oben in der Akte
- [ ] Leerzustände je Bereich („Noch kein Angebot – Erfassung starten")

## Phase 72 – Angebots-Editor & Parametrierung
- [ ] Editor in klare Zonen: oben Verfolgungs-/Kopfkarte (Status-
      Schrittleiste, Ampel, Profil), Mitte Positionsliste, unten
      Summen-/Förderblock als ruhige Karte; Aktionsleiste (Speichern,
      PDF, Versand vorbereiten, Überarbeiten) sticky am Seitenende
- [ ] Positionsliste: Blocküberschriften deutlich abgesetzt (und vom
      Drag & Drop sichtbar ausgenommen), Kennzeichen EP/bauseits/Alt./
      Sonderpreis als kleine einheitliche Badges an der Position,
      Drag-Handle klar erkennbar, „manuell geändert"-Markierungen dezent
- [ ] Förder-Baustein-Editor und Rabattbereich optisch beruhigen
      (Eingaben + Live-Ergebnis als zusammengehörige Karte)
- [ ] Parametrierung: Unterseiten mit einheitlichen Karten je Themen-
      block, Validierungs-Ausgabe (Fehler rot / Hinweise gelb) im neuen
      Hinweis-Box-Stil, Speichern-Feedback einheitlich
- [ ] Statistik-Seite: Kacheln + Diagramme im neuen Stil, einheitliche
      Farben je Sparte/Kanal

## Phase 73 – Mobile Erfassung (Außendienst)
- [ ] Fragebogen: Fortschrittsanzeige („Seite 3 von 8" + Balken),
      Seitentitel groß, eine Frage-Karte pro Frage, große Touch-Ziele
      (Radio-/Checkbox-Flächen komplett tippbar), Zahlenfelder mit
      passender Handy-Tastatur, Weiter/Zurück als sticky Fußleiste
- [ ] Sparten-Weiche und Freitext-Umschalter als große, klare Karten
- [ ] Einschätzungs-Seite: Ampelwahl als drei große Buttons
- [ ] AD-Listen (Leads VOT, Meine Angebote/Vorgänge): Karten-Layout
      fürs Handy, Badges/Chips wie am Desktop, Wiedervorlagen-Anzeige
- [ ] PWA-Darstellung prüfen (Icon, Startansicht, kein Zoom-Springen)

## Phase 74 – Feinschliff & Abnahme
- [ ] Konsistenz-Rundgang: jede Seite gegen docs/design-system.md
      prüfen (keine Alt-Stile, keine Inline-Farben mehr)
- [ ] Vorher/Nachher-Screenshots der Kernseiten (Portal, Startseite,
      Angebotsliste, Vorgangsakte, Editor, mobile Erfassung) unter
      docs/design-v12/ ablegen
- [ ] Alle automatisierten Tests grün; kompletter manueller
      Klickdurchgang laut Abnahmeskript (Funktionsverhalten identisch)
- [ ] CLAUDE.md: Kopf auf „(v12)"; Abschnitt einfügen:

      ## Neu in v12 (abgestimmt 24.09.2026)
      - Reines Design-Update, keine Funktionsänderungen: zentrales
        Design-System (CSS-Tokens, Komponenten-Baukasten, lokale
        SVG-Icons, docs/design-system.md) für alle Oberflächen.
      - Überarbeitet: Portal, Startseite, alle Listen (Filterleiste,
        Sticky-Kopf, einheitliche Badges), Vorgangsakte (Kundenkopf,
        Angebots-Karten mit Status-Schrittleiste, Notizen-Chat-Optik),
        Angebots-Editor (Zonen, sticky Aktionsleiste, Kennzeichen-
        Badges), Parametrierung, Statistik, mobile Erfassung
        (Fortschrittsanzeige, Touch-Optimierung).
      - Angebots-PDF unverändert. Künftige Module (Lead-Management,
        Projektierung) bauen auf dem Design-System auf.

- [ ] docs/nach-dem-update-v12.md: Kurzhinweis ans Team („neue Optik,
      identische Funktionen – alles ist, wo es war"), Strg+F5-Hinweis
      wegen CSS-Cache
- [ ] git push → Rollout per update.bat
