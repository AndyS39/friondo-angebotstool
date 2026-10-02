# Nach dem Update v23 (PLAN_LEAD_V2) – Lead-Management V2

Dieses Update baut das Lead-Management zur Version 2 aus: neue Modul-Navigation
als Icon-Leiste, Boards als Tabelle nach monday-Vorbild, dreispaltige
Kundenkartei, Anruf-Workflow mit fünf Versuchen und Stoppuhr, Terminassistent mit
Produktkompetenz und Ersatzkunde, Handelsvertreter-Sicht, persönliches Dashboard
mit To-Dos und das Board „Info-Veranstaltung“. **Alles läuft weiterhin im
Demo-Modus** (`lead_freigabe_modus = admin`): nur Admins sehen das Modul, Kundenmails
werden protokolliert statt gesendet, Kalender nur ins Testpostfach, Terminbuchungen
nur für Demo-Leads. Die Freischaltung für alle ist V3.

## Für Andreas – zum Ausprobieren im Demo-Modus

1. `update.bat` ausführen (git pull + `migrate.py`). Die Migration legt an:
   Parameter und Mail-Vorlagen (`disqualifiziert`, `online_termin_einladung`,
   `terminabsage`), Quelle „Info-Veranstaltung“, die Veranstaltungen Oktober 2026
   bis September 2027 (1. Donnerstag 18:00, Christi Himmelfahrt → 13.05.2027),
   zieht `vorgaenge.ad_id` aus bestehenden Terminen nach, setzt die
   Produktkompetenz (F3) an den AD-Profilen von Horst, Detlev B., Detlef J.,
   Kyriakos und Rudi und kennzeichnet René Golaschewski und Simon O Grady als
   Handelsvertreter (Kennzeichen „terminiert selbst“ am AD-Profil).
2. Parametrierung → Lead-Demo: Demo-Leads erzeugen, dann als Admin ins
   Lead-Management. Der Einstieg ist jetzt das persönliche **Dashboard „Meine
   Arbeit“** (Parameter `lm_startseite`: dashboard | hauptboard | uebersicht |
   anrufliste).
3. **Icon-Leiste links**: Hauptboard · Terminiert · Kontaktiert ·
   Info-Veranstaltung · E-Mail-Vorlagen, dazu „Mehr …“ mit Dashboard, Übersicht,
   Anrufliste, Kanban, Kalender, Karte, Posteingang, Statistik, Import,
   Handelsvertreter, To-Dos, Neuer Lead. Kein bisheriger Einstieg fehlt.
4. **Hauptboard** (Leads ohne Vor-Ort-Termin) mit Gruppen Neu · Pausiert ·
   Disqualifiziert, **Board Terminiert** mit Angebotserstellung · Angebotsversand ·
   Gewonnen · Verloren. Spalten wie in monday (Status-Label, Kanal-Label,
   5 Versuchs-Punkte, Avatare für Innendienst/Außendienst, tel:-Links …),
   Dialog „Spalten“ speichert Reihenfolge/Sichtbarkeit je Nutzer, Inline-
   Bearbeitung von Status (mit Pflichtgründen), Notiz, Zuständigen und
   Wiedervorlage, Kästchen + Sammelaktion „Status ändern“, Umschalter Tabelle |
   Anrufliste | Kanban.
5. **Kundenkartei** (Klick auf den Lead): links Stammdaten mit roten
   Pflichtfeldern (Liste in Parametrierung → Lead-Einstellungen), Objektart mit
   Parteien/Rechnungsadresse bei MFH, Zuständige; Mitte Reiter Timeline ·
   E-Mail-Verlauf · Anrufnotizen · Qualifizierung · Termin · Erfassungen/Angebote/
   Projekt; rechts Termine, Angebote, Erfassungen, Projekt, Anhänge, To-Dos.
   Unten: Termin vorschlagen · Termin manuell · Vorab-Gespräch (Telefon/Teams) ·
   Erfassung ohne Termin (Vorab-Angebot) · **Terminierung** (nur frei, wenn alle
   Pflichtfelder gefüllt sind und ein Termin vorgemerkt/geplant ist).
6. **Anrufen**: Klick auf die Nummer startet die Stoppuhr, der Ergebnis-Button
   speichert die Dauer. „Nicht erreicht“ öffnet den Dialog mit dem
   Kaskaden-Vorschlag (änderbar). Nach dem 5. erfolglosen Versuch steht der Lead
   auf „Nicht erreicht“, die Mail `disqualifiziert` und die Nurture-Mail (+30
   Tage) werden geplant (im Demo nur protokolliert), die Buttons sind gesperrt.
   „Meine Anrufe“ und die Rufnummernsuche (jede Schreibweise) finden Rückrufer.
7. **Terminassistent**: Vorschläge nur für Außendienstler mit passender
   Produktkompetenz (Sparten, Kombi WP+PV(+KL), MFH, Gewerbe – Pflege im
   AD-Profil), Puffer = max(30 Min, Fahrzeit), Begründung je Vorschlag mit
   Mini-Karte. Absage eines Termins öffnet den **Ersatzkunde-Dialog** (Radius 5
   → 10 km, ältere Leads bevorzugt) und sendet ein Storno-ICS.
8. **Handelsvertreter**: Ansicht „Handelsvertreter“ (Gesamtsicht je Vertreter),
   Zuweisung per Dropdown mit Ausschlussliste (Empfehlung, Messe, Sparkasse
   Duisburg, SWD, Enni – Parameter `hv_ausschluss`), Sonderregel „Deals - Rene“,
   Standard Simon für Deals/Deals - Simon („An Standard geben“, „Standard
   nachziehen“). Ein Handelsvertreter sieht nach dem Login nur seine Leads.
9. **Info-Veranstaltung**: Board mit einer Gruppe je Termin, Spalte
   „Teilgenommen“, Sammelaktionen „Status ändern“ / „In die nächste
   Veranstaltung verschieben“, Pflege der Termine unter „Termine“. Anmeldungen
   über `POST /api/leads` mit dem API-Key der Quelle `info_veranstaltung` landen
   automatisch in der nächsten Veranstaltung ab Eingang + 3 Tage (Parameter
   `info_vorlauf_tage`, Annahme A-8, [OFFEN 1]); bei bekannten Kunden erscheint
   der rote Hinweis „Kunde bereits im System“.

## Was Andreas noch pflegen muss

- **Vier Handelsvertreter als Benutzer anlegen** (Rolle Außendienst, E-Mail):
  Paolo Di Blasi, André Lind, Ralf Kinkel, Hartmut Leinenbach; danach im
  AD-Profil „Handelsvertreter – terminiert selbst“ ankreuzen. Die HV-Ansicht zeigt
  bis dahin den Hinweis „Noch nicht als Benutzer angelegt“. Ggf. „Simon O Grady“
  in „Simon O'Grady“ umbenennen (Benutzerverwaltung).
- **AD-Profile** der sechs Handelsvertreter: Startadresse, Arbeitszeiten,
  Gebiet, Outlook-Postfach (Kalenderabgleich), Kompetenzen.
- **Buchungslink** („Book with me“) je Innendienst-Kollege in der
  Benutzerverwaltung für Teams-Vorab-Gespräche (Vorlage `online_termin_einladung`).
- **Mail-Texte** `disqualifiziert`, `online_termin_einladung`, `terminabsage` in
  Parametrierung → Lead-Vorlagen durch die vorliegenden Texte ersetzen (F9).
- **Kanal „Messe“** und Kanalwerte an den Kunden pflegen, sonst greift der
  HV-Ausschluss für Messe-Leads nicht (Parameter `hv_ausschluss` prüft Kanal
  und Quellen-Key).
- **Qualifizierungsfragen für GW** (Gewerbe) im Blatt „Qualifizierung“ der
  Steuerdatei ergänzen; bis dahin ist der Bogen für GW leer.
- **Steuerdatei** `leadmanagement_logik_v1.xlsx`: neue Blätter „Objektarten“ und
  „Status“ (Labels, Farben, Board-Zuordnung), Kaskade mit 5 Stufen, Gründe
  „verloren“ – über Parametrierung → Lead-Logik hochladen, falls eine eigene
  Kopie der Datei im Einsatz ist.

## Rollout-Hinweise (V3 – Freischaltung)

- Vor der Umstellung auf `lead_freigabe_modus = alle`: Anmeldungen, die über
  `POST /api/leads` im Demo-Modus eingingen, tragen `demo = 1`. Bei der
  Umstellung **„Behalten“** wählen (Demo-Kennzeichen entfernen), sonst würden
  echte Agentur-Anmeldungen gelöscht.
- Mail-Modus bleibt bis V3 `protokoll`/`test`; `live` wird im Demo abgewiesen.
- Außendienst ohne HV-Kennzeichen behält Meine Termine/Leads VOT (F6); im Demo
  erreicht der Außendienst To-Dos nur über die Glocke (Erledigen), Anlegen
  erst bei Freigabe.
- Die bestehende Anrufliste, Tasten 1–7, Übersicht, Kalender, Karte, Statistik,
  Import und Posteingang bleiben unverändert erreichbar (unter „Mehr …“).

## Technik (Kurzfassung für die Entwicklung)

- Neue Module: `app/lead_v2.py` (gemeinsame Helfer, Gate, Zuweisung),
  `app/lead_boards.py`, `app/lead_kartei.py`, `app/lead_termin.py`,
  `app/lead_handelsvertreter.py`, `app/lead_dashboard.py`, `app/lead_todos.py`,
  `app/lead_info.py`; Router `app/routers/lm_*.py` (vor dem V1-Router
  eingebunden, gleiche Pfade haben Vorrang); Templates `leadmanagement/*`;
  Styles `app/static/lead_v2.css`; Skripte `app/static/lm_*.js`.
- Tests: `tests/test_lead_v2_*.py` (Fundament, Boards, Kartei, Anruf, Termin,
  Handelsvertreter, Dashboard, Info); Abnahme `tests/abnahme.py`; Voll-Crawl
  `scripts/voll_crawl.py --data diagnose/test_v23/data`.
- Entscheidungen und Bestandsabgleich: `docs/leadmanagement-entscheidungen.md`
  (Abschnitt „Lead-Management V2“); API: `docs/leads-api.md`.
