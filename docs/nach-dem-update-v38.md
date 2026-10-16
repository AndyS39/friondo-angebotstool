# Nach dem Update auf v38 – Foto-Upload (Pop-up, Offline-Puffer, Mehrfach-Löschen), Erfassung (Zwischenspeichern, Korrektur), Leads VOT / Mobil (Vergangene Termine, Termin nicht stattgefunden) (PLAN_V23, Phasen 201–205)

Stand 17.10.2026 (Plan-Kette v36 → v37 → v38, Rollout erst nach der gemeinsamen Rollout-Prüfung am Kettenende – erledigt 17.10.2026, `docs/updates.md` 4g).
Alle Datenbankänderungen sind additiv – der v37-Code läuft auf der v38-Datenbank weiter (`rollback.bat --nur-code`).

## Galerie: Hochladen mit Pop-up, wartende Fotos, Mehrfach-Löschen (Phase 201)

**Für den Außendienst (und alle, die Fotos hochladen):**
- **Fotos hochladen:** Der Knopf heißt jetzt „Hochladen (3)“ – die Zahl ist die Anzahl der Fotos in der Liste. Nach
  dem Tippen erscheint ein Fenster „Fotos werden hochgeladen“ mit Balken je Foto und einer geschätzten Restdauer;
  am Ende steht „3 Fotos hochgeladen“ (schließt von selbst) oder „2 von 3 Fotos hochgeladen“ mit dem Grund je
  Foto und dem Knopf „Erneut versuchen“ (sendet nur die fehlgeschlagenen). Die Seite wird nicht mehr neu geladen,
  die neuen Fotos stehen sofort im Ordner. „Abbrechen“ stoppt den Upload, die Liste bleibt erhalten.
- **Kein Netz:** Bricht die Verbindung ab, erscheint „Kein Netz. Die Fotos bleiben gespeichert und werden später
  hochgeladen.“ Die Fotos liegen dann im Browser des Handys. Beim nächsten Öffnen der Galerie dieses Kunden (mit
  Netz) steht oben „n Fotos warten auf Upload (seit …)“ – „Jetzt hochladen“ tippen. Die Startseite „Erfassungen“
  zeigt wartende Fotos aller Kunden mit Link. Es passiert nichts automatisch im Hintergrund; wer die Browserdaten
  löscht oder ein anderes Gerät nimmt, hat die wartenden Fotos nicht. Höchstens 50 Fotos / 100 MB warten gleichzeitig.
- **Fotos löschen:** In jedem Ordner „Auswählen“ tippen, Kästchen an den Fotos setzen (Außendienst nur an den
  selbst hochgeladenen), „n Fotos löschen“ – nach der Sicherheitsabfrage sind sie endgültig weg (Eintrag im
  Notizen-Chat). In der Upload-Liste entfernt „Auswählen“ mehrere Fotos auf einmal aus der Liste.
- **Innendienst/Projektierung:** „Auswählen“ und „n Fotos löschen“ stehen in jedem Galerie-Ordner (Vorgangs-/Projektakte);
  Montage löscht weiterhin nicht. Einzel-Löschen (✕) und Lightbox sind unverändert.

## Erfassung: Später fortsetzen, Antworten korrigieren, Objekt in der Liste (Phase 202/204)

**Für den Außendienst**
- **Später fortsetzen:** Oben rechts im Erfassungsbogen steht „Später fortsetzen“. Der Knopf speichert alles,
  was auf der aktuellen Seite ausgefüllt ist (auch wenn Pflichtfragen noch offen sind), und führt zur
  Erfassungsliste („Erfassung gespeichert. Sie können jederzeit weitermachen.“). Wer stattdessen die Seite
  einfach verlässt, bekommt bei ungespeicherten Eingaben die Browser-Nachfrage – Antworten der aktuellen Seite
  werden sonst wie bisher nur mit „Weiter“ gespeichert. Entwürfe stehen in der Liste als „Entwurf · Frage 12 von
  31“; Antippen öffnet den Bogen bei der ersten offenen Frage („Fortgesetzt bei Frage 12“). Entwürfe, die
  älter als 30 Tage sind, sind orange markiert – bitte fortsetzen oder löschen.
- **Antworten korrigieren:** Auf der Übersichtsseite einer abgesendeten Erfassung (und in der Vorgangsakte)
  gibt es „Antworten korrigieren“ – nur für eigene Erfassungen. Eine Frage antippen („ändern“), Antwort
  anpassen, „Korrektur speichern“. Jede Korrektur steht als Notiz „Erfassung nachträglich geändert …“ im
  Notizen-Chat des Kunden und als Badge an der Erfassung. Sobald das Angebot versandfertig oder versendet ist,
  ist der Knopf gesperrt („Angebot ist bereits versandfertig“) – dann bitte den Innendienst ansprechen
  (Überarbeiten/neue Version).
- **Objekt in der Liste:** Jede Erfassung zeigt jetzt das Objekt (Bezeichnung und Adresse), bei Großkunden mit
  mehreren Objekten also z. B. „Halle Nord · Nordring 12, 47167 Duisburg“.

**Für den Innendienst**
- Die Erfassungsliste hat den Reiter „Entwürfe“; in „Alle“ stehen Entwürfe mit Badge „Entwurf · Frage x von y“
  (orange ab 30 Tagen). Aus einem Entwurf lässt sich kein Angebot erzeugen.
- Badge „nachträglich geändert (TT.MM.)“ an einer Erfassung heißt: nach dem Absenden wurden Antworten geändert –
  die Details (alt → neu) stehen im Notizen-Chat des Vorgangs („Alle Änderungen anzeigen“ bei vielen
  Änderungen). Hängt ein Angebotsentwurf an der Erfassung, erscheint „Antworten geändert. Bitte das Angebot neu
  berechnen.“ – das Angebot wird nicht automatisch neu aufgebaut.
- „Antworten korrigieren“ steht dem Innendienst an allen Erfassungen zur Verfügung (Detailseite,
  Vorgangsakte), bis ein verknüpftes Angebot versandfertig ist; der Freitext-Editor protokolliert Änderungen
  jetzt ebenfalls im Notizen-Chat.
- Neue Spalte „Objekt“ in der Erfassungsliste (Spaltenwähler, Standard sichtbar); die Suche findet auch die
  Objektbezeichnung.

## Leads VOT und Mobil: Kanal-Pfeil, Vergangene Termine, Termin nicht stattgefunden (Phasen 203/204)

**Außendienst:**
- Die untere Leiste hat statt „Kunden“ den Reiter **„Vergangene Termine“** (Uhr-Symbol): alle Vor-Ort-Termine der letzten
  180 Tage, zu denen noch keine Erfassung vorliegt – neueste zuerst, mit Suche nach Name, „Erfassung starten“ und
  „Akte“. Die Kundensuche gibt es weiter über die **Lupe in der Kopfzeile**.
- In „Mein Tag“ steht unter „Heute“ nur noch der heutige Tag; das rote „überfällig“ gibt es nicht mehr – vergangene
  Termine ohne Erfassung sind auf dem neuen Reiter (Hinweis-Link unter „Heute“).
- **„Termin nicht stattgefunden“** (unter „Erfassung starten“ in „Heute“, in „Als Nächstes“ und auf dem Reiter
  „Vergangene Termine“): Grund wählen (Kunde nicht angetroffen · Kunde hat sich anders entschieden · Sonstiges mit
  Text), optional eine Bemerkung (auch diktieren), dann entweder **„Neuen Termin vereinbaren lassen“** – das
  Leadmanagement bekommt ein To-Do und sucht den neuen Termin, der Lead steht wieder auf „Kontaktiert“ – oder **„Kunde
  möchte keinen neuen Termin“** – dann Grund auswählen und „Disqualifizieren“. Der Kunde bekommt dabei keine E-Mail.
  Unentschlossene Kunden: „Neuen Termin vereinbaren lassen“ wählen und das in die Bemerkung schreiben.

**Leadmanagement:**
- Meldet ein Vertriebler „Termin nicht stattgefunden – neuen Termin vereinbaren lassen“, erscheint ein **To-Do „Neuen
  Termin vereinbaren: <Kunde>“** (fällig heute, mit Glocke) beim zugewiesenen Innendienstler des Vorgangs; der Lead steht
  im Hauptboard unter „Kontaktiert“, die Wiedervorlage auf heute, der Grund im Notizen-Chat und am Termin. Ohne
  zugewiesenen Innendienstler geht das To-Do an den nächsten Leadmanager (Hinweis „kein Leadmanager zugewiesen“).
- Vertriebler können Kunden nach einem ausgefallenen Termin direkt **disqualifizieren** (mit Grund) – der Vorgang steht
  dann im Hauptboard unter „Disqualifiziert“ und lässt sich wie bisher zurückholen. Es geht keine Mail an den Kunden.

**Innendienst:**
- Leads VOT: die Kanalspalte zeigt das Kanal-Badge und einen kleinen **Pfeil** – erst der Pfeil öffnet die Auswahl;
  die Wahl wird sofort gespeichert (manuell gesetzt hat Vorrang vor dem monday-Sync, „– (Sync-Automatik)“ hebt das auf).
- Unten in der Tabelle die zugeklappte Gruppe **„Vergangene Termine · n“** (Termine der letzten 180 Tage ohne Erfassung,
  neueste zuerst, „vor n Tagen“); der Klappzustand bleibt je Benutzer gemerkt. Der rote Überfällig-Banner und die
  Ansicht „nur überfällige“ entfallen. Die Zeilenaktion „Termin nicht stattgefunden“ gibt es auch hier.
