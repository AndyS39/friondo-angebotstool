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
