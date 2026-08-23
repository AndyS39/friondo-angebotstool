# Übergabe v6 – Stand 23.08.2026

Übergabe für den Planungs-Chat. v6 umfasst die Phasen 37–43
(PLAN_V6.md); Basis war der v5-Stand mit Nachträgen (Commit 5e3ba88).

## 1. Funktionale Zusammenfassung (Nutzersicht)

- **Lead-Zuordnungs-Bugfix:** Die Personen-Zuordnung (monday-Person →
  Tool-Benutzer) wirkt jetzt sofort rückwirkend auf alle bestehenden Leads
  (vorher erst beim nächsten Sync). Zusätzlich automatisches Matching über
  die Benutzer-E-Mail, wenn monday eine E-Mail-Adresse als Person liefert.
  Gelber Warnhinweis in der Leadliste, solange Leads ohne Vertriebler sind.
- **Vertriebskanal aus monday:** je Board über das Spalten-Mapping gelesen,
  gespeichert an Lead und Kunde. Eigene Spalte „Kanal" + Filter in Lead-
  und Angebotsliste, Auswertung „Je Kanal" in der Statistik.
- **Erfassungen archivierbar**; neuer Status **„Individuell"** für
  Erfassungen und Angebote (Vorgang wird außerhalb des Tools geschrieben)
  – archiviert beim Setzen automatisch.
- **Versendete Angebote** sind für Innendienst und Admin änderbar und (mit
  Sicherheitsabfrage) löschbar. Jede Löschung jenseits von „Entwurf" landet
  im **Lösch-Protokoll** (Parametrierung); Angebotsnummern werden nie neu
  vergeben (Zähler berücksichtigt auch gelöschte Nummern).
- **Angebotsliste:** Vertriebler-Spalte (durch ID/Admin änderbar, seit
  v5-Nachtrag) + **Summenzeile** Netto / Endbetrag (brutto) / DB über die
  jeweils gefilterte Liste.
- **Angebots-Editor:** Artikeltexte (Bezeichnung + Beschreibung) je Position
  direkt im Angebot editierbar (Katalog bleibt unberührt); lange
  Beschreibungen aufklappbar statt mit „…" abgeschnitten; **EP-Kästchen**
  je Position (wie „bauseits"); **Förderung**: KfW-Zuschuss manuell
  überschreibbar (Kennzeichen „manuell festgelegt" im PDF) oder Förderblock
  komplett im PDF ausblendbar.
- **Angebotsverfolgung:** Block „Verfolgung" im Editor mit Hot-Ampel
  (🔥 heiß / 🌤 warm / ❄ kalt), Wiedervorlage-Datum und Notizen-Verlauf
  (nur anhängen). Ampel + Wiedervorlage (rot wenn fällig) in der
  Angebotsliste inkl. Filter; Startseiten-Kachel „fällige Wiedervorlagen".
- **Statistik-Seite** (neuer Menüpunkt): Zeitraum Woche/Monat/Quartal/Jahr/
  frei; Leads, Erfassungen, versendete/angenommene/abgelehnte Angebote,
  Auftragswert, DB, Abschlussquote – gesamt, je Vertriebler, je Kanal.
  Außendienst sieht unter „Meine Statistik" nur die eigenen Zahlen (ohne DB).
- **E-Mail-Versand als HTML:** Vorlagen-Editor mit Formatierung
  (fett/kursiv/Listen/Links, ohne externe Bibliotheken); je
  Innendienst-Benutzer die **echte Outlook-Signatur** inkl. Bildern
  (Upload .htm + Bilder unter Parametrierung → Signaturen, Bilder gehen als
  Inline-Anhänge/cid mit dem Graph-Entwurf raus). Ohne Upload greift eine
  einfache Standard-Signatur.

## 2. Git-Log seit v5-Stand (5e3ba88)

```
fa5dadf PLAN_V6 + CLAUDE.md v6: Umfang abgestimmt
f4c45af Phase 37: Lead-Zuordnungs-Bugfix und Vertriebskanal
26ec3a3 Phase 38: Erfassungs-Archiv, Status Individuell, Summenzeile Angebotsliste
fd0df0a Phase 39: Editor-Texte, EP-Kaestchen, Foerder-Override, Loeschen mit Protokoll
94eac7a Phase 40: Angebotsverfolgung - Hot-Ampel, Wiedervorlage, Notizen
689f90c Phase 41: Statistik-Seite mit Zeitraum, je Vertriebler und je Kanal
2727233 Phase 42: HTML-Mail, Formatierungs-Editor und Outlook-Signaturen
2f931f8 Phase 43: Migration verifiziert, Abnahme auf 52 Punkte erweitert (v6), Nach-Update-Anleitung
9df6644 v6-Nachtrag: Vertriebskanal als eigene Spalte in Lead- und Angebotsliste
```

## 3. Geänderte/neue Dateien

40 Dateien, +1.630/−84 Zeilen. Zu den ausdrücklich gefragten:

- **CLAUDE.md: ja, geändert** – Kopf jetzt „Projektkontext (v6)", neuer
  Abschnitt „Neu in v6 (abgestimmt 21.08.2026)" mit allen oben genannten
  Funktionen. Regeln/Arbeitsweise unverändert.
- **PLAN-Dateien:** **PLAN_V6.md neu** (Phasen 37–43, alle Kästchen
  abgehakt bis auf „Rollout am Server über update.bat"). Ältere PLAN-Dateien
  unverändert.
- **konfigurator_logik_v5.xlsx: NICHT verändert** – in v6 wurde keine
  einzige .xlsx angefasst, es gibt auch keine neue Logik-Datei.
  konfigurator_logik_v5.xlsx bleibt führend.
- **Blatt „Anhänge": nicht in v6 geändert.** Die Regel „Bosch CS3800iAW.pdf
  bei WP-Paket Pos. 045–054" (Gerätebroschüre) stammt aus dem
  v5-Nachtrag-Commit 578276a (20.08., „Bosch-Beileger"). In v6 wurden nur
  die veralteten Erwartungen im Abnahmeskript daran angepasst.
- **migrate.py: ja, erweitert** (idempotent, gegen DB-Kopie verifiziert):
  ① Schema-Nachzüge (neue Spalten/Tabellen, siehe Punkt 4)
  ② Bestandsleads ohne Vertriebler erneut zuordnen (Personen-Zuordnung +
  E-Mail-Matching; manuell zugeordnete Leads bleiben unangetastet)
  ③ Statistik-Zeitstempel für Bestandsangebote als Näherung nachtragen
  (Angebotsdatum als Statuszeitpunkt) ④ Lead.angelegt_am = aktualisiert_am.

Neue Dateien: app/signaturen.py, app/routers/statistik.py,
app/templates/statistik.html, app/templates/konfiguration/signaturen.html,
docs/signaturen.md, docs/nach-dem-update-v6.md, docs/uebergabe-v6.md,
tests/test_signaturen.py, PLAN_V6.md.

Größere Änderungen: app/routers/angebote.py (Verfolgung, Förder-Override,
Positionstexte, Löschen mit Protokoll, Summenzeile), app/routers/
konfiguration.py (Signaturen, Lösch-Protokoll, rückwirkende Zuordnung),
app/mail_vorlagen.py + app/graph_versand.py (HTML-Mail, Inline-Bilder),
app/monday_sync.py (E-Mail-Matching, Vertriebskanal, zuordnung_anwenden),
app/kfw.py (ergebnis_mit_override), app/angebot_aufbau.py (Nummernsperre),
Templates editor/liste/leads/vorlagen, tests/abnahme.py (v6-Block +
Selbstreinigung am Start).

## 4. Datenbank-Änderungen

Neue Spalten (per migrate.py / db._NACHTRAEGLICHE_SPALTEN, alle nullable
bzw. mit Default – bestandsverträglich):

- **angebote:** foerderung_manuell_cent, foerderung_ausblenden,
  verfolgung_ampel, wiedervorlage_am, versendet_am, angenommen_am,
  abgelehnt_am (+ vertriebler_id aus dem v5-Nachtrag)
- **leads:** vertriebskanal, angelegt_am
- **kunden:** vertriebskanal
- **erfassungen:** archiviert

Neue Tabellen:

- **angebots_notizen** (AngebotsNotiz): angebot_id, benutzer_name, text,
  angelegt_am – Verfolgungs-Notizen, nur anhängen.
- **angebots_loeschungen** (AngebotsLoeschung): nummer, kunde_name,
  status_vorher, endbetrag_cent, benutzer_name, geloescht_am –
  Lösch-Protokoll; wird auch vom Nummern-Zähler mitgelesen.

Zentraler Status-Setter `angebot_status_setzen()` stempelt
versendet_am/angenommen_am/abgelehnt_am beim ersten Erreichen des Status.

## 5. Offene Punkte / bekannte Baustellen

- **Personen-Zuordnung unvollständig:** Für **P. Diblasi** existiert kein
  Tool-Benutzer (anlegen + zuordnen); **Ioannis Simeonidis** ungeklärt.
  Benutzer-E-Mails der ADs pflegen, damit das E-Mail-Matching greift.
- **Vertriebskanal-Spalte je Board mappen** (Parametrierung →
  monday-Anbindung; Deals-Board: Spalte „Vertriebskanal", ID color_mkyp1qm6)
  – vorher bleibt die Kanal-Spalte überall „–".
- **Signaturen hochladen** je ID-Mitarbeiter (docs/signaturen.md).
- **Offen aus v5:** MONDAY_API_TOKEN in der Server-.env; M365-Admin:
  „Senden als" für angebot@friondo.de + Graph-Berechtigungen inkl. *.Shared
  mit Admin-Zustimmung (docs/graph-einrichtung.md, Abschnitt 3/3a).
- **Statistik-Näherung:** Für Bestandsangebote wurden die Statuszeitpunkte
  aus dem Angebotsdatum genähert (Fußnote auf der Statistik-Seite).
  Exakt sind erst die ab v6 gestempelten Zeitpunkte.
- Alles Weitere ist in docs/nach-dem-update-v6.md als Checkliste erfasst.

## 6. Status

- **Lokal (PC):** fertig – 52/52 Abnahmepunkte, 83/83 Unit-Tests grün,
  Migration zweimal idempotent gegen eine Kopie der echten DB verifiziert
  (17 Angebote unangetastet).
- **GitHub:** alle v6-Commits gepusht (master, bis 9df6644).
- **Terminal Server: v6 ist NOCH NICHT ausgerollt** – auf dem Server läuft
  weiterhin v5. Rollout: einmal `update.bat` in C:\Friondo\Angebotstool
  ausführen, danach Checkliste docs/nach-dem-update-v6.md abarbeiten.
