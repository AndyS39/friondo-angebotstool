# v34 (PLAN_V21 Phase 180, Agent E): „Elektroarbeiten ins PV-Angebot (0 % USt)“ und das
# Alternativ-Kennzeichen „in anderem Angebot enthalten“ (v10).
#
# Reine Funktionen auf der Session – keine Routen, kein Netz, kein Commit (der Aufrufer
# committet im _speichern-Muster aus routers/angebote.py):
#   ziel_parsen(alternativ_zu)            → (Sparte, Angebotsnummer) aus dem v10-Verknüpfungstext
#   alternativ_label(sparte)              → „im PV-Angebot“ / „in anderem Angebot“ (Editor)
#   pdf_label(sparte)                     → „im PV-Angebot“ / „anderes Angebot“ (G-Preis-Spalte im PDF)
#   hinweis_text(sparte, nummer)          → Text des farbigen Hinweiskastens im PDF
#   geschwister_map(session, angebot)     → Nummer → Angebot (alle übrigen Angebote des Vorgangs)
#   alternativ_info(session, angebot)     → je Position: Label, Nummer, Ziel-ID, gültig?
#   pv_ziel(session, angebot)             → PV-Angebot des Vorgangs (Entwurf/Versand vorbereitet)
#   elektro_positionen(session, angebot)  → Positionen des Blocks „Elektroarbeiten“ + Liste
#                                           „gewerkeübergreifende Artikel“ (ohne EP/bauseits/Alternativ)
#   uebernehmen(session, angebot, pv, benutzer) → (anzahl, netto_cent, ersparnis_cent, meldung)
#   rueckholbar(session, angebot)         → (ok, grund)
#   zurueckholen(session, angebot, benutzer) → (anzahl, meldung)
#
# Fachlich (Plan Phase 180): Die Elektro-Positionen des Ursprungsangebots (WP Block 7
# „Elektroarbeiten“, KL Block 2 „Elektro“, WB WB003/WB005/WB006) werden im Ursprungsangebot
# Alternativ „im PV-Angebot enthalten“ (bestehendes Kennzeichen + Vermerk aus v10) und im
# PV-Angebot als voll berechnete Kopien (gleicher Artikel, Netto-Einzelpreis, Menge, Langtext,
# ek_cent) in einer eigenen Gruppe „Elektroarbeiten <Sparte> (aus Angebot AN-C-…)“ am Ende
# eingefügt; 0 % USt gilt automatisch über den Steuersatz des PV-Angebots. Die Kopien tragen
# uebernommen_von_angebot_id/-position_id (additive Spalten) – darüber läuft das Zurückholen.
# Dubletten (Entscheidung Orchestrator 15.10.2026): hat das PV-Angebot bereits eine aktive Position
# mit derselben Artikelnummer oder derselben normalisierten Bezeichnung (z. B. PV123 = WP-Pos. 104
# „Zähler-Komplettschrank“), wird die Ursprungsposition Alternativ, aber NICHT kopiert.
# Steuerliche Zulässigkeit ist Entscheidung von Friondo/Steuerberatung – das Tool setzt nur um.
from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models import Angebot, AngebotsPosition

# Sparten, deren Angebote den Knopf „Elektroarbeiten ins PV-Angebot“ zeigen
ELEKTRO_SPARTEN = ("WP", "KL", "WB")
# Status, in denen Ursprungs- und PV-Angebot für Übernahme/Zurückholen bearbeitbar sind
EDITIERBARE_STATUS = ("Entwurf", "Versand vorbereitet")
# Status, in denen ein Geschwister-Angebot als Verknüpfungsziel „nicht mehr gültig“ ist
UNGUELTIGE_STATUS = ("Überholt", "Abgelehnt")
# Elektro-Positionen je Sparte: WP Block 7 „Elektroarbeiten“ (Blatt Angebotsaufbau),
# KL Block 2 „Elektro“ (Blatt Angebotsaufbau KL), WB feste Artikelnummern (Phase 179)
WP_ELEKTRO_BLOCK = 7
KL_ELEKTRO_BLOCK = 2
WB_ELEKTRO_ARTIKEL = ("WB003", "WB005", "WB006")
HERKUNFT_NOTIZ = "Elektro ins PV"           # Kennzeichen der System-Notiz im Vorgangs-Chat
VERMERK_MUSTER = "Enthält die Elektroarbeiten aus Angebot {nummer} ({sparte})."
PDF_LABEL_GENERISCH = "anderes Angebot"     # G-Preis-Spalte ohne erkennbare Sparte (kleinere Schrift)
TITEL_ZEICHEN = 30                           # Dubletten-Vergleich: erste 30 Zeichen der Bezeichnung

_ZIEL = re.compile(r"^\s*(?P<sparte>[A-Z]{2,3})-Angebot(?:\s+(?P<nummer>AN-[A-Z]-\S+))?\s*$")


# --- Alternativ-Verknüpfung (v10-Text „<Sparte>-Angebot <Nummer>“) ------------------------

def ziel_parsen(alternativ_zu: str | None) -> tuple[str, str]:
    """Sparte und Angebotsnummer aus dem v10-Verknüpfungstext der Alternativ-Position:
    „PV-Angebot AN-C-261021“ → („PV“, „AN-C-261021“); „PV-Angebot“ (Z26) → („PV“, „“);
    Freitext/„Parallel-Angebot“/leer → („“, „“)."""
    m = _ZIEL.match(alternativ_zu or "")
    if not m:
        return "", ""
    return m.group("sparte"), (m.group("nummer") or "")


def alternativ_label(sparte: str) -> str:
    """Badge im Editor: „im PV-Angebot“ (bzw. WP/KL/WB …), ohne erkennbare Sparte generisch
    „in anderem Angebot“."""
    return f"im {sparte}-Angebot" if sparte else "in anderem Angebot"


def pdf_label(sparte: str) -> str:
    """G-Preis-Spalte im PDF: „im PV-Angebot“; ohne erkennbare Sparte „anderes Angebot“
    (Entscheidung 15.10.2026 – statt „Altern.“; passt in kleinerer Schrift in die 20-mm-Spalte)."""
    return f"im {sparte}-Angebot" if sparte else PDF_LABEL_GENERISCH


def hinweis_text(sparte: str, nummer: str) -> str:
    """Text des farbig hinterlegten Hinweiskastens vor der ersten Alternativ-Position
    eines Blocks (Plan Phase 180, wörtlich); ohne Nummer generisch."""
    if nummer:
        return (f"Die folgenden Positionen sind bereits in Ihrem Angebot {nummer}"
                f"{' (' + sparte + ')' if sparte else ''} enthalten und werden dort berechnet.")
    if sparte:
        return (f"Die folgenden Positionen sind bereits in Ihrem {sparte}-Angebot enthalten "
                "und werden dort berechnet.")
    return ("Die folgenden Positionen sind bereits in einem anderen Angebot zu diesem Vorgang "
            "enthalten und werden dort berechnet.")


def geschwister_map(session: Session, angebot: Angebot) -> dict[str, Angebot]:
    """Angebotsnummer → Angebot aller übrigen Angebote des Vorgangs (auch überholte/
    abgelehnte – die Gültigkeit entscheidet alternativ_info)."""
    if not angebot.vorgang_id:
        return {}
    return {a.nummer: a for a in session.query(Angebot)
            .filter(Angebot.vorgang_id == angebot.vorgang_id, Angebot.id != angebot.id)}


def alternativ_info(session: Session, angebot: Angebot) -> dict[int, dict]:
    """Je Alternativ-Position (Positions-ID → dict): label („im PV-Angebot“), sparte,
    nummer, ziel_id (Geschwister-Angebot im Vorgang, sonst None), gueltig (Ziel vorhanden
    und nicht überholt/abgelehnt; ohne Nummer gilt die Verknüpfung als gültig = Freitext)."""
    geschwister = geschwister_map(session, angebot)
    info: dict[int, dict] = {}
    for p in angebot.positionen:
        if not p.alternativ:
            continue
        sparte, nummer = ziel_parsen(p.alternativ_zu)
        ziel = geschwister.get(nummer) if nummer else None
        if ziel is not None and not sparte:
            sparte = ziel.konfigurator_typ or "WP"
        gueltig = (not nummer) or (ziel is not None and ziel.status not in UNGUELTIGE_STATUS)
        info[p.id] = {"label": alternativ_label(sparte), "sparte": sparte, "nummer": nummer,
                      "ziel_id": ziel.id if ziel is not None else None,
                      "ziel_status": ziel.status if ziel is not None else "",
                      "gueltig": gueltig,
                      "text": p.alternativ_zu or "Parallel-Angebot"}
    return info


def ungueltige_verknuepfungen(session: Session, angebot: Angebot) -> list[AngebotsPosition]:
    """Alternativ-Positionen, deren Geschwister-Angebot gelöscht, überholt oder abgelehnt ist
    (Hinweis „Geschwister-Angebot nicht mehr gültig“ im Editor)."""
    info = alternativ_info(session, angebot)
    return [p for p in angebot.positionen if p.alternativ and not info[p.id]["gueltig"]]


# --- PV-Ziel und Elektro-Positionen ------------------------------------------------------

def pv_ziel(session: Session, angebot: Angebot) -> Angebot | None:
    """PV-Angebot des Vorgangs (konfigurator_typ PV, Tool-Angebot, Status Entwurf oder
    Versand vorbereitet, nicht überholt); bei mehreren das jüngste [ANNAHME]."""
    if not angebot.vorgang_id or angebot.extern:
        return None
    kandidaten = (session.query(Angebot)
                  .filter(Angebot.vorgang_id == angebot.vorgang_id,
                          Angebot.id != angebot.id,
                          Angebot.konfigurator_typ == "PV",
                          Angebot.extern.is_(False),
                          Angebot.status.in_(EDITIERBARE_STATUS))
                  .order_by(Angebot.id.desc()).all())
    return kandidaten[0] if kandidaten else None


def knopf_sichtbar(session: Session, angebot: Angebot) -> Angebot | None:
    """Der Knopf „Elektroarbeiten ins PV-Angebot“ erscheint im Editor eines WP-/KL-/WB-
    Entwurfs, wenn der Vorgang ein passendes PV-Angebot hat – liefert dieses PV-Angebot."""
    if angebot.extern or angebot.status != "Entwurf":
        return None
    if (angebot.konfigurator_typ or "WP") not in ELEKTRO_SPARTEN:
        return None
    return pv_ziel(session, angebot)


def _gewerke_liste(session: Session) -> set[str]:
    from app import kombi_versand
    return set(kombi_versand.gewerke_artikel(session))


def ist_elektro_position(position: AngebotsPosition, sparte: str, gewerke: set[str]) -> bool:
    """Zugehörigkeit zum Block „Elektroarbeiten“ (ohne Prüfung von EP/bauseits/Alternativ):
    WP Block 7 bzw. Gruppenüberschrift „Elektroarbeiten…“, KL Block 2, WB feste Artikel;
    dazu jede Position aus der Parametrierungsliste „gewerkeübergreifende Artikel“ (v10)."""
    pos_nr = (position.pos_nr or "").strip()
    if pos_nr and pos_nr in gewerke:
        return True
    if sparte == "WP":
        return (position.block_nr == WP_ELEKTRO_BLOCK
                or (position.gruppe or "").strip().lower().startswith("elektroarbeiten"))
    if sparte == "KL":
        return position.block_nr == KL_ELEKTRO_BLOCK
    if sparte == "WB":
        return pos_nr in WB_ELEKTRO_ARTIKEL
    return False


def elektro_positionen(session: Session, angebot: Angebot) -> list[AngebotsPosition]:
    """Übernahmefähige Elektro-Positionen: Block Elektroarbeiten + gewerkeübergreifende
    Artikel, ohne bauseits/EP/bereits Alternativ, nur mit Preis (reine Textzeilen nie)."""
    sparte = (angebot.konfigurator_typ or "WP").upper()
    gewerke = _gewerke_liste(session)
    return [p for p in angebot.positionen
            if ist_elektro_position(p, sparte, gewerke)
            and not (p.ep_flag or p.bauseits or p.alternativ)
            and (p.e_preis_cent or 0) > 0]


# --- Dubletten (Entscheidung 15.10.2026) --------------------------------------------------

def titel_schluessel(position) -> str:
    """Normalisierte Bezeichnung für den Dubletten-Vergleich: erste Zeile der Bezeichnung
    (sonst erste nicht leere Zeile der Beschreibung, „(optionale Position …)“ übersprungen),
    Groß-/Kleinschreibung und doppelte Leerzeichen egal, erste 30 Zeichen."""
    text = (getattr(position, "bezeichnung", "") or "").strip().splitlines()
    text = text[0] if text else ""
    if not text:
        zeilen = [z.strip() for z in (getattr(position, "beschreibung", "") or "").splitlines()
                  if z.strip()]
        if len(zeilen) > 1 and zeilen[0].lower().startswith("(optionale position"):
            zeilen = zeilen[1:]
        text = zeilen[0] if zeilen else ""
    return re.sub(r"\s+", " ", text).strip().lower()[:TITEL_ZEICHEN]


def dublette_im_ziel(position: AngebotsPosition, ziel: Angebot) -> AngebotsPosition | None:
    """Aktive Position des Zielangebots (nicht EP/bauseits/Alternativ) mit derselben
    Artikelnummer ODER derselben normalisierten Bezeichnung – sonst None."""
    pos_nr = (position.pos_nr or "").strip()
    titel = titel_schluessel(position)
    for z in ziel.positionen:
        if z.ep_flag or z.bauseits or z.alternativ:
            continue
        if pos_nr and (z.pos_nr or "").strip() == pos_nr:
            return z
        if titel and titel_schluessel(z) == titel:
            return z
    return None


# --- Übernahme ---------------------------------------------------------------------------

def _sparten_lang(code: str) -> str:
    from app import sparten
    return sparten.langname(code)


def _euro(cent: int) -> str:
    vz = "-" if cent < 0 else ""
    cent = abs(int(cent))
    e, c = divmod(cent, 100)
    return f"{vz}{e:,.0f}".replace(",", ".") + f",{c:02d} €"


def _vermerke(angebot: Angebot) -> list[str]:
    try:
        liste = json.loads(angebot.vermerke_json or "[]")
    except ValueError:
        liste = []
    return [v for v in liste if isinstance(v, str)]


def _vermerk_setzen(angebot: Angebot, vermerke: list[str]) -> None:
    angebot.vermerke_json = json.dumps(vermerke, ensure_ascii=False)


def _vermerk_text(angebot: Angebot) -> str:
    return VERMERK_MUSTER.format(nummer=angebot.nummer,
                                 sparte=_sparten_lang((angebot.konfigurator_typ or "WP").upper()))


def gruppen_name(angebot: Angebot) -> str:
    """Gruppenüberschrift der Kopien im PV-Angebot: „Elektroarbeiten Wärmepumpe (aus Angebot AN-C-…)“."""
    sparte = (angebot.konfigurator_typ or "WP").upper()
    return f"Elektroarbeiten {_sparten_lang(sparte)} (aus Angebot {angebot.nummer})"


def uebernahmen(session: Session, angebot: Angebot) -> dict[int, list[AngebotsPosition]]:
    """Kopien, die aus diesem Angebot in andere Angebote übernommen wurden:
    Ziel-Angebots-ID → Positionen (uebernommen_von_angebot_id = angebot.id)."""
    ergebnis: dict[int, list[AngebotsPosition]] = {}
    for p in (session.query(AngebotsPosition)
              .filter(AngebotsPosition.uebernommen_von_angebot_id == angebot.id)
              .order_by(AngebotsPosition.angebot_id, AngebotsPosition.sort)):
        ergebnis.setdefault(p.angebot_id, []).append(p)
    return ergebnis


def ersparnis_cent(netto_cent: int, angebot: Angebot, pv: Angebot) -> int:
    """Kundenersparnis = Netto × (USt-Satz Ursprung − USt-Satz PV), kaufmännisch;
    Kontrollwert 2.400,00 € netto, 19 % → 0 % = 456,00 €."""
    differenz = angebot.ust_prozent - pv.ust_prozent
    return int((Decimal(netto_cent) * differenz / 100)
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def uebernehmen(session: Session, angebot: Angebot, pv: Angebot,
                benutzer=None) -> tuple[int, int, int, str]:
    """Elektro-Positionen des Ursprungsangebots ins PV-Angebot übernehmen (eine Transaktion
    des Aufrufers). Rückgabe (anzahl, netto_cent, ersparnis_cent, meldung); ohne neue
    Elektro-Positionen (0, 0, 0, „Nichts zu übernehmen“). Dubletten (gleiche Artikelnummer oder
    gleiche normalisierte Bezeichnung bereits aktiv im PV-Angebot) werden im Ursprung Alternativ,
    aber nicht kopiert – die Meldung nennt sie."""
    if angebot.extern or pv.extern or pv.id == angebot.id:
        return 0, 0, 0, "Übernahme nur zwischen Tool-Angeboten desselben Vorgangs möglich."
    if (pv.konfigurator_typ or "WP").upper() != "PV":
        return 0, 0, 0, f"{pv.nummer} ist kein PV-Angebot."
    if angebot.status != "Entwurf":
        return 0, 0, 0, "Elektroarbeiten können nur aus einem Entwurf übernommen werden."
    if pv.status not in EDITIERBARE_STATUS:
        return 0, 0, 0, (f"PV-Angebot {pv.nummer} ist im Status „{pv.status}“ – "
                         "Übernahme nur bei Entwurf/Versand vorbereitet.")
    if angebot.vorgang_id and pv.vorgang_id and angebot.vorgang_id != pv.vorgang_id:
        return 0, 0, 0, "Die beiden Angebote gehören zu verschiedenen Vorgängen."
    positionen = elektro_positionen(session, angebot)
    if not positionen:
        return 0, 0, 0, "Nichts zu übernehmen – keine offenen Elektro-Positionen."

    # Gruppe im PV-Angebot: bestehende Kopien desselben Ursprungs fortführen (eigene Gruppe
    # je Ursprungsangebot), sonst neuer Block am Ende
    name = gruppen_name(angebot)
    bestehende = [p for p in pv.positionen if p.uebernommen_von_angebot_id == angebot.id]
    if bestehende:
        block_nr = bestehende[-1].block_nr
        name = bestehende[-1].gruppe or name
    else:
        block_nr = max((p.block_nr or 0 for p in pv.positionen), default=0) + 1
    sort = max((p.sort or 0 for p in pv.positionen), default=0)
    netto = 0
    dubletten: list[str] = []
    for p in positionen:
        netto += p.gesamt_cent
        vorhanden = dublette_im_ziel(p, pv)
        if vorhanden is None:
            sort += 1
            kopie = AngebotsPosition(
                sort=sort, block_nr=block_nr, gruppe=name, pos_nr=p.pos_nr,
                bezeichnung=p.bezeichnung, beschreibung=p.beschreibung, menge=p.menge,
                einheit=p.einheit, e_preis_cent=p.e_preis_cent, ep_flag=False,
                ek_cent=p.ek_cent, guid=p.guid,
                # Netto-Einzelpreis inkl. manueller Änderung/Positionsrabatt 1:1 [ANNAHME]
                original_preis_cent=p.original_preis_cent, sonderpreis=p.sonderpreis,
                rabatt_prozent=p.rabatt_prozent, rabatt_cent=p.rabatt_cent,
                uebernommen_von_angebot_id=angebot.id, uebernommen_von_position_id=p.id)
            pv.positionen.append(kopie)
        else:
            dubletten.append(p.pos_nr or p.titel[:TITEL_ZEICHEN])
        # Ursprung: Alternativ „im PV-Angebot enthalten“ mit Verknüpfung (v10-Kennzeichen)
        p.alternativ = True
        p.alternativ_zu = f"PV-Angebot {pv.nummer}"
    # Vermerk im PV-Angebot (einmal je Ursprungsangebot – auch wenn nur Dubletten vorlagen)
    vermerk = _vermerk_text(angebot)
    vermerke = _vermerke(pv)
    if vermerk not in vermerke:
        vermerke.append(vermerk)
        _vermerk_setzen(pv, vermerke)
    session.flush()
    ersparnis = ersparnis_cent(netto, angebot, pv)
    anzahl = len(positionen)
    dubletten_satz = ""
    if dubletten:
        dubletten_satz = (f" – davon {len(dubletten)} bereits im PV-Angebot vorhanden "
                          f"({', '.join(dubletten)}) – nicht kopiert")
    meldung = (f"{anzahl} Position{'en' if anzahl != 1 else ''} (netto {_euro(netto)}) in "
               f"{pv.nummer} übernommen{dubletten_satz} – Kundenersparnis {_euro(ersparnis)}")
    # Notiz im Vorgangs-Chat (Autor System, Kennzeichen „Elektro ins PV“)
    _notiz(session, angebot, benutzer,
           f"Elektroarbeiten aus {angebot.nummer} ins PV-Angebot {pv.nummer} übernommen: "
           f"{anzahl} Position{'en' if anzahl != 1 else ''}, netto {_euro(netto)}, "
           f"Kundenersparnis {_euro(ersparnis)} (0 % USt)"
           + (f"; {len(dubletten)} bereits im PV-Angebot vorhanden, nicht kopiert" if dubletten else "")
           + (f" – durch {benutzer.name}" if getattr(benutzer, "name", "") else ""))
    return anzahl, netto, ersparnis, meldung


def _notiz(session: Session, angebot: Angebot, benutzer, text: str) -> None:
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    # Autor „System“ wie bei den Nachfass-/Verfolgungs-Notizen (benutzer=None)
    vorgaenge_modul.notiz_anlegen(session, vorgang.id, None, text, herkunft=HERKUNFT_NOTIZ)


# --- Zurückholen ---------------------------------------------------------------------------

def _rueckhol_umfang(session: Session, angebot: Angebot) -> dict:
    """Was „Elektroarbeiten zurückholen“ tun würde: kopien (zu löschende Kopien in bearbeitbaren
    PV-Angeboten), zuruecksetzen (eigene Positions-IDs, deren Alternativ-Kennzeichen entfällt),
    ziele (bearbeitbare Zielangebote, aus denen der Vermerk entfällt), gesperrt (Nummern
    versendeter/angenommener Zielangebote – dort bleibt alles unverändert).
    Erfasst (a) Kopien mit uebernommen_von_* und (b) Alternativ-Verknüpfungen des Ursprungs auf
    ein PV-Angebot des Vorgangs (Dubletten ohne Kopie) sowie auf gelöschte/überholte/abgelehnte
    Geschwister-Angebote jeder Sparte."""
    eigene = {p.id: p for p in angebot.positionen}
    geschwister = geschwister_map(session, angebot)
    kopien: list[AngebotsPosition] = []
    zuruecksetzen: set[int] = set()
    ziele: dict[int, Angebot] = {}
    gesperrt: dict[str, str] = {}
    for ziel_id, liste in uebernahmen(session, angebot).items():
        ziel = session.get(Angebot, ziel_id)
        if ziel is not None and ziel.status not in EDITIERBARE_STATUS \
                and ziel.status not in UNGUELTIGE_STATUS:
            gesperrt[ziel.nummer] = ziel.status      # versendet/angenommen: nicht anfassen
            continue
        for kopie in liste:
            ursprung = eigene.get(kopie.uebernommen_von_position_id)
            if ursprung is not None and ursprung.alternativ:
                zuruecksetzen.add(ursprung.id)
            if ziel is not None and ziel.status in EDITIERBARE_STATUS:
                kopien.append(kopie)
        if ziel is not None and ziel.status in EDITIERBARE_STATUS:
            ziele[ziel.id] = ziel
    for p in angebot.positionen:
        if not p.alternativ:
            continue
        _sparte, nummer = ziel_parsen(p.alternativ_zu)
        if not nummer:
            continue                                   # Freitext-Verknüpfung bleibt
        ziel = geschwister.get(nummer)
        if ziel is None or ziel.status in UNGUELTIGE_STATUS:
            zuruecksetzen.add(p.id)                    # gelöscht/überholt/abgelehnt (jede Sparte)
        elif (ziel.konfigurator_typ or "WP").upper() == "PV":
            if ziel.status in EDITIERBARE_STATUS:
                zuruecksetzen.add(p.id)                # Dublette ohne Kopie oder kopierte Position
                ziele.setdefault(ziel.id, ziel)
            else:
                gesperrt.setdefault(ziel.nummer, ziel.status)
    return {"kopien": kopien, "zuruecksetzen": zuruecksetzen, "ziele": ziele, "gesperrt": gesperrt}


def rueckholbar(session: Session, angebot: Angebot) -> tuple[bool, str]:
    """„Elektroarbeiten zurückholen“ ist möglich, solange das Ursprungsangebot Entwurf/
    Versand vorbereitet ist und es etwas zurückzuholen gibt: Kopien in einem PV-Angebot, das
    selbst noch Entwurf/Versand vorbereitet ist, oder Alternativ-Kennzeichen im Ursprung, die
    auf ein bearbeitbares PV-Angebot (auch Dubletten ohne Kopie) bzw. auf ein gelöschtes/
    überholtes/abgelehntes Geschwister-Angebot zeigen. Rückgabe (ok, Grund bei nein)."""
    if angebot.extern:
        return False, "Externer TAIFUN-Eintrag."
    if angebot.status not in EDITIERBARE_STATUS:
        return False, (f"Zurückholen nur solange das Angebot Entwurf/Versand vorbereitet ist "
                       f"(Status „{angebot.status}“).")
    umfang = _rueckhol_umfang(session, angebot)
    if umfang["kopien"] or umfang["zuruecksetzen"]:
        return True, ""
    if umfang["gesperrt"]:
        gruende = [f"{nummer} ist „{status}“" for nummer, status in umfang["gesperrt"].items()]
        return False, ("Zurückholen nicht möglich – " + ", ".join(gruende)
                       + " (nur solange beide Angebote Entwurf/Versand vorbereitet sind).")
    return False, "Keine übernommenen Elektroarbeiten vorhanden."


def zurueckholen(session: Session, angebot: Angebot, benutzer=None) -> tuple[int, str]:
    """Kopien aus dem PV-Angebot entfernen (nur Kopien mit uebernommen_von_*, nur solange das
    PV-Angebot Entwurf/Versand vorbereitet ist – überholte/abgelehnte PV-Angebote und dort
    vorhandene eigene Positionen bleiben unverändert) und das Alternativ-Kennzeichen im
    Ursprungsangebot aufheben (auch bei Dubletten ohne Kopie); dazu Alternativ-Verknüpfungen auf
    gelöschte/ungültige Geschwister-Angebote lösen. Rückgabe (anzahl, Meldung)."""
    ok, grund = rueckholbar(session, angebot)
    if not ok:
        return 0, grund
    umfang = _rueckhol_umfang(session, angebot)
    eigene = {p.id: p for p in angebot.positionen}
    for kopie in umfang["kopien"]:
        session.delete(kopie)
    vermerk = _vermerk_text(angebot)
    for ziel in umfang["ziele"].values():
        _vermerk_setzen(ziel, [v for v in _vermerke(ziel) if v != vermerk])
    for pid in umfang["zuruecksetzen"]:
        p = eigene[pid]
        p.alternativ = False
        p.alternativ_zu = ""
    session.flush()
    anzahl = len(umfang["zuruecksetzen"])
    if not anzahl and not umfang["kopien"]:
        return 0, "Nichts zurückzuholen."
    ziele = sorted(z.nummer for z in umfang["ziele"].values())
    meldung = (f"{anzahl} Position{'en' if anzahl != 1 else ''} zurückgeholt – wieder voll "
               f"in {angebot.nummer} berechnet"
               + (f", {len(umfang['kopien'])} Kopie{'n' if len(umfang['kopien']) != 1 else ''} aus "
                  f"{', '.join(ziele)} entfernt" if umfang["kopien"] and ziele else "")
               + (f" – {', '.join(f'{n} ({s})' for n, s in umfang['gesperrt'].items())} unverändert"
                  if umfang["gesperrt"] else "") + ".")
    _notiz(session, angebot, benutzer,
           f"Elektroarbeiten nach {angebot.nummer} zurückgeholt: {anzahl} Position"
           f"{'en' if anzahl != 1 else ''}"
           + (f" (Kopien aus {', '.join(ziele)} entfernt)" if umfang["kopien"] and ziele else "")
           + (f" – durch {benutzer.name}" if getattr(benutzer, "name", "") else ""))
    return anzahl, meldung
