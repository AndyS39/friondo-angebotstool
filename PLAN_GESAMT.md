# PLAN_GESAMT – Gesamt-Update Ende September 2026

Grundlage: docs/STATUS-GESAMT.md (29.09.2026). Dieser Plan orchestriert die
offenen Stränge in der dort empfohlenen Reihenfolge. CLAUDE.md steht lokal
auf v17 (v16 = PV, v17 = Projektierung V4); jeder Teilplan trägt seinen
CLAUDE-Abschnitt nach dem Muster „Nummer = höchste + 1" ein. Grundregel für
JEDEN Rollout (bewährt am 29.09.): vorher aktuelle Server-DB-Kopie nach
diagnose\ ziehen, lokal migrieren, Crawl + Abnahmeskript dagegen – erst dann
push und update.bat.

════════════════════════════════════════════════════════════════════
TEIL A – ROLLOUTS (Server-Aktionen durch Andreas, heute möglich)
════════════════════════════════════════════════════════════════════

## A0 – Hotfix bestätigen (5 Minuten, sofort)
- [ ] Server: update.bat als Administrator ausführen
- [ ] Kontrolle: http://192.168.35.4:8000/vorgaenge/169 öffnet ohne Fehler;
      zwei weitere Vorgänge mit Wiedervorlage stichprobenartig prüfen

## A1 – v16 PV-Konfigurator ausrollen
- [ ] Vorher: frische Server-DB-Kopie nach diagnose\ (Ablauf wie gehabt:
      Task beenden → data\*.db kopieren → Task starten)
- [ ] Claude Code: Kopie migrieren + Crawl/Abnahmeskript dagegen; nur bei
      Grün weiter
- [ ] Entwicklungs-PC: git push origin 48f8be9:master
- [ ] Server: update.bat; Migrationslog prüfen (u. a. ust_satz, pv_json,
      176 PV-Artikel, 5 PV-Textblöcke)
- [ ] Kontrolle: ein PV-Testangebot durchspielen (Bedarfsauslegung,
      0-%-USt-Summenblock, Beispielrechnung, Lieferschein); ein
      WP-Kontrollangebot unverändert (Regression)
- [ ] docs/nach-dem-update-v13.md abarbeiten (heißt historisch v13,
      beschreibt PV/v16): DB-Ampel-Schwellen PV setzen, Team-Anleitung
      PV-Erfassung verteilen

## A2 – v17 Projektierung V4 ausrollen
- [ ] RISIKO-CHECK vorher auf dem Server (C:\Friondo\Angebotstool):
      git status – ist projektierung_logik_v1.xlsx dort verändert
      (Stücklisten-Upload)? Falls ja: Datei nach data\backups\ sichern und
      Claude Code fragen, WIE zusammengeführt wird, bevor update.bat läuft
      (sonst bricht git pull --ff-only)
- [ ] Entwicklungs-PC: git push (Rest bis 9d0367f)
- [ ] Server: update.bat; Kontrolle als Admin: Kanban (zweigeteilt,
      Abnahme/Freigabe getrennt), Projektakte, „Meine Aufgaben",
      BzA-Aufgabe an einem Projekt
- [ ] Ab jetzt KEINE Stücklisten-Pflege auf dem Server, solange sie in der
      Excel liegen (Provisorium 11 aus STATUS-GESAMT)

════════════════════════════════════════════════════════════════════
TEIL B – CODE-DURCHLAUF (Claude Code, alle Schritte am Stück)
════════════════════════════════════════════════════════════════════
Reihenfolge B1 → B5; je Schritt Checkboxen abhaken, am Ende von Teil B
Gesamtübersicht (Testergebnisse, offene Punkte, Rückfragen gebündelt).

## B1 – Phase 94: Doku-Bereinigung & Aufräumen (kein Funktions-Code)
- [x] CLAUDE.md-Fehler aus STATUS-GESAMT Abschnitt 3 korrigieren:
      Preislisten-Pfad; foerderrechner-Verweis streichen; „15 AMPEL-Gründe"
      → 14; v12-Routen (/lead-management, /api/leads per API-Key);
      v17-Erdleitung = Pos. 102 / A05
- [x] Überholtes markieren („überholt durch vX"): Rollenliste im Kopf um
      Projektierung/Montage/Leadmanagement ergänzen; Konfigurator-Typ
      „WP und PV"; Kanban-Phasen nur v17 gültig; v15-Paket
      „Abnahme & Freigabe" und alte Galerie-Ordnerliste; v11-Roadmap
- [x] Ergänzen: Stand 27.09. (Galerie je Sparte, Foto-Sammelbox,
      Demo-Projekte, Team-Zuweisung, Montage-Login, BnD in Abnahme,
      CEO-Review) und Hotfix 7408bb4; je Versionsabschnitt den
      Plan-Dateinamen nennen; Zuordnungstabelle Plan ↔ CLAUDE-Version
- [x] Untracked einchecken: PLAN_PROJ_V3_GOLIVE.md, PLAN_V14.md,
      PLAN_LEAD_V1.1.md, docs/leadmanagement-prototyp.html,
      PROJEKTIERUNG-KONZEPT.md (geändert), PLAN_GESAMT.md
- [x] Kleinkram aus STATUS-GESAMT 4.2: veralteten Hinweis „Formular folgt
      (Phase 82)" ersetzen; UGL-Doku auf cp850 vereinheitlichen;
      Abnahmeskript datenunabhängig machen (91/93-Punkte);
      nach-dem-update-v13.md: PV-Rückfragen aus dem Abschlussbericht
      vom 29.09. nachtragen (Gateway/Zählerzusammenlegung, EV-Quote,
      PA04, 4-Feld, Set je String, Mailtext)

## B2 – PLAN_PROJ_V3 (Phasen 84–86) mit V4-Abgleich
- [x] Vorspann: PLAN_PROJ_V3 gegen den umgesetzten V4-Stand und
      docs/projektierung-entscheidungen.md abgleichen – bereits Erledigtes/
      Überholtes im Plan streichen mit Vermerk „durch V4 erledigt";
      Abweichungen melden statt doppelt bauen
- [x] Dann Phasen 84–86 umsetzen wie geschrieben; dabei lösen sich die
      Provisorien 1–3, 14 und 19 aus STATUS-GESAMT ab (Go-live-Prüfpunkte
      von der Stücklisten-Seite in die Checkliste; TAIFUN-Auftragsdaten
      mit „gefördert"; Steckbrief-Übernahme; Pilot-Sendesperre;
      Bestandsimport)
- [x] Bestandsimport (Phase 85) NUR gegen eine DB-Kopie testen, nie direkt
      produktiv; Trockenlauf-Protokoll für Andreas
- [x] CLAUDE-Abschnitt „Projektierung Go-live" (Nummer = höchste + 1)

## B3 – PLAN_V14 als Phasen 95–97 (BzA-Datenblatt, BAFA-Nummern)
- [x] Vorab: PLAN_V14.md umnummerieren (82–84 → 95–97, Kollisions-
      empfehlung aus STATUS-GESAMT) und den CLAUDE-Abschnitt auf
      „Nummer = höchste + 1" stellen
- [x] ABGLEICH STATT NEUBAU: Es existieren bereits das BzA-Datenblatt am
      Gewerk (v15, projektierung/bza.html) und die BzA-Erfassung aus v17
      (Phase 92: BzA-ID, Kundenmail, KfW-Felder). Den bestehenden
      Generator wiederverwenden: der neue Button am ANGEBOT ruft dieselbe
      Strecke auf (funktioniert auch ohne Projekt); nur ergänzen, was
      fehlt – Blatt „BAFA-Anlagen" (Zuordnungstabelle aus PLAN_V14),
      die vier neuen Erfassungsfragen (Heizflächen → 35/55 °C,
      Nennleistung Altanlage, Inbetriebnahmejahr, Contracting) und die
      Feldlücken laut Abgleich mit Phase 92
- [x] ÄNDERUNG gegenüber PLAN_V14 (Chat-Abstimmung 29.09.): Button auch an
      EXTERNEN TAIFUN-WP-Angeboten – Gerät dann als Pflichtauswahl aus dem
      BAFA-Blatt im Datenblatt-Dialog (Erfassungsdaten liegen ja vor);
      nur bei Nicht-WP-Sparten kein Button
- [x] NEU: Feld „KfW-gefördert" (Ja | Nein) am externen Angebotseintrag –
      im „Extern erledigt"-Dialog abgefragt, nachträglich änderbar,
      Migration Bestand = unbekannt; app/bza.py wertet es aus und bietet
      nur noch bei „unbekannt" beide Wege an (löst Provisorium 2 endgültig)
- [x] Übrige PLAN_V14-Checkboxen wie geschrieben (Ersteller-Parametrierung
      HWK 1862718, rote „fehlt"-Markierungen, Tests); offene Zulieferungen
      (weiße 8800er-Nummer, Hybrox) blockieren nur ihre Zeilen

## B4 – Phase 98: Anschriften-Ausbau (Chat-Abstimmung 29.09.)
- [x] Editor-Bereich „Anschriften" mit zwei Karten – Rechnungsanschrift und
      Lieferanschrift – Felder je: Name/Firma, Zusatz (optional), Straße
      und Hausnummer, PLZ, Ort. Vorbelegung: Rechnung aus Erfassung/Kunde,
      Lieferung = Ausführungsort; frei überschreibbar
- [x] Beide Anschriften auch am Kunden in der Vorgangsakte pflegbar als
      Standard für neue Erfassungen/Angebote
- [x] PDF: Rechnungs-Name ersetzt bei Abweichung den Kundennamen im
      Empfängerblock (Briefanrede bleibt der Ansprechpartner);
      Lieferanschrift als eigene Zeile/Block, wenn abweichend vom
      Ausführungsort; Lieferschein (v16) adressiert an die Lieferanschrift
- [x] Regel: editierbar im Entwurf; bei versendeten Angeboten läuft die
      Änderung über „Überarbeiten" → Version .2
- [x] migrate.py: Anschriftenfelder an Angebot und Kunde; CLAUDE-Abschnitt
      (Nummer = höchste + 1)

## B5 – PLAN_LEAD_V1.1 (Phasen 87–89)
- [x] Umsetzen wie geschrieben (Demo-Modus, risikoarm); kann nach B1 auch
      parallel zu B2–B4 laufen, falls gewünscht
- [x] CLAUDE-Abschnitt (Nummer = höchste + 1)

════════════════════════════════════════════════════════════════════
TEIL C – GESAMTABNAHME & FINALER ROLLOUT
════════════════════════════════════════════════════════════════════
- [x] Frische Server-DB-Kopie → migrate (zweimal) → Voll-Crawl alle Rollen
      → Abnahmeskript: Ziel 0 Abstürze, Skript grün
      (30.09.: Kopie vom 29.09. 15:32 · migrate 2× sauber · Crawl 45.252
      Aufrufe, 0 Abstürze, Rollen Admin/ID/AD/Montage · Abnahme 93/93 ·
      Logik-Validierung beider Excels grün)
- [x] Regressionen: WP-Kontroll-Szenarien, B1–B4-Fördertests, PV-Testfälle,
      Doppler-Schutz – alle grün (Suite 198/198)
- [ ] git push → Server: DB-Kopie sichern, update.bat, Kontrolldurchgang
      (Angebot, PV-Angebot, Vorgangsakte, Projektakte, BzA-Datenblatt am
      Angebot UND am TAIFUN-Angebot, Anschriften im PDF, Lead-Übersicht)
- [x] docs/nach-dem-update-gesamt.md: Team-Hinweise gesammelt (PV live,
      BzA-Weg, Anschriften, Projektierung-Neuerungen für Admins)
- [ ] Andreas: CLAUDE.md im Projektwissen austauschen; Lead- und
      Projektierungs-Chat über neuen Stand informieren

## Zulieferungen (blockieren nur ihre Zeilen – Liste: STATUS-GESAMT Abschn. 6)
Priorität kurzfristig: Janni-Paket (Klassengrenzen + VK-Preisliste),
CS8800-Broschüre, TAIFUN-Muster (Auslegungszeile + Pos.-124-Text),
weiße 8800er-BAFA-Nummer, PROJ_V4-Annahmen 1–8 + BzA-Portal-URLs/Mailtext,
CEO-Entscheidungen (Rabattstufen, KfW-Wächter), Collin-Daten.
