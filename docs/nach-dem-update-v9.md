# Nach dem Update auf v9 – Checkliste & Hinweise

## ✅ Checkliste für den Innendienst (einmalig nach dem Update)

1. **Kanal-Zuordnung prüfen** (für die automatische Profil-Wahl):
   Die Angebotsprofile greifen über den **Vertriebskanal** des Kunden/Leads
   (Teilstring, Groß-/Kleinschreibung egal):
   - Kanalwert enthält **„Enni"** → Enni-Profil
   - Kanalwert enthält **„Sparkasse"** → Sparkasse-DU-Profil
   - **SWD** hat bewusst keinen Kanal-Automatismus – das SWD-Profil wird
     am Angebot **manuell** gewählt (Editor → Zeile „Profil").
   Unter **Parametrierung → Angebotsprofile** die Kanalwerte kontrollieren
   und bei Bedarf an die tatsächlichen monday-Kanalbezeichnungen anpassen.
   In den Listen (Leads/Kunden) lässt sich der Kanal seit v9 auch
   **manuell setzen** (✎ = manuell, Sync überschreibt nicht mehr).

2. **BCC auf Mehrfachadressen umstellen**: Das BCC-Feld in der
   Parametrierung akzeptiert **mehrere Adressen mit Komma**, z. B.
   `info@friondo.de, d.chatzis@friondo.de`. Aktuellen Wert prüfen und
   gewünschte Adressen eintragen.

3. **Nachtext-Blöcke inhaltlich abnehmen**: Unter **Parametrierung →
   Angebotsprofile** liegen die vier Textblöcke (Standard, Enni, SWD,
   Sparkasse DU). Bitte die Texte einmal fachlich gegenlesen – sie wurden
   aus den Word-Vorlagen übernommen (ohne den Vollmacht-Teil, der weiter
   automatisch als Nachtext D angehängt wird, außer bei Enni/SWD).
   Die Blöcke sind direkt im Browser editierbar (Formatierungs-Konventionen
   stehen im Editor).

4. **Pos.-162-Preis kontrollieren**: Der Text der Pos. 162 wurde auf den
   enni.flexstrom-Wortlaut aktualisiert, der **Preis blieb unverändert**.
   Im Artikelstamm prüfen, ob der hinterlegte Preis stimmt (bei 0,00 €
   bitte den gewünschten Preis eintragen).

5. **Enni-Sonderpreis prüfen**: Im Enni-Profil wird Pos. 015 (Friondo
   HEMS) automatisch auf **599,00 €** gesetzt (Sonderpreis-Kennzeichen;
   der Deckungsbeitrag rechnet weiter mit dem echten EK).

## 📣 Hinweise für das Team

### Versionierung: „Überarbeiten" statt Duplizieren

Bei **Änderungswünschen zu einem bereits versendeten Angebot** ab sofort
den neuen Button **„Überarbeiten"** verwenden (nicht mehr Duplizieren):

- Es entsteht eine vollständige Kopie als Entwurf mit Nummer
  **`<Stamm>.2`** (dann .3, .4 …).
- Das Original wechselt auf **„Überholt"** und verschwindet aus der
  Standard-Angebotsliste und der Statistik (kein Doppelzählen mehr).
  Es bleibt über den Status-Filter „Überholt" und die
  **Versions-Historie** im Editor erreichbar.
- Das PDF der neuen Version trägt die Zeile
  **„Ersetzt Angebot `<Nr.>` vom `<Datum>`"**.
- Beim Versand der neuen Version wird der **monday-Deal-Wert
  automatisch** auf die neue Summe aktualisiert.
- **Duplizieren** bleibt für echte Zweitangebote (z. B. Alternativ-Variante)
  erhalten – es zählt dann als eigenes Angebot.

### Solarthermie ist jetzt konfigurierbar

Die frühere AMPEL bei vorhandener Solarthermie (A10) entfällt:

- **„Ja, soll stillgelegt werden"** → automatisch Pos. Z24
  (Rückbau im Heizungsraum, 0,00 €) in Block 5.
- **„Ja, soll übernommen werden"** → AWE-Paket + Pos. 069
  (Einbindung Solarspeicher); die Warmwasser-Frage entfällt, das
  Warmwasser läuft über den bivalenten 390-l-Solarspeicher.
- Widersprüchliche Angaben erzeugen einen **fachlichen Hinweis** am
  Vorgang (⚠ in der Erfassungsliste).

### Weitere Neuerungen in Kürze

- **15-kW-Klasse (Serie CS8800i)**: 31.001–37.000 kWh bzw. Heizlast
  16,0–18,5 kW konfigurieren jetzt automatisch (Farbe Weiß/Schwarz,
  Speichergröße); erst darüber greift die AMPEL.
- **Vor- und Nachtexte** der Angebots-PDFs kommen aus editierbaren
  Textblöcken; der Vortext lässt sich je Angebot übersteuern.
- **MFH-Förderung**: Die PDF-Aufschlüsselung zeigt Klima- und
  Einkommensbonus als getrennte Zeilen (anteilig auf die selbstgenutzte
  WE) – die Rechenlogik ist unverändert.
- **Sparten-Chips** sind farbcodiert (WP terrakotta, PV gold, KL blau,
  WB grün): gefüllt mit Haken = erfasst, umrandet = offen, grau
  durchgestrichen = ausgeblendet. Legende unter den Listen.
- **Freitext-Erfassungen** sind nachträglich editierbar (AD nur eigene);
  Änderungen werden protokolliert, bei laufenden Vorgängen erscheint der
  Hinweis „Freitext geändert".
- **Startseite** in drei Bereichen: Mitte Angebotstool, links
  Lead-Management und rechts Projektierung als „Coming soon"-Platzhalter.
