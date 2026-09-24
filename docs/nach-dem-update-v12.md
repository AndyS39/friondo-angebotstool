# Nach dem Update: Design-Update (PLAN_V12, intern v14)

**Kurz gesagt: neue Optik, identische Funktionen – alles ist, wo es
war.** Keine Route, kein Formular, keine Berechnung und kein
Angebots-PDF wurde geändert; auch die Rollen/Rechte sind exakt gleich.

## Wichtig nach dem Update

- **Einmal Strg+F5 drücken** (bzw. am Handy die Seite neu laden):
  Das Stylesheet ist neu, der Browser-Cache zeigt sonst noch die alte
  Optik oder eine Mischung aus beidem.

## Was anders aussieht

- **Farben/Badges:** Ein einheitliches Statusfarben-Schema überall –
  Entwurf/Überholt grau, Versand vorbereitet orange, Versendet blau,
  Angenommen grün, Abgelehnt rot, Individuell/TAIFUN violett.
- **Listen:** Suchfeld + Filter als helle Leiste, Tabellen mit
  Zebra-Streifen, Zeilen-Hover und feststehender Kopfzeile; die
  Aktionen rechts sind jetzt kompakte Symbol-Buttons (Maus
  darüberhalten zeigt die Beschriftung). Nebenbei behoben: die
  Aktions-Buttons standen bisher versetzt NEBEN der Tabelle – sie
  sitzen jetzt in der Zeile.
- **Vorgangsakte:** Kundenkopf als Karte (Hot-Ampel + Wiedervorlage
  direkt am Namen, Schnellaktionen rechts), Angebote als Karten mit
  einer kleinen Status-Schrittleiste (Entwurf → … → Angenommen),
  Notizen im Chat-Stil (eigene Einträge rechts, Eingabe klebt unten).
- **Editor:** Oben eine Kopfkarte mit der Schrittleiste, unten eine
  feststehende Leiste mit PDF · Signieren · Überarbeiten · Versand
  vorbereiten – dieselben Knöpfe wie bisher, nur immer erreichbar.
- **Mobile Erfassung:** „Seite 3 von 8" mit Balken, jede Frage eine
  Karte, Weiter/Zurück kleben unten. Die Einschätzung (heiß/warm/kalt)
  sind drei große Buttons. Das Tool lässt sich am Handy „zum
  Startbildschirm hinzufügen" (eigenes Icon, ohne Browserleiste).

## Für Später

- Design-Dokumentation für Anpassungen: `docs/design-system.md`
  (Farben/Abstände nur noch über die dort beschriebenen Tokens).
- Vorher/Nachher-Screenshots der Kernseiten: `docs/design-v12/`.

## Rollout

Wie immer `update.bat` auf dem Terminal-Server (keine Migration
nötig – rein Frontend). Danach im Browser Strg+F5.
