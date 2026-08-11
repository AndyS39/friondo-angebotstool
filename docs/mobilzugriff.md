# Mobilzugriff für den Außendienst – Entscheidungsvorlage (Phase 16)

Die Vertriebler sollen die mobile Erfassung (`/erfassung`) beim Kunden auf dem
Handy nutzen. Der Server steht im Rechenzentrum und ist nur im Firmennetz
erreichbar. **Die Entscheidung zwischen den Varianten ist offen – bitte mit
der IT/dem Rechenzentrum abstimmen. Umsetzung erst nach Entscheidung.**

## Variante A – WireGuard-App auf den Vertriebler-Handys (empfohlen)

Das bestehende WireGuard-VPN wird genutzt: Jedes Außendienst-Handy erhält ein
eigenes WireGuard-Profil; die App baut den Tunnel ins Firmennetz auf, danach
funktioniert `http://<SERVERNAME>:8000/erfassung` wie im Büro.

**Vorteile**
- Kein öffentlich erreichbarer Dienst, keine neue Angriffsfläche
- Kein Zertifikat, keine Domain, kein Reverse Proxy nötig
- Bestehende WireGuard-Infrastruktur wird weiterverwendet
- PIN-Login der App bleibt als zweite Hürde bestehen

**Aufwand**
- Je Handy ein WireGuard-Peer (Schlüsselpaar + Konfig-QR-Code) durch die IT
- WireGuard-App aus dem App-Store, Profil per QR-Code einlesen
- Kurze Anleitung für die Vertriebler („Tunnel einschalten, Link öffnen")

**Offene Punkte für die IT**
- IP-Bereich/Routing für mobile Peers, ggf. Split-Tunnel nur fürs Firmennetz
- Sperrprozess bei Geräteverlust (Peer entfernen)

## Variante B – /erfassung öffentlich über HTTPS + Login

Die App (oder nur der Pfad `/erfassung`) wird über einen Reverse Proxy
(z. B. Caddy oder nginx) öffentlich erreichbar gemacht: eigene Domain,
TLS-Zertifikat (Let's Encrypt), Weiterleitung auf den internen Port 8000.

**Vorteile**
- Kein VPN auf den Handys, Zugriff aus jedem Netz
- Einfachste Bedienung für die Vertriebler (nur ein Link)

**Aufwand / Risiken**
- Domain + Zertifikat + Reverse Proxy durch RZ/IT einrichten und betreiben
- Öffentlich erreichbarer Login: PIN-Schutz allein ist knapp – zusätzlich
  nötig: Ratenbegrenzung/Fail2ban, lange PINs oder zweiter Faktor,
  idealerweise Pfad-Beschränkung rein auf `/erfassung` und `/login`
- Öffentliche Angriffsfläche muss laufend gepatcht/überwacht werden

## Empfehlung

**Variante A.** Sie nutzt vorhandene Infrastruktur, hält das Tool komplett aus
dem Internet heraus und der Mehraufwand pro Gerät ist gering. Variante B nur,
wenn VPN auf den Geräten organisatorisch nicht durchsetzbar ist.
