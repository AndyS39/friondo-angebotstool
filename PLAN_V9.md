# Umsetzungsplan v9 – Profile, 8800er-Serie, Solarthermie, Versionierung

Voraussetzung: Phasen 0–52 umgesetzt, v8 läuft auf dem Server. CLAUDE.md und
konfigurator_logik_v5.xlsx sind Live-Master – direkt ändern, nicht ersetzen.
Je Phase: Ansatz erläutern → umsetzen → testen → abhaken → committen.
Schema-Änderungen in migrate.py (idempotent). Die Quelldateien der neuen
Nachtexte liegen im Projektordner (Unterordner mit den drei Dateien Enni /
SWD / Sparkasse DU – beim Start lokalisieren, im Zweifel nachfragen).

## Phase 53 – Angebotsprofile, Nach- & Vortexte, Versandregeln
- [x] CLAUDE.md: Kopf auf „(v9)"; neuen Abschnitt einfügen:

      ## Neu in v9 (abgestimmt 29.08.2026)
      - Angebotsprofile (Standard / Enni / SWD / Sparkasse DU) bündeln je
        Vertriebskanal: Nachtext-Block, Positionsregeln und Versandregeln.
        Auto-Auswahl über den Kanal des Leads (Zuordnung Kanalwert → Profil
        in der Parametrierung, Fallback Standard), am Angebot manuell
        umschaltbar mit Konsistenz-Hinweis. Nach- und Vortexte sind
        editierbare Textblöcke in der Parametrierung.
      - Enni: nur HEMS-Frage (P02/P03 entfallen im Bogen); HEMS = Ja →
        Pos. 015 zum Sonderpreis 599 € (kein 014) + Pos. 162 automatisch;
        keine Vollmacht; Versand zusätzlich CC energieberatung@enni.de.
        SWD: P01–P03 nur Protokoll (keine 014–017, keine Vollmacht);
        Empfängerfeld beim Versand leer (ID trägt SWD-Kontakt manuell ein).
        Sparkasse DU: nur eigener Nachtext. BCC-Feld akzeptiert mehrere
        Adressen (kommagetrennt).
      - Neue Leistungsklasse 15 kW (Serie CS8800i): Verbrauch 31.001–37.000
        kWh bzw. Heizlast 16,0–18,5 kW; Farbwahl Außeneinheit (030 weiß /
        031 schwarz); Inneneinheit aus Pufferwahl abgeleitet (70 l → AWMB
        055; 200/300/500 l → AWE 056 + externer Puffer); Warmwasser fix
        über Pos. 065. Pos. 067 kommt automatisch bei jedem AWM-Paket
        (045–049) – einzige Quelle: Paketmatrix.
      - Solarthermie ist konfigurierbar: „stilllegen" → Z24 (0 €, Rückbau
        im Heizungsraum); „übernehmen" → AWE-Paket + Pos. 069 (bivalenter
        390-l-Speicher) statt 065/067, WW-Größenfrage entfällt; Widerspruch
        „Übernahme, aber WW über WP = Nein" erzeugt einen fachlichen
        Hinweis am Vorgang (069 übersteuert). Noch 13 AMPEL-Gründe.
      - Angebots-Versionierung: Button „Überarbeiten" an versendeten/
        angenommenen Angeboten erzeugt Version .2/.3 … als Entwurf;
        Original erhält Status „Überholt" (zählt nicht mehr in Statistik,
        Summen, 90-Tage-Lauf); PDF trägt „Ersetzt Angebot … vom …";
        monday-Deal-Wert folgt der neuen Version.
      - Bedingte Angebotsvermerke (neues Logik-Blatt „Vermerke"): erster
        Vermerk „Heizungsumverlegung DG → Keller" bei A04 = DG und
        D01 = Nein. MFH-Förderaufschlüsselung weist Klima- und
        Einkommensbonus getrennt aus (Rechenlogik unverändert korrekt).
        Freitext von Erfassungen nachträglich editierbar (auch AD bei
        eigenen), Vertriebskanal manuell änderbar (Vorrang vor Sync),
        Sparten-Chips mit Zustandsanzeige, Startseite in drei Bereichen
        (Lead-Management · Angebotstool · Projektierung).

- [x] Nachtexte als Textblock-Verwaltung in der Parametrierung: heutigen
      Nachtext als „Friondo Standard" migrieren; die drei Quelldateien
      einlesen und als Blöcke „Friondo Enni", „Friondo SWD",
      „Friondo Sparkasse DU" anlegen; Blöcke editierbar, neue anlegbar
- [x] Vortext ebenfalls als Textblock: je Profil ein Standard, am Angebot
      bearbeitbar und in der Reihenfolge verschiebbar
- [x] Profil-Objekt (Nachtext + Positionsregeln + Versandregeln);
      Zuordnungstabelle Kanalwert → Profil in der Parametrierung,
      Vorbelegung: „Enni" → Enni, „Sparkasse" → Sparkasse DU, SWD-Wert
      beim Einrichten zuordnen; Fallback Standard; Umschalten am Angebot
      mit Hinweis, welche Positionen/Versandregeln sich ändern
- [x] Enni-Regeln: Bogen zeigt bei Enni-Kanal nur P01; P01 = Ja →
      Pos. 015 mit Positionspreis 599,00 € (Kennzeichen Sonderpreis,
      DB nutzt echten EK) + Pos. 162 ×1; Pos.-162-Text aktualisieren auf:
      „Voranmeldung ‚iMSys' und dynamischer Stromtarif ‚enni.flexstrom'
      Ihr intelligentes Messsystem (iMSys) – der Schlüssel zur smarten
      Energieversorgung. Neuer Zweiwegezähler inkl. Smart Meter
      (Zählertausch) und dynamischer Stromtarif ‚enni.flexstrom' direkt
      über die ENNI. https://www.enni.de/energie-und-wasser/strom/flexstrom/"
      (Preis prüfen und beibehalten); keine Vollmacht-Seite; Versand:
      CC zusätzlich energieberatung@enni.de
- [x] SWD-Regeln: P01–P03 bleiben im Bogen, wirken aber nur ins Protokoll
      (keine Positionen 014–017, keine Vollmacht); Versand: Empfänger
      leer lassen + Pflichthinweis „SWD-Kontakt eintragen", AD bleibt CC
- [x] BCC-Feld: mehrere Adressen kommagetrennt (Parametrierung)
- [x] Vertriebskanal am Lead/Vorgang manuell änderbar; manuelle Änderung
      hat Vorrang vor dem Sync; beim Ändern Rückfrage „Profil umstellen?"
- [x] migrate.py: Profile, Textblöcke, Kanal-Override, Sonderpreis-Feld

## Phase 54 – Leistungsklasse 15 kW (Serie CS8800i) & Pos. 067
- [x] Engine: Fragen-Bedingungen dürfen von der ermittelten Leistungsklasse
      abhängen („nur wenn Klasse = 15 kW"); Live-Ein-/Ausblenden, verworfene
      Antworten werden ignoriert und nicht protokolliert
- [x] Logik-Excel: Klassenzuordnung erweitern – Verbrauch 31.001–37.000 kWh
      → 15 kW (AMPEL erst über 37.000); Heizlast 16,0–18,5 → 15 kW
      (AMPEL ab 18,6)
- [x] Neue Frage (nur Klasse 15): „Farbe der Außeneinheit?" Weiß | Schwarz
      → Pos. 030 / Pos. 031; Platzierung nach der Warmwasser-Frage
- [x] Pufferfrage klassenabhängig: bei Klasse 15 Optionen 70 l | 200 l |
      300 l | 500 l | mehr als 500 l → 70 l = AWMB Pos. 055 (kein externer
      Puffer); 200/300/500 = AWE Pos. 056 + Z17 / 098 / 099; mehr = AMPEL.
      3800er-Klassen behalten die bisherige Optionsliste
- [x] Warmwasser bei Klasse 15: N02 = Ja → Pos. 065 fix, Größenfrage N03
      entfällt; KEINE Pos. 067 bei der 8800er
- [x] Pos. 067 bei den AWM-Paketen: in der Paketmatrix-Spalte „WW bis
      200 l" je Zelle ergänzen („Pos. 04x + Pos. 067") – Paketmatrix ist
      die EINZIGE Quelle (Doppler-Schutzprüfung muss grün bleiben)
- [x] Block-1-Überschrift serienabhängig („…CS8800i AW…" bei Klasse 15)
- [x] Tests: 35.000 kWh + weiß + 70 l Puffer + WW Ja → 030 + 055 + 065,
      keine 067; 35.000 kWh + schwarz + 300 l → 031 + 056 + 098 + 065;
      Heizlast 17,5 → Klasse 15; Heizlast 18,6 → AMPEL; AWM-Kontrollfall:
      18.500 kWh + WW bis 200 l → Paket 047 + 067 genau 1×

## Phase 55 – Solarthermie & bedingte Vermerke
- [x] Zusatzartikel Z24 anlegen: „Rückbau Solarthermieanlage im
      Heizungsraum inkl. Entsorgung", pauschal, VK 0,00 € / EK 0,00 €,
      Beschreibung wörtlich:
      „Technischer Hinweis: Im Angebot enthalten ist ausschließlich der
      Rückbau der Solarthermieanlage im Heizungsraum, einschließlich
      Aufputzleitungen, Solarthermie-Speicher und Solarstation, inkl.
      fachgerechter Entsorgung. Die vorhandene Solarthermieflüssigkeit
      wird abgelassen, die Anlage entleert und das Medium fachgerecht
      entsorgt. Nicht enthalten sind die dachseitigen Komponenten sowie
      die Leitungsführung außerhalb des Heizungsraums ab dem
      Übergabepunkt."
- [x] A10 „Ja, soll stillgelegt werden": AMPEL entfernen → Z24 ×1 (Block 5)
- [x] A10 „Ja, soll übernommen werden": AMPEL entfernen → Warmwasser-
      Übersteuerung: Paket zwingend AWE-Variante der Klasse (Klasse 15:
      Inneneinheit weiter über Pufferwahl AWMB/AWE – Übernahme wirkt nur
      auf die WW-Schiene); Pos. 069 ×1 statt 065/067; N03 wird
      ausgeblendet, Info „Warmwasser über bivalenten 390-l-Solarspeicher";
      Block-1-Überschrift mit Warmwasserbereitung
- [x] Generischer Mechanismus „fachliche Hinweise am Vorgang" (Warnsymbol
      in Erfassungsliste + prominenter Kasten im Angebotsentwurf, ohne
      Blockade); erster Hinweis: N02 = Nein UND A10 = übernehmen →
      „Widerspruch: Solarthermie-Übernahme erfasst, aber ‚Warmwasser über
      WP = Nein' – 069 wurde übernommen, bitte prüfen"
- [x] Neues Logik-Blatt „Vermerke" (Spalten: Text | Bedingung |
      Platzierung); Engine rendert zutreffende Vermerke als Textabsatz;
      erster Eintrag – Bedingung A04 = DG und D01 = Nein, Platzierung
      Ende Positionsteil vor Summenblock, Text wörtlich:
      „Vermerk zur Heizungsumverlegung
      Im Rahmen des vorliegenden Angebots ist vorgesehen, die bestehende
      Heizungsanlage aus dem Dachgeschoss in das Kellergeschoss zu
      verlegen. Die finale Ausführung kann erst im Zuge der detaillierten
      Feinplanung verbindlich festgelegt werden. Voraussetzung hierfür ist
      die eindeutige Klärung der hydraulischen Anbindung im
      Kellergeschoss. Insbesondere müssen geeignete Anschlusspunkte für
      Heizungs-Vorlauf und -Rücklauf sowie für die Warmwasserversorgung
      und eine gegebenenfalls erforderliche Zirkulationsleitung vorhanden
      sein. Für die Kalkulation dieses Angebots wird davon ausgegangen,
      dass entsprechende Übergabepunkte im Kellergeschoss selbst oder
      alternativ im direkt darüberliegenden Geschoss vorhanden sind und
      für die Anbindung genutzt werden können. Die erforderlichen
      baulichen Maßnahmen zur Leitungsführung einschließlich der Öffnung
      von Fliesenflächen, Trockenbaukonstruktionen sowie ggf. die Nutzung
      eines geeigneten Schachtes mit Durchführung in das Kellergeschoss
      wurden bereits berücksichtigt und sind Bestandteil der Kalkulation.
      Diese Voraussetzungen werden bauseitig als gegeben angenommen."
- [x] Tests: Stilllegung → Z24 mit 0,00 €; Übernahme + 18.500 kWh +
      „200 l" → Paket 052 (AWE) + 069, keine 065/067; Übernahme +
      N02 = Nein → 069 + fachlicher Hinweis; DG + D01 = Nein → Vermerk
      im PDF vorhanden

## Phase 56 – Angebots-Versionierung
- [x] Button „Überarbeiten" an Angeboten mit Status Versendet/Angenommen:
      erzeugt vollständige Kopie als Entwurf mit Nummer <Stamm>.2
      (fortlaufend .3, .4 …); Original → neuer Status „Überholt"
- [x] „Überholt": zählt nicht in Statistik, Summenzeile, 90-Tage-Lauf;
      Standard-Angebotsliste zeigt nur die aktuelle Version, ältere über
      Versions-Historie in der Angebots-Detailansicht
- [x] Neue Version: PDF-Zeile „Ersetzt Angebot <Nr.> vom <Datum>";
      Versand aktualisiert den monday-Deal-Wert; Verfolgung, Mail-Verlauf
      und Lead-Verknüpfung laufen an der Stammnummer weiter
- [x] Nummernkreis-Logik: Versionssuffix berührt den Zähler nicht;
      Duplizieren (bestehende Funktion) bleibt davon getrennt
- [x] Tests: Version .2 erzeugen, versenden → Original „Überholt",
      Statistik zählt 1 Angebot, monday-Wert = neue Summe

## Phase 57 – Darstellung: Förderung, Chips, Freitext, Startseite
- [x] MFH-Förderaufschlüsselung: Klima- und Einkommensbonus als getrennte
      Zeilen (je „x % anteilig auf die selbstgenutzte WE" + €-Betrag);
      Rechenlogik UNVERÄNDERT (war korrekt – prüfen, dass aus dem
      früheren Bugfix-Auftrag keine Logikänderung übrig ist, Tests
      B1–B4 müssen weiter grün sein). Kappungsregel für die Anzeige:
      Klimabonus zuerst voll, Einkommensbonus = Gesamtbonus −
      Klimabonus-Zeile (Restwertbildung, damit die Summe exakt der
      Referenz entspricht), Kappungshinweis wie im Referenz-Rechner.
      Anzeige-Tests: B1 → Klima 3.093,33 € + Einkommen 4.640,00 €;
      B3 → Klima 3.093,33 € + Einkommen 6.573,34 € (Restwert)
- [x] Förder-Baustein-Editor entsprechend MFH-tauglich beschriften
- [x] Sparten-Chips-Redesign in Leads VOT, Erfassungs- und Angebotsliste:
      farbcodiert je Sparte, Zustände erfasst (gefüllt, Haken) / offen
      (umrandet) / ausgeblendet (grau, durchgestrichen); Tooltip + Legende
- [x] Freitext nachträglich editierbar: ID/Admin überall, AD bei eigenen
      Erfassungen; Änderungen protokolliert (Name, Zeit); ist der Vorgang
      bereits in Bearbeitung/mit Angebot, erscheint der Hinweis „Freitext
      geändert" am Vorgang
- [x] Startseite in drei Bereiche: Mitte „Angebotstool" (klickbar → 
      bisherige Startansicht/Kacheln), links „Lead-Management", rechts
      „Projektierung" – beide mit rotem „Coming soon" und eigenen
      Platzhalter-Kacheln (Werte 0, ohne Logik):
      Lead-Management: Neue Leads · Kontaktierte Leads · Nachzufassende
      Leads · Disqualifizierte Leads · Terminierte Leads.
      Projektierung: Aufträge in Feinplanung · Feinplanung abgeschlossen ·
      Montage geplant · In Ausführung · Abnahme offen.
      Falls die Drei-Block-Struktur bereits als Entwurf existiert:
      Seitenblöcke auf genau diese Kachel-Sets umstellen

## Phase 58 – Migration, Abnahme & Rollout
- [ ] migrate.py final: idempotent, zweimal gegen Kopie der echten DB
- [ ] Regressionstests: alle Kontroll-Szenarien (KG, DG, Rabatt, A13,
      Heizlast, B1–B4) unverändert grün; Doppler-Schutz (065/067) grün
- [ ] Abnahmeskript v9-Block: Profile (Enni-Angebot mit 015 à 599 € +
      162, SWD-Versand ohne Empfänger, Sparkasse-Nachtext), 15-kW-Fälle,
      Solarthermie-Fälle, Vermerk, Version .2, Chips, Freitext-Edit,
      MFH-Anzeige-Split
- [ ] docs/nach-dem-update-v9.md: Parametrierung – Kanal-Zuordnung
      prüfen/ergänzen („Enni", „Sparkasse", SWD-Wert), BCC-Feld auf
      Mehrfachadressen umstellen (info@friondo.de, ggf. d.chatzis@…),
      Nachtext-Blöcke inhaltlich abnehmen, Pos.-162-Preis kontrollieren;
      Team-Hinweise: Versionierung („Überarbeiten" statt Duplizieren bei
      Änderungswünschen), Solarthermie jetzt konfigurierbar
- [ ] git push → Rollout per update.bat → Checkliste abarbeiten
