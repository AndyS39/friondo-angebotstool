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


def rechnung(angebot, kunde) -> dict:
    """Effektive Rechnungsanschrift (Angebot > Kunden-Standard > Kunde)."""
    werte = _feldsatz(angebot, "rechnung")
    standard = _feldsatz(kunde, "rechnung") if kunde is not None else {}
    basis = ausfuehrungsort(kunde)
    if not any(werte.values()) and any(standard.values()):
        werte = standard
    if not _hat_adresse(werte):
        for f in ("strasse", "plz", "ort"):
            werte[f] = basis[f]
    werte["name"] = werte["name"] or basis["name"]
    return werte


def lieferung(angebot, kunde) -> dict:
    """Effektive Lieferanschrift (Angebot > Alt-Text v13 > Kunden-Standard >
    Ausführungsort)."""
    werte = _feldsatz(angebot, "liefer")
    if not any(werte.values()) and (getattr(angebot, "liefer_anschrift", "") or "").strip():
        werte = alt_text_parsen(angebot.liefer_anschrift)
    standard = _feldsatz(kunde, "liefer") if kunde is not None else {}
    if not any(werte.values()) and any(standard.values()):
        werte = standard
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
    if not adr_abw and not name_abweichend(werte, kunde) and not werte.get("zusatz"):
        # Standardfall wie bisher: Firma, Person, Kundenadresse
        person = " ".join(t for t in (kunde.anrede if kunde.anrede != "Firma" else "",
                                      kunde.vorname, kunde.nachname) if t)
        return [t for t in (kunde.firma, person, kunde.strasse,
                            f"{kunde.plz} {kunde.ort}".strip()) if t], False
    return zeilen(werte), adr_abw


def lieferzeile(angebot, kunde) -> str:
    """„Lieferanschrift: …“ nur, wenn sie vom Ausführungsort abweicht."""
    werte = lieferung(angebot, kunde)
    if not adresse_abweichend(werte, kunde) and not name_abweichend(werte, kunde) \
            and not werte.get("zusatz"):
        return ""
    return einzeilig(werte)


def alt_text_parsen(text: str) -> dict:
    """v13-Freitext („Name, Straße 1, 12345 Ort“) → Felder (bestmöglich)."""
    teile = [t.strip() for t in (text or "").split(",") if t.strip()]
    werte = {f: "" for f in FELDER}
    if teile and re.match(r"^\d{5}\s+\S", teile[-1]):
        plz, _, ort = teile.pop().partition(" ")
        werte["plz"], werte["ort"] = plz, ort.strip()
    if teile and re.search(r"\d", teile[-1]):
        werte["strasse"] = teile.pop()
    if teile:
        werte["name"] = teile.pop(0)
    if teile:
        werte["zusatz"] = ", ".join(teile)
    if not any(werte.values()) and text:
        werte["zusatz"] = text.strip()
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


def angebot_vorbelegen(angebot, kunde) -> None:
    """Neues Angebot ohne Erfassungs-Anschriften: Kunden-Standards übernehmen."""
    if kunde is None:
        return
    standard = _feldsatz(kunde, "rechnung")
    eigene = _feldsatz(angebot, "rechnung")
    if not any(eigene.values()):
        if any(standard.values()):
            setzen(angebot, "rechnung", standard)
    elif (standard["zusatz"] and not eigene["zusatz"]
          and _norm(eigene["strasse"]) == _norm(standard["strasse"])):
        angebot.rechnung_zusatz = standard["zusatz"]   # Erfassung kennt keinen Zusatz
    if not any(_feldsatz(angebot, "liefer").values()) and not angebot.liefer_anschrift:
        standard = _feldsatz(kunde, "liefer")
        if any(standard.values()):
            setzen(angebot, "liefer", standard)
