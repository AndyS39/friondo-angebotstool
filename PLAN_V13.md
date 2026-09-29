# Umsetzungsplan v13 – PV-Konfigurator: Erfassung → fertiges PV-Angebot

Voraussetzung: der zuvor laufende Plan ist abgeschlossen und ausgerollt
(nur ein Plan zur Zeit; Absprache mit PLAN_LEAD/PLAN_PROJ). CLAUDE.md und
konfigurator_logik_v5.xlsx sind Live-Master. Je Phase: Ansatz erläutern →
umsetzen → testen → abhaken → committen. migrate.py idempotent.

QUELLEN IM PROJEKTORDNER (vom Nutzer bereitgestellt): vier Excel-Dateien
mit den PV-Positionen (Bezeichnungen, Beschreibungen, VK/EK) und ein
PV-Muster-PDF. Diese Dateien zuerst sichten: Artikel daraus importieren,
Angebotsaufbau und Nachtext am Muster ausrichten. Bei Unklarheiten in den
Dateien nachfragen statt raten.

ZULIEFERUNG SPÄTER: Dachbelegungstool (liefert Modulanzahl je Dachseite
und Quer-Anteil). Bis dahin gelten Interim-Eingabefelder im Bogen
(siehe Phase 75); die Schnittstelle so bauen, dass das Tool die Felder
später ersetzt.

## Phase 75 – Fundament: USt je Angebot, PV-Artikel, Bogen-Umbau
- [x] STEUERSATZ JE ANGEBOT: Feld ust_satz am Angebot (Standard je
      Sparte: WP/KL/WB = 19 %, PV = 0 % gem. § 12 Abs. 3 UStG).
      Wirkung überall: Summenblock (bei 0 %: Zeile „Umsatzsteuer 0 %
      (§ 12 Abs. 3 UStG): 0,00 €", Endbetrag = Netto), Rabatt (bei 0 %
      brutto = netto), DB-Berechnung, monday-Summe, Statistik.
      KfW-/Förderblock bei Sparte PV komplett aus (kein Eigenanteil,
      keine Förderzeilen). Bestehende Angebote unverändert (19 %)
- [x] PV-Artikelimport: die vier Excel-Positionslisten einlesen →
      eigener PV-Artikelbereich im Katalog (fortlaufende Nummern mit
      Präfix „PV", z. B. PV001; Bezeichnung, Beschreibung, Einheit,
      VK, EK übernehmen). Import wiederholbar (Update über Bezeichnung
      oder mitgelieferte Nummer); Artikel unter „Artikel bearbeiten"
      pflegbar wie WP-Artikel
- [x] Neue Logik-Blätter: „Aktionen PV", „Angebotsaufbau PV" (Block-
      struktur nach Muster-PDF), „PV-Parameter" mit allen Rechenwerten:
      Modulleistung 0,455 kWp; Modul-Leerlaufspannung 36,19 V;
      max. Stringspannung 1.000 V; Faktor Haushalt 1,3; Faktor WP 1,5;
      spezifischer Ertrag 960 kWh/kWp; JAZ-Umrechnung Gas/Öl→Strom 3,5;
      Wirtschaftlichkeits-Annahmen (Phase 78). Validierung erweitern
- [x] Erfassungsbogen PV umbauen:
      · NEU ganz am Anfang: „Belegungsart" – Maximalbelegung |
        Bedarfsorientierte Belegung (zwei große Buttons)
      · PO04 „Stromverbrauch (inkl. WP & WB)" ENTFERNEN; stattdessen:
        „Stromverbrauch des Haushalts in kWh" (Zahl)
      · NEU „Stromverbrauch Wärmepumpe": Zahl-Eingabe ODER Option
        „Aus WP-Erfassung ermitteln" (zieht aus der WP-Erfassung des
        Vorgangs den Gas-/Ölverbrauch und rechnet ÷ 3,5; vorhandene
        Direktangabe „Stromverbrauch Wärmepumpe" hat Vorrang; keine
        WP-Erfassung vorhanden → Hinweis und manuelle Eingabe)
      · NEU „Wallbox geplant oder vorhanden?" (Ja | Nein) + bei Ja
        „Stromverbrauch Wallbox in kWh" (Zahl)
      · NEU „Zählerzusammenlegung erforderlich?" (Ja | Nein)
      · NEU bei Flachdach: „Belegung" – Ost/West | Süd
      · INTERIM (bis Dachbelegungstool): „Maximale Modulanzahl lt.
        Dachbelegungstool" (Zahl, Pflicht) und bei Satteldach „davon
        quer verlegte Module" (Zahl, Standard 0)
      · PD06 umbenennen: „Anzahl Optimierer (Verschattung und Module
        mit abweichender Neigung, z. B. Gaube)" – Hinweistext dazu
- [x] migrate.py: ust_satz, neue Erfassungsfelder, PV-Artikel

## Phase 76 – Auslegungsmodul (pv_auslegung)
- [x] Modulanzahl: Maximalbelegung → Anzahl = Interim-Feld (später
      Dachbelegungstool). Bedarfsorientiert → Bedarf =
      (Haushalt × 1,3) + (WP × 1,5, falls vorhanden) + (Wallbox, falls
      vorhanden); kWp = Bedarf ÷ 960; Module = aufrunden(kWp ÷ 0,455);
      Deckel: nie mehr als die Maximalbelegung – wird gedeckelt, gilt
      Maximalbelegung (mit Vermerk in Protokoll und Auslegungstext)
- [x] kWp der Anlage = Module × 0,455 (für Anzeige, WR-Wahl,
      Wirtschaftlichkeit)
- [x] Strings: max. 27 Module je String (1.000 V ÷ 36,19 V = 27,6 →
      abrunden). Anzahl Strings = max(Anzahl belegter Dachseiten
      [PD07: Nein = 1, Ja = 2], aufrunden(Module ÷ 27))
      [ANNAHME – siehe Chat, Veto möglich]
- [x] Wechselrichter/Speicher (Sigenergy): benötigte WR-Leistung =
      kleinste verfügbare Stufe ≥ kWp ÷ 1,2 [ANNAHME – siehe Chat].
      Stufen 6/8/10/12 → „Hybrid System TP2 <WR>/<Bat>";
      ab 15 kW → „SigenStor <WR>/<Bat>" (15/17/20/25/30).
      Batteriekapazität: nächstgrößere verfügbare Stufe ≥ PA10
      [ANNAHME]. Die konkrete Kombi-Position aus den importierten
      PV-Artikeln wählen; existiert die Kombination nicht → AMPEL
      „WR/Speicher-Kombination nicht im Sortiment"
- [x] Auslegungs-Zusammenfassung im Protokoll und als Textzeile im
      Angebot: Module, kWp, Strings, WR/Speicher, Belegungsart mit
      Herleitung (bei Bedarf: die Formel mit Zahlen)
- [x] AMPEL-Gründe PV: WR-Bedarf über 30 kW; Belegungsart-Konflikt
      ohne Maximalangabe; PD01 = Sonstige; PD03 = Vollgerüst oder
      Sonstiges [ANNAHMEN – siehe Chat]

## Phase 77 – Positionslogik PV (Aktionen)
- [x] Block PV-Anlage: Module-Position × Anzahl (Pos. 1);
      WR/Speicher-Kombi (Pos. 2)
- [x] Unterkonstruktion nach PD01: Satteldach → „UK Satteldach"
      × (Module − quer) und, wenn quer > 0, „UK Satteldach Kreuz"
      × quer; Walmdach → wie Satteldach [ANNAHME]; Flachdach →
      „UK Flachdach Ost/West" bzw. „UK Flachdach Süd" je Belegungs-
      antwort × Module
- [x] „Montage je Modul" × Modulanzahl
- [x] Tigo TS4 Optimierer × PD06-Anzahl (nur wenn > 0)
- [x] Gerüst: PD03 = Fanggerüst → „Gerüst / Absturzsicherung";
      Vollgerüst/Sonstiges → AMPEL (Phase 76)
- [x] Elektro-Kette: „Elektroarbeiten AC ab Wechselrichter" immer;
      PA02 = Ja → Zählerschrank-Position gemäß PA03-Feldanzahl (Zu-
      ordnung aus den PV-Positionslisten; PA03 = Sonstige → AMPEL);
      PA02 = Nein UND PA07 = Ja → „Hager VA36CN AP Kleinverteiler
      3-reihig 36 PLE"; Zählerzusammenlegung = Ja → Position
      „Zählerzusammenlegung" (Text aus Positionsliste); PA08 = Nein →
      „Erdungsspieß"; DC-Überspannungsschutz: Strings ≤ 2 → „Typ 2,
      2 MPPT" ×1; genau 3 → „Typ 2, 3 MPPT" ×1; genau 4 → „Typ 2,
      2 MPPT" ×2; über 4 → AMPEL
- [x] Immer-Positionen: „Sigenergy Energy Gateway 3Ph Ersatzstrom
      inkl. Installation" als EP; „Planung, Netzanmeldung …";
      „An-/Abfahrt & Müllentsorgung"
- [x] Friondo Fit for Future analog WP über PA11/PA12/PA13
      (014-Paket bzw. 015/016/017-Logik, Vollmacht-Regeln bei
      PA12/PA13, Angebotsprofile Enni/SWD/Sparkasse greifen identisch –
      Enni: nur HEMS-Frage, 015 à 599 €, Pos. 162, keine Vollmacht)
- [x] Gewerkeübergreifende Artikel: der v10-Hinweis („ggf. ins
      PV-Angebot verlagern") funktioniert jetzt in beide Richtungen
      zwischen zwei Tool-Angeboten; Kombi-Doppelungs-Warnung erfasst
      PV-Angebote mit
- [x] Doppler-Schutz und Validierung decken die PV-Blätter ab

## Phase 78 – PV-PDF & Wirtschaftlichkeitsberechnung
- [x] Angebots-PDF PV: Aufbau, Blocküberschriften, Vor-/Nachtexte am
      Muster-PDF ausrichten; Kopf/Fußzeile, Nummernkreis, Briefanrede,
      Profile und Versand identisch zur WP-Strecke; 0-%-USt-Summen-
      block; Auslegungszeile (Phase 76); kein Förderblock
- [x] WIRTSCHAFTLICHKEITSBERECHNUNG im Nachtext (eigener Abschnitt
      „Ihre Beispielrechnung"): personalisiert aus den Angebotsdaten –
      Jahresertrag = kWp × 960 kWh; Eigenverbrauchsquote nach Ausbau
      (PV 32 % / + Speicher 33 % / + HEMS 10 % – Annahmen aus der
      Unternehmenspräsentation, Blatt „PV-Parameter", pflegbar);
      Ersparnis = Eigenverbrauch × Strompreis (Parameter, Start
      0,32 €/kWh) + Einspeisung × Vergütung (Parameter, Start
      0,078 €/kWh); Gegenüberstellung Investition (Endbetrag) →
      grobe Amortisation in Jahren. Fußnote „Beispielrechnung auf
      Basis üblicher Annahmen, keine Garantie" [Annahme-Werte siehe
      Chat – anpassbar]
- [x] DB-Ampel-Schwellen je Sparte parametrierbar (Start: PV wie WP;
      Werte passt der Nutzer später an)

## Phase 79 – Prozessintegration
- [x] PV-Katalog-Erfassungen sind nicht mehr automatisch „Individuell":
      grüne Ampel → normaler Weg „Angebot erzeugen" (PV-Angebot mit
      Sparten-Badge, Editor voll nutzbar); Ampel-Fälle → bekannte
      Individuell-Kette. Bestehende PV-Erfassungen der Warteschlange
      bleiben unberührt, können aber neu ausgewertet werden (Button
      „Erneut prüfen" wie bei WP)
- [x] Einschätzungs-Seite, Verfolgung, Versionierung, Kombi-Versand,
      monday, Statistik: für PV-Angebote identisch aktiv (Statistik
      Sparte PV zählt jetzt Tool-Angebote)
- [x] Anhänge: bestehende Regeln greifen (HEMS/SpotDynamic über
      PA-Fragen); Platz für ein Sigenergy-/Modul-Datenblatt als
      weitere Zeile, sobald geliefert

## Phase 80 – Lieferschein (spartenübergreifend)
- [ ] Button „Lieferschein (PDF)" an Angeboten mit Status Angenommen:
      Friondo-Layout, Ausführungsort, Positionsliste mit Nummer,
      Bezeichnung, Beschreibung (gekürzt) und Menge – OHNE Preise,
      Summen, Rabatte, Förderung; EP-/Alternativ-/bauseits-Positionen
      werden nicht aufgeführt; Unterschriftszeile „Ware vollständig
      erhalten" mit Datum; Dateiname LS-<Angebotsnummer>.pdf;
      Aktion im Editor-Kopf und in der Vorgangsakte

## Phase 81 – Abnahme & Rollout
- [ ] Tests: Bedarfsauslegung (Beispiel: HH 4.000, WP aus 20.000 kWh
      Gas → 5.714 × 1,5, WB 2.500 → Bedarf 16.271 kWh → 16,95 kWp →
      38 Module, Deckel prüfen); Maximalbelegung 30 Module davon 4
      quer → UK 26 + UK Kreuz 4; Strings 38 Module/2 Seiten → 2;
      WR-Wahl und Speicher-Stufen; 0-%-USt-Summenblock; Zählerschrank-
      Kette; Wirtschaftlichkeitsabschnitt mit Zahlen; Lieferschein
      ohne Preise; Enni-Profil im PV; Kombi WP+PV mit Alternativ-HEMS
- [ ] Regressionen: alle WP-Kontroll-Szenarien und B1–B4 unverändert
- [ ] CLAUDE.md: Kopf „(v13)"; Abschnitt einfügen:

      ## Neu in v13 (abgestimmt 29.09.2026)
      - PV-Konfigurator: Erfassung erzeugt vollständige PV-Angebote
        (0 % USt gem. § 12 Abs. 3 UStG, kein Förderblock). Auslegung:
        Maximal- oder Bedarfsbelegung ((HH×1,3 + WP×1,5 + WB) ÷ 960,
        Module à 0,455 kWp, Deckel = Dachbelegung), Strings (max. 27
        Module, 1.000 V), Sigenergy TP2/SigenStor-Auswahl aus kWp und
        Speicherwunsch; Parameter im Blatt „PV-Parameter". Positions-
        logik: UK je Dachart inkl. Kreuz-Verlegung, Montage je Modul,
        Tigo-Optimierer, Gerüst (Vollgerüst → individuell), Elektro-
        Kette (Zählerschrank/UV/Zusammenlegung/Erdungsspieß/DC-ÜSS
        nach Strings), Immer-Positionen, Fit for Future analog WP
        inkl. Profile. Wirtschaftlichkeits-Beispielrechnung im
        Nachtext (parametrierbare Annahmen). Dachbelegungstool folgt –
        bis dahin Interim-Felder für Modulanzahl/Quer-Anteil.
      - Steuersatz je Angebot (PV 0 %, sonst 19 %) in Summen, DB,
        monday und Statistik. DB-Ampel-Schwellen je Sparte
        parametrierbar.
      - Lieferschein-PDF (ohne Preise) für angenommene Angebote
        aller Sparten.

- [ ] docs/nach-dem-update-v13.md: Team-Anleitung PV-Erfassung neu
      (Belegungsart, Interim-Felder, Verbrauchsfragen), Hinweis
      Warteschlangen-Altfälle optional neu prüfen, DB-Schwellen PV
      setzen; Zulieferungen offen: Dachbelegungstool,
      Sigenergy-Datenblatt
- [ ] git push → Rollout per update.bat → Checkliste
