# Umsetzungsplan v10 – Kundenvorgänge: Akte, Kombi-Versand, Notizen

Voraussetzung: Phasen 0–58 umgesetzt, v9 läuft auf dem Server (NICHT parallel
zu v9 bauen – erst nach dessen Rollout starten). CLAUDE.md und Logik-Excel
sind Live-Master. Je Phase: Ansatz erläutern → umsetzen → testen → abhaken →
committen. Schema-Änderungen in migrate.py (idempotent).

Leitidee: Das Angebot bleibt die Einheit für Kalkulation und Dokument.
Der VORGANG (= Lead/Kundenanfrage) wird die Einheit fürs Arbeiten: Er
bündelt alle Sparten, Erfassungen, Angebote, Mails, die Verfolgung und
die Notizen – und er ist die Einheit für den gemeinsamen Versand.

## Phase 59 – Vorgangsakte
- [x] CLAUDE.md: Kopf auf „(v10)"; neuen Abschnitt einfügen:

      ## Neu in v10 (abgestimmt 05.09.2026)
      - Kundenvorgänge: Jeder Lead ist ein Vorgang mit eigener Akte –
        sie bündelt Sparten-Chips, alle Erfassungen, alle Angebote
        (Tool/TAIFUN, inkl. Versionen), Mail-Verlauf, Verfolgung und
        einen chronologischen Notizen-Chat (Autor + Zeitstempel,
        Einträge unveränderlich; AD bei eigenen Vorgängen, ID/Admin
        überall). Verfolgung (Hot-Ampel, Wiedervorlage) lebt auf
        Vorgangsebene – EINE Ampel je Kundenanfrage; Angenommen/
        Abgelehnt bleibt je Angebot. Der 90-Tage-Lauf respektiert die
        Vorgangs-Wiedervorlage für alle Angebote des Vorgangs.
      - Kombi-Versand: Aus der Akte mehrere versandfertige Angebote in
        EINER Mail versenden (mehrere separate PDFs). Kombi-Vorlage mit
        {angebotsliste} (je Angebot Sparte + Endbetrag, WP zusätzlich
        Eigenanteil) – Einzelbeträge, keine Gesamtsumme. Broschüren
        dedupliziert. Die Versand-Erkennung setzt alle enthaltenen
        Angebote auf „Versendet"; der Mail-Verlauf hängt an allen.
      - Externe TAIFUN-Einträge können übergangsweise ein PDF tragen
        (Upload am Eintrag), damit Kombi-Mails alle Angebote enthalten.
      - Alternativ-Kennzeichen je Position: „in anderem Angebot enthalten"
        – Darstellung wie EP (ausgewiesen, nicht in Summe/KfW/DB) mit
        automatischem Vermerk und Verknüpfung zum Geschwister-Angebot des
        Vorgangs. Parametrierungs-Liste „gewerkeübergreifende Artikel"
        löst bei Mehr-Sparten-Vorgängen einen fachlichen Hinweis aus;
        der Kombi-Versand warnt bei doppelt voll berechneten Artikeln
        (nur zwischen Tool-Angeboten prüfbar).
      - monday: Deal-Wert = Summe aller versendeten, nicht überholten
        Angebote des Vorgangs (aktualisiert bei Versand, neuer Version,
        Ablehnung). Statistik zusätzlich je Vorgang (Kombiquote,
        Auftragswert je Vorgang) und als Monatsübersicht Auftragseingang
        (angenommene Angebote), filterbar.
      - Außendienst-Ausbau: Suche in „Meine Angebote"; vollständige
        Angebotsansicht der eigenen Angebote (weiterhin ohne EK/DB);
        AD kann den Gesamtrabatt selbst setzen, solange die DB-Ampel
        nicht rot wird – darunter Freigabe-Anfrage an den Innendienst.
        Wiedervorlagen haben einen Verantwortlichen: vom AD gesetzte
        erscheinen in dessen Sicht, nicht in der ID-Kachel.

- [x] Datenmodell: Vorgang als führendes Objekt formalisieren (Anker =
      Lead; für manuell angelegte Kunden ohne Lead wird beim ersten
      Erfassen automatisch ein Vorgang erzeugt); bestehende
      Verknüpfungen (Erfassungen, Angebote, Lead) daran aufhängen
- [x] Vorgangsakte als Detailseite: Kopf (Kunde, Ausführungsort, Kanal/
      Profil, Sparten-Chips, Vertriebler), Bereiche Erfassungen ·
      Angebote (mit Status, Version, Endbetrag; TAIFUN-Badge) ·
      Mail-Verlauf · Verfolgung · Notizen
- [x] Einstiege: Klick auf den Kunden in Leads VOT, Erfassungs- und
      Angebotsliste öffnet die Akte; Suche findet Vorgänge; Akte bleibt
      nach Abschluss/Ausblenden des Leads erreichbar
- [x] AD-Sicht (mobil): eigene Vorgänge lesbar inkl. Angebots-PDFs
      (read-only, ohne EK/DB) – ersetzt perspektivisch „Meine Angebote",
      der Menüpunkt bleibt vorerst und verlinkt auf die Akten
- [x] BUGFIX: Erfassung, die ohne Leads-VOT-Eintrag aus dem Angebote-/
      Kundenbereich gestartet wird, hat am Ende keinen Absenden-/
      Versand-Button – reproduzieren, Ursache beheben, Vorgänge ohne
      Lead müssen den identischen Ablauf haben wie Lead-Vorgänge
- [x] „Meine Angebote": Suchfeld (Name, Ort, Angebotsnummer)
- [x] AD-Vollansicht der eigenen Angebote: alle Positionen, Preise,
      Summen, Status, Verlauf und PDF – weiterhin OHNE EK, DB-Werte
      und Editor (Entscheidung siehe Chat; falls doch inkl. DB: nur
      diese Zeile ändern)
- [x] AD-Rabatt mit Freigabe-Workflow: AD kann am eigenen Angebot den
      Gesamtrabatt (Brutto, v4-Mechanik) eingeben. Zulässig, solange
      der resultierende DB die Rot-Schwelle der Ampel nicht
      unterschreitet – der AD sieht dabei nur die Ampel-FARBE als
      Rückmeldung, keine €-DB-Werte. Bei Entwürfen wirkt der Rabatt
      direkt; bei versendeten Angeboten erzeugt er automatisch
      Version .2 als Entwurf (v9-Mechanik) – bereit für Vor-Ort-
      Signatur oder ID-Versand. Würde der Rabatt die Ampel auf Rot
      drücken: Freigabe-Anfrage an den Innendienst (Kachel/Hinweis
      „Rabatt-Freigaben offen"; ID genehmigt → Rabatt/Version
      entsteht, oder lehnt mit Kommentar ab); alles im Notizen-Chat
      des Vorgangs protokolliert
- [x] migrate.py: Vorgangs-Objekt + Verknüpfungen, rückwirkend aus
      Bestandsdaten erzeugen (je Lead bzw. je Kunde mit Erfassungen)

## Phase 60 – Verfolgung & Notizen auf Vorgangsebene
- [x] Hot-Ampel + Wiedervorlage vom Angebot auf den Vorgang verlagern;
      Anzeige in Akte (oben) und in den Listen; Einschätzungs-Seite der
      Erfassung schreibt die Startwerte auf den Vorgang
- [x] Migration Bestand: je Vorgang heißeste vorhandene Angebots-Ampel
      und früheste zukünftige Wiedervorlage übernehmen; alte Werte an
      den Angeboten stilllegen (Historie bleibt lesbar)
- [x] 90-Tage-Automatik: zukünftige Vorgangs-Wiedervorlage schützt ALLE
      Angebote des Vorgangs
- [x] Wiedervorlagen-Verantwortlicher: Vorbelegung = Ersteller, durch
      ID änderbar. Kachel „Fällige Wiedervorlagen" und Listen zeigen
      rollenbezogen die eigenen (ID sieht ID-Wiedervorlagen, AD seine
      in der mobilen Sicht – dort neue kleine Fälligkeits-Anzeige);
      Migration: bestehende Wiedervorlagen dem Ersteller zuordnen
- [x] Notizen-Chat am Vorgang: chronologisch, Eingabefeld unten, Eintrag
      wird automatisch mit „<Name> <TT.MM.JJ> <HH:MM> Uhr:" versehen,
      Einträge unveränderlich (kein Bearbeiten/Löschen); Rechte: ID/Admin
      alle Vorgänge, AD eigene (auch mobil); bestehende Verfolgungs-
      Notizen der Angebote werden als Alt-Einträge in den Chat migriert
      (mit Herkunftsvermerk)
- [x] „Neue Notizen"-Punkt je Benutzer in Vorgangsliste/Akte (seit
      letztem Öffnen), dezent
- [x] Statistik-Kachel „Fällige Wiedervorlagen" zählt ab jetzt Vorgänge
- [x] migrate.py: Vorgangs-Verfolgung, Notizen-Tabelle, Gelesen-Marker

## Phase 61 – Kombi-Versand
- [x] In der Akte: Auswahl mehrerer versandfertiger Angebote (Entwurf/
      Versand vorbereitet; TAIFUN-Einträge nur mit hinterlegtem PDF) →
      „Gemeinsam versenden"
- [x] Eine Mail, mehrere PDF-Anhänge: Betreff „Ihre Angebote <Nr1>,
      <Nr2> – Friondo GmbH"; neue Kombi-Vorlage in der Parametrierung
      mit Platzhaltern {angebotsliste} (je Zeile: Sparte, Angebotsnummer,
      Endbetrag; bei WP zusätzlich „Eigenanteil nach Förderung: …"),
      {briefanrede}, {vertriebler} usw.; KEINE Gesamtsumme
- [x] Profil-/Versandregeln des Vorgangs gelten (Enni-CC, SWD-Empfänger
      leer, Mehrfach-BCC); Broschüren-Anhänge über alle Angebote
      dedupliziert (allgemeine einmal, produktspezifische je Sparte)
- [x] Versand-Erkennung: setzt alle enthaltenen Angebote auf „Versendet"
      (inkl. Rückspielung), Konversation wird allen zugeordnet;
      Brief-Symbol an Vorgang und Angeboten
- [x] Alternativ-Kennzeichen je Position im Editor: „Alternativ – in
      anderem Angebot enthalten" mit Verknüpfung (Auswahl aus Angeboten
      des Vorgangs oder Freitext, z. B. „PV-Angebot"); Darstellung wie
      EP (Preis ausgewiesen, nicht in Summe/KfW-Basis/DB), automatischer
      Vermerk unter der Position: „Hinweis: Diese Position ist im
      parallel vorliegenden <Verknüpfung> enthalten und kommt nur zum
      Tragen, wenn ausschließlich das vorliegende Angebot beauftragt
      wird."; Kennzeichen jederzeit entfernbar (Position zählt dann
      wieder voll)
- [x] Parametrierung „Gewerkeübergreifende Artikel" (Startbestückung:
      Pos. 014/015/016/017, 104, Z22, 152, Z23 – Liste pflegbar);
      fachlicher Hinweis am Vorgang, wenn er mehrere Sparten hat und
      ein solcher Artikel in einem Tool-Angebot VOLL berechnet ist:
      „Prüfen: ggf. ins PV-Angebot verlagern oder Alternativ-Kennzeichen
      setzen (Förder-/USt-Optimierung)"
- [x] Kombi-Versand-Warnung, wenn dieselbe Artikelnummer in mehreren
      angehängten Tool-Angeboten voll berechnet ist (TAIFUN-PDFs sind
      nicht prüfbar – Hinweis in docs)
- [x] migrate.py: Alternativ-Kennzeichen + Verknüpfungsfeld
- [x] Einzelversand bleibt unverändert möglich
- [x] Tests: Kombi aus WP-Tool-Angebot + PV-TAIFUN-Eintrag (mit PDF) →
      1 Mail, 2 Angebots-PDFs + deduplizierte Broschüren, beide auf
      „Versendet", monday-Wert = Summe; WP-Angebot mit HEMS als
      Alternativ-Kennzeichen → nicht in Summe/KfW/DB, Vermerk im PDF,
      monday-Summe ohne diese Position; fachlicher Hinweis erscheint
      bei Mehr-Sparten-Vorgang mit voll berechnetem HEMS

## Phase 62 – TAIFUN-PDF & monday-Summenlogik
- [x] Externer Angebotseintrag: PDF-Upload (ersetzbar, mit Zeitstempel);
      UI-Hinweis „Übergangslösung – Ziel ist die Erstellung im Tool";
      ohne PDF ist der Eintrag im Kombi-Versand nicht wählbar (Tooltip)
- [x] monday-Rückspielung umstellen: Deal-Wert = Summe der Endbeträge
      aller versendeten, nicht überholten, nicht abgelehnten Angebote
      des Vorgangs; Neuberechnung bei Versand, Versionierung, Ablehnung,
      Löschung; Protokoll wie gehabt
- [x] Migration: Deal-Werte der aktiven Vorgänge einmalig nach neuer
      Summenlogik aktualisieren (Trockenlauf-Liste zur Bestätigung)
- [x] migrate.py: PDF-Feld extern, Summen-Trigger

## Phase 63 – Statistik, Abnahme & Rollout
- [x] Statistik: Kombiquote (Anteil Vorgänge mit >1 versendeter Sparte),
      Auftragswert je Vorgang; bestehende Auswertungen unverändert
- [x] Statistik „Auftragseingang je Monat": Summe der Endbeträge aller
      im jeweiligen Monat auf „Angenommen" gesetzten Angebote (Basis:
      Statuszeitpunkt), als Diagramm + Tabelle, filterbar nach
      Vertriebler, Kanal, Sparte und Tool/TAIFUN
- [x] Logik-Excel (Angebotsaufbau): Erdleitung (Pos. 102 aus A05) von
      Block 2 „Leitungen und Heizkreise" in Block 6 „Aufstellung der
      Außeneinheit und Hauseinführung" verschieben (zur Fundament-/
      Konsolen-Position); Fassadenleitung bleibt in Block 2;
      Kontroll-Szenario-PDFs entsprechend prüfen
- [x] Regressionstests: alle Kontroll-Szenarien grün; Einzelversand,
      Status-Automatik, 90-Tage-Lauf mit Vorgangs-Wiedervorlage
- [x] Abnahmeskript v10-Block: Akte, Notizen-Chat (Format, Rechte,
      Unveränderlichkeit), Kombi-Versand, TAIFUN-PDF, monday-Summe,
      Migrationen (Ampeln, Notizen, Deal-Werte)
- [x] docs/nach-dem-update-v10.md: Kombi-Vorlage texten/abnehmen,
      Team-Hinweise (Verfolgung jetzt am Vorgang, Notizen-Chat-Regeln,
      Kombi-Versand-Ablauf, TAIFUN-PDF-Pflicht für Kombi); Hinweis an
      den Projektierungs-Chat: „Vorgang" ist ab v10 das zentrale Objekt –
      Projekte docken am Vorgang an (ein Vorgang, ggf. mehrere Gewerke)
- [x] git push → Rollout per update.bat → Checkliste abarbeiten
