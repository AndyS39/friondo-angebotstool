# E-Signatur im Angebotstool (Phase 23)

## Was das Tool macht

- **Vor-Ort-Modus (aktiv):** Aus der Angebotsansicht (Innendienst) oder der
  Erfassungs-Übersicht (Außendienst, eigenes Angebot) öffnet „Signieren" eine
  Seite mit Angebots-PDF-Vorschau und Touch-Signaturfeld. Der Kunde
  unterschreibt auf dem Bildschirm; Signaturbild, Name und Zeitstempel werden
  in die Unterschriften-Seite des PDFs eingebettet. Das signierte PDF liegt
  unter `data/angebote/signiert/`, das Angebot wechselt auf **„Angenommen"**,
  und am Angebot wird ein Signaturprotokoll gespeichert (Zeit, Unterzeichner,
  erfassender Benutzer, IP, Gerät).
- **Fern-Modus (vorbereitet, deaktiviert):** Eine Token-Link-Route
  (`/signatur/extern/<token>`) mit Gültigkeitsdauer ist angelegt, liefert aber
  standardmäßig nur einen Hinweis. Aktivierung über `SIGNATUR_FERN_AKTIV=ja`
  in der `.env` – **erst sinnvoll, wenn** der öffentliche HTTPS-Zugang
  (PLAN_V2 Phase 16, Variante B) umgesetzt ist oder ein externer
  Signatur-Anbieter gewählt wurde.

## Rechtlicher Hinweis

Die hier umgesetzte Signatur ist eine **einfache elektronische Signatur**
im Sinne der eIDAS-Verordnung (Signaturbild + Metadaten, keine qualifizierte
Zertifikats-Signatur). Für Wärmepumpen-Angebote ist das üblicherweise
ausreichend, da kein gesetzliches Schriftformerfordernis besteht; die
Beweiskraft ist jedoch geringer als bei fortgeschrittenen/qualifizierten
Signaturen. **Rechtliche Feinheiten (z. B. Beweiswert, Widerrufsbelehrung im
Haustürgeschäft, Aufbewahrung) bei Bedarf mit einer Rechtsberatung klären.**
