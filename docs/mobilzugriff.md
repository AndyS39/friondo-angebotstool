# Mobilzugriff für den Außendienst – Entscheidungsvorlage (Phase 16)

> **Umgesetzt (Variante A, WireGuard, Stand 06.10.2026).** Der Außendienst
> arbeitet über das bestehende WireGuard-VPN bereits mit dem Tool
> (`http://192.168.35.4:8000/erfassung`, Tunnel einschalten → Link öffnen,
> PIN-Login bleibt die zweite Hürde). Die IT wird nur noch für zusätzliche
> WireGuard-Profile gebraucht, wenn mit den 50 Nutzern neue Geräte dazukommen
> (je Gerät ein Peer mit QR-Code; Sperrprozess bei Geräteverlust: Peer
> entfernen). Variante B (öffentlich über HTTPS) ist nicht vorgesehen. Der in
> `docs/betrieb-it-uebergabe.md` beschriebene Reverse-Proxy mit HTTPS betrifft
> nur die interne Adresse (Firmennetz/VPN), nicht einen öffentlichen Zugang.
> Der Rest dieser Seite ist die ursprüngliche Entscheidungsvorlage (v27,
> PLAN_V17 Phase 127/129).

Die Vertriebler sollen die mobile Erfassung (`/erfassung`) beim Kunden auf dem
Handy nutzen. Der Server steht im Rechenzentrum und ist nur im Firmennetz
erreichbar. Entscheidung: Variante A (siehe oben).

## Variante A – WireGuard-App auf den Vertriebler-Handys (umgesetzt)

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

## Variante B – /erfassung öffentlich über HTTPS + Login (nicht gewählt)

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

## Empfehlung (umgesetzt)

**Variante A.** Sie nutzt vorhandene Infrastruktur, hält das Tool komplett aus
dem Internet heraus und der Mehraufwand pro Gerät ist gering. Variante B nur,
wenn VPN auf den Geräten organisatorisch nicht durchsetzbar ist.
