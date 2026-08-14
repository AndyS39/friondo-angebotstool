# Fern-Signatur: Anforderung an die IT (Phase 28)

Das Angebotstool kann Kunden per E-Mail einen **Einmal-Link zum
Online-Unterschreiben** schicken (mobile Signaturseite mit PDF-Ansicht).
Damit das funktioniert, muss **genau eine Route** des Tools aus dem Internet
erreichbar sein – der Rest bleibt intern im Firmennetz/Terminal-Server.

## Was benötigt wird

1. **Öffentliche HTTPS-Adresse** (z. B. `https://signatur.friondo.de`) mit
   gültigem Zertifikat (z. B. Let's Encrypt).
2. **Reverse Proxy** (IIS ARR, nginx o. ä.), der ausschließlich Anfragen an
   `/signatur/extern/*` an den internen Server des Angebotstools
   (`http://<interner-host>:8000`) weiterleitet.
   **Alle anderen Pfade dürfen NICHT öffentlich erreichbar sein** – am
   einfachsten per Pfadregel im Proxy (nur `/signatur/extern/` zulassen,
   zusätzlich `/static/` für das Stylesheet der Signaturseite).
3. Die öffentliche Basis-Adresse wird anschließend im Tool unter
   **Parametrierung → Fern-Signatur** eingetragen und der Schalter aktiviert
   (Standard ist AUS).

## Sicherheit

- Der Link enthält ein zufälliges **Einmal-Token** (32 Byte, URL-sicher);
  ohne gültiges Token liefert die Route nur eine neutrale Hinweisseite.
- Das Token **verfällt automatisch** (Gültigkeitsdauer in Tagen in der
  Parametrierung, Standard 14) und wird **direkt nach der Signatur entwertet**.
- Die Route ist rein für die Signatur: kein Login, keine Navigation, keine
  weiteren Daten abrufbar; das Signaturprotokoll (Zeit, IP, Gerät) wird am
  Angebot gespeichert.
- Nach der Signatur erhält der Innendienst-Postfachinhaber automatisch eine
  Info-Mail (über die bestehende Microsoft-Graph-Anmeldung, Berechtigung
  `Mail.Send`; siehe docs/graph-einrichtung.md).

## Alternative: externer Signatur-Anbieter

Wenn keine öffentliche Route bereitgestellt werden soll, kann stattdessen ein
Signatur-Dienst genutzt werden (z. B. DocuSign, Adobe Acrobat Sign, Skribble,
d.velop sign). Ablauf dann: PDF aus dem Tool herunterladen, beim Anbieter
hochladen und den Signatur-Umlauf dort starten; das signierte PDF wird manuell
am Angebot abgelegt. Vorteile: qualifizierte/fortgeschrittene Signaturen und
Beweiskraft nach eIDAS; Nachteile: laufende Kosten je Umschlag und ein
Medienbruch gegenüber der integrierten Lösung.
