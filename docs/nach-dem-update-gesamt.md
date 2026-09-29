# Nach dem Gesamt-Update (v16 – v21) – Hinweise fürs Team

Stand 30.09.2026 · gilt für den Rollout aus PLAN_GESAMT Teil C
(Commits bis `c138838`). Einzelheiten je Version: CLAUDE.md und die
jeweiligen `nach-dem-update-*.md`.

## Für alle

- **PV-Angebote kommen jetzt aus dem Tool** (v16): PV-Erfassung → Ampel →
  „Angebot erzeugen“; 0 % USt, Beispielrechnung, Lieferschein.
  Anleitung: docs/nach-dem-update-v13.md (heißt historisch v13).
- **Anschriften** (v20): Im Angebots-Editor gibt es den Bereich
  „Anschriften“ mit Rechnungs- und Lieferanschrift (Name/Firma, Zusatz,
  Straße, PLZ, Ort). Änderbar nur im Entwurf – bei versendeten Angeboten
  über „Überarbeiten“. Im PDF erscheint nur, was vom Ausführungsort
  abweicht; der Lieferschein geht an die Lieferanschrift. Standard-
  Anschriften je Kunde pflegen Innendienst und Außendienst (eigene Vorgänge)
  in der Vorgangsakte (aufklappen „Anschriften“).

## Außendienst (WP-Erfassungsbogen)

- Neu: **A20 „Nennleistung der bestehenden Heizung in kW“** (Pflicht,
  vom Typenschild; unbekannt → 0) und **N11 „Contracting-Modell?“**
  (vorbelegt Nein). **A02** heißt jetzt „Inbetriebnahmejahr (Baujahr) der
  bestehenden Heizung“. Hintergrund: KfW-Portal (BzA). Details:
  docs/nach-dem-update-v19.md.

## Innendienst

- **BzA-Datenblatt (PDF)** an jedem WP-Angebot (Editor-Kopf,
  Vorgangsakte) – auch an TAIFUN-WP-Einträgen (Gerät dann aus der
  BAFA-Liste wählen). Internes Arbeitsblatt zur Portaleingabe, rot
  markierte Zeilen beim Kunden erfragen.
- **„Extern erledigt“** (WP) fragt jetzt „KfW-gefördert?“ – nachträglich am
  TAIFUN-Eintrag änderbar; steuert die BzA-Aufgabe der Projektierung.
- Parametrierung → **BzA-Ersteller**: Standard-Ansprechpartner wählen;
  E-Mail/Telefon in der Benutzerverwaltung pflegen.

## Projektierung (zunächst nur Admins – Demo-Modus)

- v17: Board zweigeteilt, Abnahme/Freigabe getrennt, Vorlauf-Ampel,
  BzA-Erfassung + Kundenmail, UGL-Bestellung, Stücklisten-Pflege.
- **BzA-Kundenmail:** Betreff/Text und das Häkchen „BzA-Kundenmail
  versenden“ unter Parametrierung → Projektierung-Einstellungen („Kundenmail
  BzA“). Versand immer erst nach Vorschau + Klick; „ohne Mail abschließen“,
  wenn der Kunde die BzA anders bekommt.
- v18: **Auftragsdaten** bei TAIFUN-Aufträgen (Pflichtseite nach „Angebot →
  Projekt“), **Bestandsimport** laufender Projekte (Parametrierung →
  Bestandsimport; erst gegen eine DB-Kopie testen, Trockenlauf:
  docs/bestandsimport-trockenlauf.md), Freigabe **Pilot** (Admin + Pilot-
  Benutzer), **Go-live-Checkliste** (Parametrierung).
- Stücklisten NICHT auf dem Server pflegen, solange sie in der Excel liegen
  (sonst blockiert das nächste update.bat).

## Lead-Management (Demo-Modus, nur Admins)

- Neuer Einstieg **Übersicht** (Kacheln, Eingänge je Tag nach Quellen-Typ,
  Kontaktstatus, Quelle × Kanal); das Cockpit ist darin aufgegangen.
- **Anrufliste** gruppiert (Jetzt dran · Weiter versuchen · Neu heute ·
  Wiedervorlagen · Sonstige) mit Versuchs-Punkten und Kontaktstatus-Satz.
- Landingpages: unbekannte Quellen/Kampagnen legen sich selbst an –
  Formular-Standard für die Agentur: docs/formular-standard-agentur.md.

## Admin – nach dem Update prüfen

0. **Vor dem Bestandsimport:** Parametrierung → Kunden-Dubletten (auf der
   Server-Kopie vom 29.09.: 4 Gruppen mit 10 Kunden, u. a. #1/#2/#3; die
   Gruppe #299/#398 hat abweichende Straßen – einzeln prüfen).
1. Migrationslog: Spalten v16–v21, 176 PV-Artikel, V4-Paketumbau,
   „v19: BzA-Ersteller-Parameter angelegt“, „v20: … Lieferanschriften
   strukturiert“, Lead-Startquelle `unbekannt`.
2. Parametrierung → „Parametrierung neu einlesen“: Validierung grün.
3. Kontrolldurchgang (PLAN_GESAMT Teil C): WP-Angebot, PV-Angebot,
   Vorgangsakte, Projektakte, BzA-Datenblatt am Tool- und TAIFUN-Angebot,
   Anschriften im PDF, Lead-Übersicht.
4. Parametrierung → BzA-Ersteller, Go-live-Checkliste ansehen.
