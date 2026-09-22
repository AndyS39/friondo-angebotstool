# Projektierung V1 – Bedienanleitung (v11)

Kurzer Leitfaden für den Alltag. Grundlage: PROJEKTIERUNG-KONZEPT.md
(abgestimmt 20.09.2026). V1 läuft als **Demo im Live-Tool**: solange der
Freigabe-Schalter auf „Nur Admin“ steht, sehen nur Admins das Modul
(Portal-Badge „Demo · Coming soon“). Freischalten: Parametrierung →
Projektierung-Einstellungen → „Alle berechtigten Rollen“.

## 1. Angebot → Projekt

- Am **angenommenen** Angebot (Editor, Liste oder Vorgangsakte) erscheint der
  Button **„Angebot → Projekt“**. Er öffnet den Anlage-Dialog:
  - **Projekt-Wahl**: neues Projekt oder das offene Projekt des Vorgangs
    (je Vorgang gibt es höchstens ein offenes Projekt).
  - **Sparten** (WP/PV/KL/WB): je Sparte entsteht ein **Gewerk**.
  - **Projektleiter** ist Pflicht; Feinplaner/Elektroplaner optional
    (sonst greifen die Standards aus den Einstellungen).
- Beim Anlegen passiert automatisch: PR-Nummer (PR-JJNNNN), Ordnerstruktur
  unter `data/projekte/<PR-Nr.>/`, Angebots-PDF-Ablage, die
  IMMER-Aufgabenpakete der Sparte, Verlaufseintrag und Benachrichtigungen.
- Wird später eine **neue Version** des Angebots angenommen, zieht das Gewerk
  automatisch nach (Auftragswert aktuell, Verlaufseintrag).

## 2. Board, Liste, Termine, Meine Aufgaben

- **/projektierung** ist das Kanban-Board: eine Karte je Projekt in der Spalte
  seines Status (= am wenigsten fortgeschrittenes offenes Gewerk). Chips je
  Gewerk zeigen Phase, Planungs-Ampel, nächsten Termin und offene/überfällige
  Aufgaben. Drag & Drop wechselt die Phase (Wächter wie in der Akte; bei
  Kombi-Projekten fragt ein Dialog, welches Gewerk gemeint ist).
- Filter: Sparte (schaltet auf Karte je Gewerk um), Projektleiter, Team,
  Kanal, PLZ-Präfix, Suche, „Storniert anzeigen“.
- **Liste**: dieselben Filter als Tabelle mit Sortierung, Summenzeile und
  CSV-Export. **Termine**: Wochen-/Monatsansicht mit Termin-Dialog
  (Montage-/Feinplanungstermine berechnen `M±N`/`FP+N`-Fälligkeiten nach).
- **Meine Aufgaben**: Überfällig · Heute · Diese Woche · Später · Neu
  zugewiesen – mit Status-Dropdown und Erledigt-Haken.

## 3. Projektakte

- Kopf: Kunde, Ausführungsadresse, Projektleiter, Kanal, Notiz.
- Je Gewerk eine Spalte: Phasen-Stepper, Ampel, Zuweisungen, Heizlast,
  Aufgaben (nach Paketen gruppiert, mit Kommentaren je Aufgabe), Termine,
  Auftrag (Positionen; EK/DB nur mit Berechtigung), Phase ändern / Storno /
  Rechnungsfreigabe.
- **Wächter** je Phasenwechsel (z. B. offene Pflichtaufgaben, fehlender
  Montagetermin): kein hartes Sperren – mit Begründung geht es weiter
  (Override wird protokolliert).
- **Rechnungsfreigabe** fragt nach Restarbeiten (Pflichtfrage); mit
  Restarbeiten entsteht eine Aufgabe (+14 Tage), die Buchhaltung wird
  benachrichtigt, das Gewerk wird „Abgeschlossen“.
- Reiter: **Dokumente** (Ordnerstruktur, Upload auch mobil),
  **Verlauf & Kommentare** (@Name erwähnt Benutzer), **Subs & Bestellungen**.

## 4. Aufgabenpakete pflegen

- Steuerdatei `daten/projektierung_logik_v1.xlsx` (Blätter Aufgabenpakete,
  Paketregeln, Ordnerstruktur, Sub-Typen). Upload/Prüfbericht unter
  Parametrierung → **Projektierung-Logik**; Änderungen wirken auf **neue**
  Paket-Aktivierungen, bestehende Aufgaben bleiben unverändert.
- V1 aktiviert die IMMER-Pakete je Sparte; weitere Pakete lassen sich in der
  Akte manuell aktivieren (die Feinplanungs-Fragen kommen ab V2).
- Fälligkeitsregeln je Schritt: `+N` (ab Aktivierung), `FP+N` (ab
  Feinplanungstermin), `M-N`/`M+N` (um den Montagetermin).

## 5. Rollen

- **Admin/Innendienst**: alles (Innendienst erst nach Freischaltung).
- **Projektierung** (Hauptrolle): Projektierung voll; Angebote, Erfassungen
  und Kunden nur lesend (Angebotsliste ohne DB-Spalte, außer das Häkchen
  „Kalk.“ ist gesetzt); Parametrierung nur Projektierung-Logik, Teams,
  Subunternehmer.
- **Montage** (Hauptrolle): nur der mobile Bereich **/montage** – „Meine
  Einsätze“ (Termine der eigenen Teams), Steckbrief ohne Preise, Foto-Upload,
  „Montage gestartet“ / „Montage fertig“ (mit Pflicht-Kurzbericht).
- **Außendienst**: am eigenen Angebot der Block „Projektstand“ (Phase, Ampel,
  nächster Termin, Projektleiter mit Telefon) + Kommentar an die Projektierung.
- **Zusatzrollen**: In der Benutzerverwaltung lassen sich projektierung/
  montage zusätzlich zur Hauptrolle anhaken (z. B. Innendienst, der auch
  projektiert); dort auch Team-Zuordnung, Telefon und Benachrichtigungs-Mail
  (aus / sofort / Tagesdigest 07:15).

## 6. Benachrichtigungen

- Glocke in der Kopfzeile (alle Rollen): Zähler + letzte 20, Klick öffnet den
  Link und markiert gelesen.
- Ereignisse: Aufgabe zugewiesen, @Erwähnung, Phasenwechsel, neues Gewerk,
  Freigabe, täglicher Fälligkeits-Lauf 07:00 (gebündelt je Benutzer).
- E-Mail je Benutzerprofil (aus / sofort / Tagesdigest 07:15) über Graph;
  Absender-Postfach in den Projektierungs-Einstellungen (Fehler stehen dort
  im Mail-Protokoll, der Versand blockiert das Tool nie).

## 7. Ablage

`data/projekte/<PR-Nr.>/` mit der Standardstruktur aus dem Konzept (3.5);
Ordner der Ebene „gewerk“ liegen je Sparte unter `<Sparte>/<Ordner>`.
Änderbar über die Steuerdatei (Blatt Ordnerstruktur), wirkt auf neue Projekte.
