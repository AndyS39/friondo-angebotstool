# Anschriften (v20, PLAN_GESAMT B4 / Phase 98): Rechnungs- und
# Lieferanschrift je Angebot (Name/Firma, Zusatz, Straße + Nr., PLZ, Ort) mit
# Standardwerten am Kunden. Ausführungsort = Kundenadresse (monday, v8).
#
# Vorbelegung: Rechnung aus Erfassung (O06/O09–O12) bzw. Kunden-Standard,
# sonst Kundenname + Ausführungsort; Lieferung = Kunden-Standard, sonst
# Ausführungsort. Im PDF zählt nur, was vom Ausführungsort/Kundennamen
# ABWEICHT – gleichlautende Werte ändern die Darstellung nicht.

import re

FELDER = ("name", "zusatz", "strasse", "plz", "ort")
LAENGEN = {"name": 200, "zusatz": 200, "strasse": 200, "plz": 10, "ort": 100}


def _norm(text: str) -> str:
    return re.sub(r"[\s.,-]+", "", (text or "").lower()).replace("straße", "str") \
        .replace("strasse", "str")


def kundenname(kunde) -> str:
    if kunde is None:
        return ""
    if kunde.firma:
        return kunde.firma
    person = " ".join(t for t in (kunde.anrede if kunde.anrede not in ("Firma", "") else "",
                                  kunde.vorname, kunde.nachname) if t)
    return person


def ausfuehrungsort(kunde) -> dict:
    return {"name": kundenname(kunde), "zusatz": "",
            "strasse": kunde.strasse if kunde else "", "plz": kunde.plz if kunde else "",
            "ort": kunde.ort if kunde else ""}


def _feldsatz(obj, praefix: str) -> dict:
    return {f: (getattr(obj, f"{praefix}_{f}", "") or "").strip() for f in FELDER}


def _hat_adresse(werte: dict) -> bool:
    return bool(werte.get("strasse") or werte.get("ort"))


def _auffuellen(werte: dict, kunde) -> dict:
    basis = ausfuehrungsort(kunde)
    if not _hat_adresse(werte):
        for f in ("strasse", "plz", "ort"):
            werte[f] = basis[f]
    werte["name"] = werte["name"] or basis["name"]
    return werte


def standard_rechnung(kunde) -> dict:
    """Standard-Rechnungsanschrift des Kunden (für die Pflege in der Akte)."""
    return _auffuellen(_feldsatz(kunde, "rechnung"), kunde)


def standard_lieferung(kunde) -> dict:
    return _auffuellen(_feldsatz(kunde, "liefer"), kunde)


def rechnung(angebot, kunde) -> dict:
    """Effektive Rechnungsanschrift: Felder des Angebots, sonst Kundenname +
    Ausführungsort. Bugfix 30.09.2026: KEIN Rückgriff auf den Kunden-Standard
    zur Anzeigezeit – der Standard wird nur beim Anlegen kopiert
    (angebot_vorbelegen); sonst änderte ein später gepflegter Standard bereits
    versendete/angenommene Angebote (PDF, Lieferschein)."""
    werte = _feldsatz(angebot, "rechnung")
    basis = ausfuehrungsort(kunde)
    if not _hat_adresse(werte):
        for f in ("strasse", "plz", "ort"):
            werte[f] = basis[f]
    werte["name"] = werte["name"] or basis["name"]
    return werte


def lieferung(angebot, kunde) -> dict:
    """Effektive Lieferanschrift (Angebot > Alt-Text v13 > Ausführungsort);
    wie bei rechnung() kein Rückgriff auf den Kunden-Standard zur Anzeigezeit."""
    werte = _feldsatz(angebot, "liefer")
    if not any(werte.values()) and (getattr(angebot, "liefer_anschrift", "") or "").strip():
        werte = alt_text_parsen(angebot.liefer_anschrift)
    basis = ausfuehrungsort(kunde)
    if not _hat_adresse(werte):
        for f in ("strasse", "plz", "ort"):
            werte[f] = basis[f]
    werte["name"] = werte["name"] or basis["name"]
    return werte


def adresse_abweichend(werte: dict, kunde) -> bool:
    basis = ausfuehrungsort(kunde)
    return any(_norm(werte.get(f, "")) != _norm(basis[f]) for f in ("strasse", "plz", "ort"))


def name_abweichend(werte: dict, kunde) -> bool:
    return bool(werte.get("name")) and _norm(werte["name"]) != _norm(kundenname(kunde))


def zeilen(werte: dict) -> list[str]:
    return [t for t in (werte.get("name"), werte.get("zusatz"), werte.get("strasse"),
                        f"{werte.get('plz', '')} {werte.get('ort', '')}".strip()) if t]


def einzeilig(werte: dict) -> str:
    return ", ".join(zeilen(werte))


def empfaenger(angebot, kunde) -> tuple[list[str], bool]:
    """Empfängerblock des Angebots-PDFs + „Ausführungsort ausweisen?“.
    Rechnungs-Name ersetzt bei Abweichung den Kundennamen; bei abweichender
    Rechnungsadresse steht der Ausführungsort als eigene Zeile darunter."""
    werte = rechnung(angebot, kunde)
    adr_abw = adresse_abweichend(werte, kunde)
    if not adr_abw and not name_abweichend(werte, kunde):
        # Standardfall wie bisher: Firma, Person, Kundenadresse – ein Zusatz
        # allein ergänzt nur eine Zeile (der Ansprechpartner bleibt stehen)
        person = " ".join(t for t in (kunde.anrede if kunde.anrede != "Firma" else "",
                                      kunde.vorname, kunde.nachname) if t)
        return [t for t in (kunde.firma, person, werte.get("zusatz"), kunde.strasse,
                            f"{kunde.plz} {kunde.ort}".strip()) if t], False
    return zeilen(werte), adr_abw


def lieferzeile(angebot, kunde) -> str:
    """„Lieferanschrift: …“ nur, wenn sie vom Ausführungsort abweicht."""
    werte = lieferung(angebot, kunde)
    if not adresse_abweichend(werte, kunde) and not name_abweichend(werte, kunde) \
            and not werte.get("zusatz"):
        return ""
    return einzeilig(werte)


_PLZ_ORT = re.compile(r"^(?P<vor>.*?)[,\s]*(?:D[-\s])?(?P<plz>\d{5})\s+(?P<ort>[^,]+?)\s*(?:,\s*(?P<nach>.*))?$")


def alt_text_parsen(text: str) -> dict:
    """Freitext-Lieferanschrift (Erfassung O13, v13) → Felder. Strukturiert
    wird nur, was sicher erkennbar ist: „[Name, [Zusatz,]] Straße Nr[,]
    PLZ Ort[, Zusatz]“ – auch mit „D-“ vor der PLZ und ohne Komma vor der
    PLZ. Alles andere (Hinweise wie „beim Nachbarn abgeben“) landet
    unverändert im Zusatz: Name und Adresse bleiben dann die des Kunden
    (Bugfix 30.09.2026: vorher wurde der erste Teil immer zum Empfängernamen)."""
    roh = " ".join((text or "").split())
    werte = {f: "" for f in FELDER}
    if not roh:
        return werte
    m = _PLZ_ORT.match(roh)
    vor = [t.strip() for t in (m.group("vor") if m else "").split(",") if t.strip()]
    if not m or not vor:
        werte["zusatz"] = roh
        return {f: werte[f][:LAENGEN[f]] for f in FELDER}
    werte["plz"], werte["ort"] = m.group("plz"), m.group("ort").strip()
    werte["strasse"] = vor.pop()
    if vor:
        werte["name"] = vor.pop(0)
    zusatz = vor + ([m.group("nach").strip()] if (m.group("nach") or "").strip() else [])
    werte["zusatz"] = ", ".join(zusatz)
    return {f: werte[f][:LAENGEN[f]] for f in FELDER}


def erfassung_vorbelegung(kunde) -> dict:
    """Antworten für einen neuen WP-Bogen aus den Kunden-Standards:
    O06 = Nein + O09–O12 (Rechnung), O13 (Lieferung, einzeilig)."""
    if kunde is None:
        return {}
    antworten = {}
    re_ = _feldsatz(kunde, "rechnung")
    if any(re_.values()):
        antworten.update({"O06": "Nein", "O09": re_["name"], "O10": re_["strasse"],
                          "O11": re_["plz"], "O12": re_["ort"]})
    li = _feldsatz(kunde, "liefer")
    if any(li.values()):
        antworten["O13"] = einzeilig(li)[:300]
    return antworten


def aus_formular(form, praefix: str) -> dict:
    return {f: (form.get(f"{praefix}_{f}") or "").strip()[:LAENGEN[f]] for f in FELDER}


def setzen(obj, praefix: str, werte: dict) -> None:
    for f in FELDER:
        setattr(obj, f"{praefix}_{f}", (werte.get(f) or "")[:LAENGEN[f]])


def angebot_vorbelegen(angebot, kunde, antworten: dict | None = None) -> None:
    """Kunden-Standards in ein NEUES Angebot kopieren. Bei Angeboten aus einer
    Erfassung gewinnt die Erfassung: hat der Bogen O06 beantwortet (auch
    „Ja“ = identisch), greift der Rechnungs-Standard nicht; ist O13 im Bogen
    vorhanden (auch leer), greift der Liefer-Standard nicht (Bugfix
    30.09.2026). Bögen ohne diese Fragen (PV/KL) und manuelle Angebote
    übernehmen die Standards."""
    if kunde is None:
        return
    antworten = antworten or {}
    standard = _feldsatz(kunde, "rechnung")
    eigene = _feldsatz(angebot, "rechnung")
    if "O06" not in antworten:
        if not any(eigene.values()) and any(standard.values()):
            setzen(angebot, "rechnung", standard)
    elif (standard["zusatz"] and not eigene["zusatz"] and eigene["strasse"]
          and _norm(eigene["strasse"]) == _norm(standard["strasse"])):
        angebot.rechnung_zusatz = standard["zusatz"]   # der Bogen kennt keinen Zusatz
    standard = _feldsatz(kunde, "liefer")
    if "O13" not in antworten:
        if not any(_feldsatz(angebot, "liefer").values()) and not angebot.liefer_anschrift \
                and any(standard.values()):
            setzen(angebot, "liefer", standard)
    elif any(standard.values()) and _norm(str(antworten.get("O13") or "")) == _norm(einzeilig(standard)):
        setzen(angebot, "liefer", standard)   # unveränderte Vorbelegung: exakt übernehmen
