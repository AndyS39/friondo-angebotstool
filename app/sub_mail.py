# Sub-Beauftragung per Mail (v15, Phase 79): Vorlage aus der Logik-Excel,
# Platzhalter aus Steckbrief/Projekt, Foto-Anhänge aus der Galerie (auf
# 1600 px verkleinert, max. 20 MB gesamt), Steckbrief-PDF, Versand über
# Graph als projektierung@ (Fallback angebot@), CC Projektleiter.

import io
import json
from datetime import datetime
from pathlib import Path

from app import config

BILD_KANTE = 1600
MAX_GESAMT = 20 * 1024 * 1024


def standard_sub_id(session, sub_typ: str) -> int | None:
    """Standard-Sub je Typ (Parameter sub_standards, JSON {typ: sub_id})."""
    from app import projektierung as kern
    try:
        daten = json.loads(kern.parameter_holen(session, "sub_standards", "{}"))
        wert = int(daten.get(sub_typ) or 0)
        return wert or None
    except (ValueError, TypeError):
        return None


def standard_sub_setzen(session, sub_typ: str, sub_id: int | None) -> None:
    from app import projektierung as kern
    try:
        daten = json.loads(kern.parameter_holen(session, "sub_standards", "{}"))
    except ValueError:
        daten = {}
    if sub_id:
        daten[sub_typ] = sub_id
    else:
        daten.pop(sub_typ, None)
    kern.parameter_setzen(session, "sub_standards",
                          json.dumps(daten, ensure_ascii=False))


def aktion_parsen(aktion_wert: str) -> tuple[str, str]:
    """"mail:GaLa-Bau@Außengerät" -> (sub_typ, ordner-fallback)."""
    rest = (aktion_wert or "")
    if rest.startswith("mail:"):
        rest = rest[5:]
    typ, _, ordner = rest.partition("@")
    return typ.strip(), ordner.strip()


def fotos_fuer(session, gewerk, ordner: list[str]) -> list:
    """Galerie-Bilder des Vorgangs aus den Vorlage-Ordnern (neueste zuerst)."""
    from app.models import Angebot, GalerieDatei
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    if angebot is None or not angebot.vorgang_id or not ordner:
        return []
    return (session.query(GalerieDatei)
            .filter(GalerieDatei.vorgang_id == angebot.vorgang_id,
                    GalerieDatei.ordner.in_(ordner),
                    GalerieDatei.bild.is_(True))
            .order_by(GalerieDatei.id.desc()).all())


def _foto_anhang(datei) -> tuple[str, bytes, str] | None:
    """Bild lesen und für den Mailversand auf 1600 px verkleinern."""
    from PIL import Image
    pfad = config.DATA_ORDNER / datei.pfad
    if not pfad.exists():
        return None
    try:
        with Image.open(pfad) as bild:
            bild = bild.convert("RGB")
            bild.thumbnail((BILD_KANTE, BILD_KANTE))
            puffer = io.BytesIO()
            bild.save(puffer, "JPEG", quality=85)
        name = Path(datei.dateiname).stem[:60] + ".jpg"
        return (f"{datei.ordner.replace('/', '-')}_{name}",
                puffer.getvalue(), "image/jpeg")
    except Exception:
        return None


def senden(session, aufgabe, gewerk, sub, betreff: str, text: str,
           foto_ids: list[int], mit_steckbrief: bool,
           benutzer=None) -> tuple[bool, str]:
    """Versand + Folgeaktionen: ProjektSub (angefragt), Projekt-Mail-Verlauf,
    Verlaufseintrag, Aufgabe auf die *beauftragt*-Option setzen."""
    from app import benachrichtigungen, graph_versand
    from app import projektierung as kern
    from app.models import Benutzer, GalerieDatei, Projekt, ProjektMail, ProjektSub

    if sub is None or not (sub.email or "").strip():
        return False, "Der Subunternehmer hat keine E-Mail-Adresse."
    projekt = session.get(Projekt, gewerk.projekt_id)

    anhaenge: list[tuple[str, bytes, str]] = []
    gesamt = 0
    weggelassen = 0
    for foto_id in foto_ids:
        datei = session.get(GalerieDatei, foto_id)
        if datei is None:
            continue
        anhang = _foto_anhang(datei)
        if anhang is None:
            continue
        if gesamt + len(anhang[1]) > MAX_GESAMT:
            weggelassen += 1
            continue
        gesamt += len(anhang[1])
        anhaenge.append(anhang)
    if mit_steckbrief:
        from app.steckbrief_pdf import steckbrief_pdf_bytes
        try:
            pdf = steckbrief_pdf_bytes(session, gewerk)
            if gesamt + len(pdf) <= MAX_GESAMT:
                anhaenge.append((f"Steckbrief_{projekt.nummer}.pdf", pdf,
                                 "application/pdf"))
        except Exception:
            pass   # PDF darf den Versand nie verhindern

    absender = benachrichtigungen._absender(session)
    cc = []
    if projekt and projekt.projektleiter_id:
        leiter = session.get(Benutzer, projekt.projektleiter_id)
        if leiter is not None and leiter.email:
            cc.append(leiter.email)
    ok, fehler, conversation_id = graph_versand.mail_mit_anhaengen_senden(
        sub.email, betreff, text, anhaenge, cc=cc, absender=absender)
    if not ok:
        return False, fehler

    eintrag = ProjektSub(
        projekt_id=gewerk.projekt_id, gewerk_id=gewerk.id, sub_id=sub.id,
        leistung=(aufgabe.titel if aufgabe is not None else "Sub-Anfrage")[:300],
        status="angefragt", graph_conversation_id=conversation_id or None,
        angefragt_am=datetime.now(),
        erstellt_von=benutzer.id if benutzer else None)
    session.add(eintrag)
    session.flush()
    session.add(ProjektMail(
        projekt_id=gewerk.projekt_id, sub_eintrag_id=eintrag.id,
        graph_id=f"ausgehend-{eintrag.id}-{datetime.now():%Y%m%d%H%M%S}",
        von_name=benutzer.name if benutzer else "Angebotstool",
        von_email=absender, empfangen_am=datetime.now(),
        betreff=betreff, vorschau=text[:500], eingehend=False))
    kern.verlauf(session, gewerk.projekt_id,
                 f"Sub-Anfrage per Mail an {sub.firma} ({sub.typ}) – "
                 f"{len(anhaenge)} Anhänge",
                 benutzer=benutzer, gewerk_id=gewerk.id)
    if aufgabe is not None and aufgabe.aktion_typ == "auswahl":
        for teil in (aufgabe.optionen or "").split("|"):
            teil = teil.strip()
            if teil.endswith("*") and "beauftragt" in teil.lower():
                kern.aufgabe_auswahl_setzen(session, aufgabe,
                                            teil.rstrip("*").strip(),
                                            benutzer=benutzer)
                break
    meldung = f"Mail an {sub.firma} gesendet ({len(anhaenge)} Anhänge"
    if weggelassen:
        meldung += f", {weggelassen} Fotos wegen 20-MB-Grenze weggelassen"
    return True, meldung + ")."


def antworten_abgleichen() -> int:
    """v15 (Phase 79): Antworten der Subs (Konversation der Anfrage) aus dem
    Projektierungs-Postfach lesen – läuft im mail_sync-Scheduler. Neue
    eingehende Mails landen im Projekt-Mail-Verlauf; die erste Antwort setzt
    antwort_am (die Akte schlägt dann „bestätigt“ vor)."""
    from app import graph_versand, mail_sync
    from app.db import SessionLocal
    from app.models import Benutzer, ProjektMail, ProjektSub

    token = graph_versand._token()
    if token is None:
        return 0
    session = SessionLocal()
    neu_gesamt = 0
    try:
        from app import benachrichtigungen
        from app import projektierung as kern
        postfach = benachrichtigungen._absender(session)
        eigene = {postfach.lower(),
                  (graph_versand.angemeldeter_benutzer() or "").lower()}
        for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True)):
            if b.email:
                eigene.add(b.email.lower())
        offene = (session.query(ProjektSub)
                  .filter(ProjektSub.graph_conversation_id.isnot(None),
                          ProjektSub.status.in_(["angefragt", "beauftragt"]))
                  .all())
        for eintrag in offene:
            try:
                nachrichten = mail_sync.nachrichten_je_konversation(
                    token, eintrag.graph_conversation_id, postfach)
            except Exception:
                continue
            for nachricht in nachrichten:
                graph_id = nachricht.get("id") or ""
                if not graph_id or nachricht.get("isDraft"):
                    continue
                if session.query(ProjektMail).filter(
                        ProjektMail.graph_id == graph_id).first() is not None:
                    continue
                absender = ((nachricht.get("from") or {})
                            .get("emailAddress") or {})
                von_email = absender.get("address") or ""
                eingehend = bool(von_email) and von_email.lower() not in eigene
                session.add(ProjektMail(
                    projekt_id=eintrag.projekt_id, sub_eintrag_id=eintrag.id,
                    graph_id=graph_id,
                    von_name=absender.get("name") or "",
                    von_email=von_email,
                    empfangen_am=mail_sync._zeit_parsen(
                        nachricht.get("receivedDateTime")
                        or nachricht.get("sentDateTime") or ""),
                    betreff=nachricht.get("subject") or "",
                    vorschau=nachricht.get("bodyPreview") or "",
                    eingehend=eingehend))
                neu_gesamt += 1
                if eingehend and eintrag.antwort_am is None:
                    eintrag.antwort_am = datetime.now()
                    from app.models import Projekt
                    projekt = session.get(Projekt, eintrag.projekt_id)
                    if projekt is not None:
                        kern.benachrichtigen(
                            session, [projekt.projektleiter_id],
                            f"Sub-Antwort zu {projekt.nummer} eingegangen",
                            f"/projektierung/projekt/{projekt.id}#subs",
                            art="sub")
        session.commit()
    finally:
        session.close()
    return neu_gesamt
