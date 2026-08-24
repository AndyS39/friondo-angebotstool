# Abnahmetests (v5): End-to-End über den FastAPI-TestClient – NUR auf dem
# Entwicklungs-PC gegen die Test-DB ausführen (verbraucht Angebotsnummern),
# mit gemocktem Microsoft Graph. Aufruf: venv\Scripts\python tests\abnahme.py
# Gibt eine Ergebnisübersicht aus; Exit-Code 1 bei Fehlern. Hinterlässt keine
# Testdaten (alles wird am Ende wieder entfernt).
import copy
import datetime
import io
import json
import sys
import warnings
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pypdf
from fastapi.testclient import TestClient

from app import angebot_aufbau, anhaenge, config, graph_versand, kfw, pdf_export
from app import konfigurator as engine
from app.db import SessionLocal, init_db
from app.logik import logik_einlesen
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, Erfassung, Kunde,
                        Lead, einstellung_holen)
from tests.test_regression import KONTROLL_SZENARIO

ERGEBNISSE: list[tuple[str, str, bool, str]] = []   # (Bereich, Test, ok, Detail)


def pruefe(bereich, name, ok, detail=""):
    ERGEBNISSE.append((bereich, name, bool(ok), detail))


def euro(cent):
    return f"{cent / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def vorab_aufraeumen(s):
    """Reste eines abgebrochenen Laufs entfernen, damit der neue Lauf sauber startet."""
    from app import signaturen
    from app.models import AngebotsLoeschung, AngebotsMail, AngebotsNotiz, Erfassung, MondayPerson
    for k in s.query(Kunde).filter(Kunde.email == "abnahme@test.local"):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            (config.DATA_ORDNER / "angebote" / f"{a.nummer}.pdf").unlink(missing_ok=True)
            s.query(AngebotsMail).filter_by(angebot_id=a.id).delete()
            s.query(AngebotsNotiz).filter_by(angebot_id=a.id).delete()
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.in_(["AD Abnahme", "Abn V6"])):
        s.delete(b)
    for l in s.query(Lead).filter(Lead.monday_item_id.in_(["abn-lead", "abn-v6"])):
        s.delete(l)
    s.query(MondayPerson).filter_by(monday_name="abn.v6@friondo.de").delete()
    s.query(AngebotsMail).filter(AngebotsMail.graph_id.in_(["s1", "k1"])).delete(synchronize_session=False)
    s.query(AngebotsLoeschung).filter(AngebotsLoeschung.kunde_name.like("%Abnahme%")).delete(synchronize_session=False)
    s.commit()
    sig_ordner = config.DATA_ORDNER / "signaturen" / "1"
    if sig_ordner.exists():
        for datei in sig_ordner.iterdir():
            if datei.suffix.lower() in (".htm", ".html") and "Abnahme-Signatur" in datei.read_text(errors="ignore"):
                signaturen.entfernen(1)
                break


def main():
    init_db()
    s = SessionLocal()
    vorab_aufraeumen(s)
    logik, bericht = logik_einlesen()
    aufraeumen: list = []
    client = TestClient(app)
    client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    # ---------- 1) Kontroll-Szenarien ----------
    kg = dict(KONTROLL_SZENARIO)            # enthält A13 = 4
    pos = angebot_aufbau.positionen_zusammenstellen(logik, kg, s)
    netto = sum(round(p["menge"] * p["e_preis_cent"]) for p in pos if not p["ep_flag"])
    pruefe("Kontroll KG", "Katalog vollständig (inkl. A13 = 4)", engine.naechste_frage(logik, kg) is None)
    pruefe("Kontroll KG", "Ampel grün", engine.ampel_gruende(logik, kg) == [])
    pruefe("Kontroll KG", "Netto 29.629,37 €", netto == 2962937, euro(netto))
    pruefe("Kontroll KG", "Erdleitung 8 m → Pos. 102 × 5", [p["menge"] for p in pos if p["pos_nr"] == "102"] == [5.0])
    pruefe("Kontroll KG", "A13 = 4 m → keine Pos. 103", not [p for p in pos if p["pos_nr"] == "103"])
    kg8 = dict(kg, A13=8)
    pos8 = angebot_aufbau.positionen_zusammenstellen(logik, kg8, s)
    netto8 = sum(round(p["menge"] * p["e_preis_cent"]) for p in pos8 if not p["ep_flag"])
    pruefe("Kontroll KG", "A13 = 8 m → Pos. 103 × 3 = +267,00 €", netto8 == 2962937 + 26700
           and [p["menge"] for p in pos8 if p["pos_nr"] == "103"] == [3.0], euro(netto8))
    # KfW für KG-Fall
    parameter, _ = kfw.parameter_lesen(logik)
    eing = kfw.eingaben_aus_antworten(engine.kfw_daten(kg), netto + int(netto * 0.19))
    erg = kfw.berechnen(parameter, eing)
    pruefe("Kontroll KG", "KfW Zuschuss 19.600 € (Satz 70)", erg.zuschuss_cent == 1960000, euro(erg.zuschuss_cent))

    dg = dict(KONTROLL_SZENARIO)
    dg.update({"A04": "DG", "D01": "Nein", "D02": "Nein", "D03": "Nein", "D04": "Ja",
               "D05": {"Heizung VL/RL (m)": 6, "Trinkwasser TWK/TWW/Zirkulation (m)": 4}, "A05": 8})
    posdg = angebot_aufbau.positionen_zusammenstellen(logik, dg, s)
    nummern = {p["pos_nr"] for p in posdg}
    pruefe("Kontroll DG", "Katalog vollständig (inkl. A13)", engine.naechste_frage(logik, dg) is None)
    pruefe("Kontroll DG", "Pos. 163 (Dachzentrale) + 139/140 × Meter", {"163", "139", "140"} <= nummern
           and [p["menge"] for p in posdg if p["pos_nr"] == "139"] == [6.0])
    pruefe("Kontroll DG", "Erdleitung gefragt (DG + D01 = Nein), Fassade nicht",
           engine.ist_sichtbar(logik.fragen["A05"], dg, logik.fragen)
           and not engine.ist_sichtbar(logik.fragen["A06"], dg, logik.fragen))

    # Rabatt: Kontroll-Angebot mit 500 € Brutto-Rabatt
    kunde_t = Kunde(anrede="Frau", vorname="Erika", nachname="Abnahme", email="abnahme@test.local",
                    strasse="Testweg 1", plz="47441", ort="Moers")
    s.add(kunde_t); s.commit(); aufraeumen.append(kunde_t)
    ang = angebot_aufbau.angebot_anlegen(s, kunde_t.id, antworten=kg, logik=logik)
    aufraeumen.append(ang)
    ang.rabatt_cent = 50000; s.commit()
    su = ang.summen()
    pruefe("Rabatt", "Endbetrag 34.758,95 € (Brutto − 500 €)", su["endbetrag"] == 3475895, euro(su["endbetrag"]))
    eing = kfw.eingaben_aus_antworten(json.loads(ang.kfw_json), su["endbetrag"])
    erg = kfw.berechnen(parameter, eing)
    pruefe("Rabatt", "Zuschuss 19.600 €, Eigenanteil 15.158,95 €",
           erg.zuschuss_cent == 1960000 and erg.eigenanteil_cent == 1515895, euro(erg.eigenanteil_cent))
    db_ohne = dict(angebot_aufbau.angebot_anlegen(s, kunde_t.id, antworten=kg, logik=logik).deckungsbeitrag())
    aufraeumen.append(s.query(Angebot).order_by(Angebot.id.desc()).first())
    pruefe("Rabatt", "DB sinkt um Netto-Anteil 420,17 €", db_ohne["db"] - ang.deckungsbeitrag()["db"] == 42017)

    # ---------- 2) KfW gegen foerderrechner-website.html ----------
    import unittest
    ausgabe = io.StringIO()
    res = unittest.TextTestRunner(stream=ausgabe, verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromName("tests.test_kfw"))
    pruefe("KfW", f"{res.testsRun} Testfälle gegen den HTML-Rechner (EFH/MFH/Gewerbe, Deckel, Rundung)",
           res.wasSuccessful(), f"{len(res.failures)} Fehler, {len(res.errors)} Abbrüche")

    # ---------- 3) A09 Stahltank ----------
    a09 = dict(kg, A01="Öl", A07="Ja", A08="Stahl", A09="bis 5.000 L")
    p09 = angebot_aufbau.positionen_zusammenstellen(logik, a09, s)
    z10 = [p for p in p09 if p["pos_nr"] == "Z10"]
    pruefe("A09", "Öl → Ja → Stahl → bis 5.000 L = Z10, 1.812,00 €", len(z10) == 1 and z10[0]["e_preis_cent"] == 181200
           and not [p for p in p09 if p["pos_nr"] == "Z03"])
    pruefe("A09", "Validator ohne A09-Warnung", not [w for w in bericht.warnungen if "A09" in w])

    # ---------- 4) Anhänge ----------
    pruefe("Anhänge", "4 Broschüren im Ordner anlagen/",
           all((Path("anlagen") / n).exists() for n in ("Friondo Unternehmenspräsentation.pdf", "Broschüre Ratenkauf.pdf",
                                                       "Friondo HEMS.pdf", "Friondo SpotDynamic.pdf")))
    hems = [a.datei for a in anhaenge.fuer_angebot(logik, ang)]     # KG: P01 = Ja, P03 = Nein
    pruefe("Anhänge", "HEMS-Angebot (P01 = Ja) → 4 Anhänge inkl. Gerätebroschüre", sorted(hems) == sorted(
        ["Friondo Unternehmenspräsentation.pdf", "Broschüre Ratenkauf.pdf",
         "Friondo HEMS.pdf", "Bosch CS3800iAW.pdf"]), ", ".join(hems))
    ohne = angebot_aufbau.angebot_anlegen(s, kunde_t.id, antworten=dict(kg, P01="Nein", P02="Nein", P03="Nein"), logik=logik)
    aufraeumen.append(ohne)
    liste_ohne = [a.datei for a in anhaenge.fuer_angebot(logik, ohne)]
    pruefe("Anhänge", "ohne Friondo-Produkte → 3 Anhänge (Standard + Gerätebroschüre)", sorted(liste_ohne) == sorted(
        ["Friondo Unternehmenspräsentation.pdf", "Broschüre Ratenkauf.pdf",
         "Bosch CS3800iAW.pdf"]), ", ".join(liste_ohne))
    spot = angebot_aufbau.angebot_anlegen(s, kunde_t.id, antworten=dict(kg, P03="Ja"), logik=logik)
    aufraeumen.append(spot)
    pruefe("Anhänge", "SpotDynamic (P03 = Ja) → 5 Anhänge + Vollmacht",
           len(anhaenge.fuer_angebot(logik, spot)) == 5 and anhaenge.vollmacht_erforderlich(spot))
    pruefe("Anhänge", "alle Dateien vorhanden (kein „fehlt“)", all(a.vorhanden for a in anhaenge.fuer_angebot(logik, spot)))

    # ---------- 5) Status-Kette + CC/BCC (gemockter Graph) ----------
    ad = Benutzer(name="AD Abnahme", rolle="aussendienst", pin_hash="x", email="ad.abnahme@friondo.de")
    s.add(ad); s.commit(); aufraeumen.append(ad)
    erf = Erfassung(kunde_id=kunde_t.id, benutzer_id=ad.id, angebot_id=ang.id, antworten_json=json.dumps(kg), status="In Bearbeitung")
    s.add(erf); s.commit(); aufraeumen.append(erf)
    payloads = []

    def fake_graph(methode, pfad, token, daten=None):
        payloads.append((pfad, daten))
        return {"id": "msg-abn", "webLink": "https://outlook/x", "conversationId": "konv-abn"} if pfad == "/me/messages" else {}

    with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
            mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"), \
            mock.patch.object(graph_versand, "_token", return_value="tok"), \
            mock.patch.object(graph_versand, "_graph_aufruf", side_effect=fake_graph):
        antwort = client.post(f"/angebote/{ang.id}/email", follow_redirects=False)
    s.expire_all(); ang = s.get(Angebot, ang.id)
    nachricht = next((d for p, d in payloads if p == "/me/messages"), {}) or {}
    adressen = lambda schl: [r["emailAddress"]["address"] for r in nachricht.get(schl, [])]
    pruefe("Versand", "Status → „Versand vorbereitet“", ang.status == "Versand vorbereitet", ang.status)
    pruefe("Versand", "conversationId gespeichert", ang.graph_conversation_id == "konv-abn")
    pruefe("Versand", "Absender angebot@friondo.de", nachricht.get("from", {}).get("emailAddress", {}).get("address") == "angebot@friondo.de")
    pruefe("Versand", "An = Kunde", adressen("toRecipients") == ["abnahme@test.local"])
    pruefe("Versand", "CC = E-Mail des Außendienstlers", adressen("ccRecipients") == ["ad.abnahme@friondo.de"])
    bcc_soll = [a.strip() for a in einstellung_holen(s, "mail_bcc", "").split(",") if a.strip()]
    pruefe("Versand", f"BCC aus Parametrierung ({', '.join(bcc_soll) or 'leer'})", adressen("bccRecipients") == bcc_soll)
    pruefe("Versand", "Betreff/Text aus Vorlage mit Platzhaltern gefüllt",
           ang.nummer in nachricht.get("subject", "") and "Sehr geehrte Frau Abnahme," in nachricht.get("body", {}).get("content", "")
           and "{" not in nachricht.get("body", {}).get("content", ""))
    anhang_namen = [d["name"] for p, d in payloads if p.endswith("/attachments")]
    pruefe("Versand", "PDF + 4 Broschüren als Anhang", anhang_namen[0] == f"{ang.nummer}.pdf" and len(anhang_namen) == 5, ", ".join(anhang_namen))
    # Mail-Abgleich: gesendete Nachricht → Versendet; Erfassung erledigt; monday übersprungen (kein Lead)
    from app import mail_sync
    gesendet = {"id": "s1", "conversationId": "konv-abn", "isDraft": False, "sentDateTime": "2026-08-19T10:00:00Z",
                "from": {"emailAddress": {"address": "angebot@friondo.de", "name": "Friondo"}}, "subject": "x", "bodyPreview": ""}
    mail_sync.versand_erkennen(s, ang, [gesendet], {"angebot@friondo.de", "ida@friondo.de"}); s.commit()
    mail_sync._nach_versand(s, ang)
    s.expire_all(); ang = s.get(Angebot, ang.id); erf = s.get(Erfassung, erf.id)
    pruefe("Versand", "Abgleich erkennt Versand → „Versendet“", ang.status == "Versendet")
    pruefe("Versand", "Erfassung → Erledigt, monday-Rückspielung protokolliert (übersprungen, kein Lead)",
           erf.status == "Erledigt" and ang.monday_rueck_status == "uebersprungen")
    # Kundenantwort → Brief-Symbol
    antwort_mail = dict(gesendet, id="k1", from_={"emailAddress": {"address": "abnahme@test.local", "name": "Erika"}})
    antwort_mail["from"] = antwort_mail.pop("from_")
    mail_sync.nachrichten_verarbeiten(s, ang, [gesendet, antwort_mail], {"angebot@friondo.de"}); s.commit()
    liste = client.get("/angebote").text
    pruefe("Versand", "Antwort → Brief-Symbol mit Zähler in der Liste", f'/angebote/{ang.id}/mails' in liste and "✉ 1" in liste)
    from app.models import AngebotsMail
    aufraeumen.extend(s.query(AngebotsMail).filter(AngebotsMail.angebot_id == ang.id).all())

    # ---------- 6) Lösch-/Archiv-Regeln ----------
    # seit v6 sind Versendete löschbar (mit Protokoll, geprüft im v6-Block) –
    # hier nur: Archivieren funktioniert weiterhin
    client.post(f"/angebote/{ang.id}/archivieren", follow_redirects=True); s.expire_all()
    pruefe("Löschen/Archiv", "Versendet → archivierbar, aus Standardliste raus, im Archiv-Filter",
           s.get(Angebot, ang.id).archiviert and ang.nummer not in client.get("/angebote").text
           and ang.nummer in client.get("/angebote?status=archiv").text)
    client.post(f"/angebote/{ang.id}/archivieren"); s.expire_all()
    pruefe("Löschen/Archiv", "zurückgeholt", not s.get(Angebot, ang.id).archiviert)
    r = client.post(f"/erfassungen/{erf.id}/loeschen", follow_redirects=True); s.expire_all()
    pruefe("Löschen/Archiv", "Erfassung mit Angebot nicht löschbar", s.get(Erfassung, erf.id) is not None and "Angebot verknüpft" in r.text)
    entwurf = angebot_aufbau.angebot_anlegen(s, kunde_t.id)
    e2 = Erfassung(kunde_id=kunde_t.id, benutzer_id=ad.id, angebot_id=entwurf.id, status="In Bearbeitung")
    s.add(e2); s.commit(); eid, e2id = entwurf.id, e2.id
    client.post(f"/angebote/{eid}/loeschen"); s.expire_all()
    pruefe("Löschen/Archiv", "Entwurf löschbar, Erfassung wird freigegeben (Neu)",
           s.get(Angebot, eid) is None and s.get(Erfassung, e2id).angebot_id is None and s.get(Erfassung, e2id).status == "Neu")
    lead = Lead(monday_item_id="abn-lead", vorname="A", nachname="B", erfassung_id=e2id, vot_datum=datetime.datetime.now())
    s.add(lead); s.commit(); lid = lead.id
    client.post(f"/erfassungen/{e2id}/loeschen"); s.expire_all()
    pruefe("Löschen/Archiv", "Erfassung ohne Angebot löschbar, Lead wieder frei",
           s.get(Erfassung, e2id) is None and s.get(Lead, lid).erfassung_id is None)
    aufraeumen.append(s.get(Lead, lid))
    r = client.post(f"/benutzer/{ad.id}/loeschen", follow_redirects=True); s.expire_all()
    pruefe("Löschen/Archiv", "Benutzer mit Erfassung → deaktiviert statt gelöscht",
           s.get(Benutzer, ad.id) is not None and not s.get(Benutzer, ad.id).aktiv and "deaktiviert statt gelöscht" in r.text)

    # ---------- 7) Briefanrede im PDF ----------
    pfad = pdf_export.pdf_fuer_angebot(s, ang)
    t1 = pypdf.PdfReader(str(pfad)).pages[0].extract_text()
    pruefe("PDF", "Briefanrede „Sehr geehrte Frau Abnahme,“ im Vortext", "Sehr geehrte Frau Abnahme," in t1)
    k = s.get(Kunde, kunde_t.id); k.anrede = "Herr"; s.commit(); s.expire_all()
    t2 = pypdf.PdfReader(str(pdf_export.pdf_fuer_angebot(s, s.get(Angebot, ang.id)))).pages[0].extract_text()
    pruefe("PDF", "„Sehr geehrter Herr Abnahme,“ bei Anrede Herr", "Sehr geehrter Herr Abnahme," in t2)
    k = s.get(Kunde, kunde_t.id); k.anrede = "Firma"; s.commit(); s.expire_all()
    t3 = pypdf.PdfReader(str(pdf_export.pdf_fuer_angebot(s, s.get(Angebot, ang.id)))).pages[0].extract_text()
    pruefe("PDF", "Fallback „Sehr geehrte Damen und Herren,“", "Sehr geehrte Damen und Herren," in t3)
    alle_seiten = "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(pfad)).pages)
    pruefe("PDF", "Summenblock Netto/USt/Gesamt/−Rabatt/=Endbetrag + Eigenanteil",
           all(w in alle_seiten for w in ("Netto-Summe", "Rabatt", "Endbetrag", "Eigenanteil")))

    # ---------- 8) v6-Abnahme ----------
    from app import mail_vorlagen, monday_sync, signaturen
    from app.models import AngebotsLoeschung, AngebotsNotiz, MondayPerson
    # Lead-Zuordnung rückwirkend
    tl = Lead(monday_item_id="abn-v6", vorname="V", nachname="Sechs",
              monday_person="abn.v6@friondo.de", vot_datum=datetime.datetime.now())
    tb = Benutzer(name="Abn V6", rolle="aussendienst", email="abn.v6@friondo.de", pin_hash="x")
    s.add_all([tl, tb]); s.commit()
    mp = MondayPerson(monday_name="abn.v6@friondo.de"); s.add(mp); s.commit()
    mp.benutzer_id = tb.id
    anzahl = monday_sync.zuordnung_anwenden(s, mp); s.commit()
    pruefe("v6", "Personen-Zuordnung wirkt sofort rückwirkend", anzahl == 1
           and s.get(Lead, tl.id).benutzer_id == tb.id)
    pruefe("v6", "E-Mail-Matching (monday liefert Adresse)",
           monday_sync._benutzer_fuer_person(s, "abn.v6@friondo.de") == tb.id)
    # Individuell (v7): KEIN Auto-Archiv mehr – Kette läuft über die Erfassung
    indiv = angebot_aufbau.angebot_anlegen(s, kunde_t.id)
    client.post(f"/angebote/{indiv.id}/status", data={"status": "Individuell"})
    s.expire_all()
    pruefe("v6", "Status Individuell OHNE Auto-Archiv (v7-Kette)",
           s.get(Angebot, indiv.id).status == "Individuell" and not s.get(Angebot, indiv.id).archiviert)
    # Summenzeile
    pruefe("v6", "Angebotsliste mit Summenzeile Netto/Endbetrag/DB",
           all(w in client.get("/angebote").text for w in ("Summe (", "Netto:", "Endbetrag (brutto):", "DB:")))
    # Förder-Override + EP-Kästchen (auf dem Rabatt-Angebot ang)
    a2 = s.get(Angebot, indiv.id); a2.status = "Entwurf"; a2.archiviert = False; s.commit()
    client.post(f"/angebote/{ang.id}/foerderung", data={"betrag": "12.345,00"})
    s.expire_all()
    pruefe("v6", "Förderbetrag manuell überschreibbar", s.get(Angebot, ang.id).foerderung_manuell_cent == 1234500)
    client.post(f"/angebote/{ang.id}/foerderung", data={"betrag": ""})
    pos1 = s.get(Angebot, ang.id).positionen[0]
    client.post(f"/angebote/{ang.id}/position/{pos1.id}/aendern",
                data={"anzeige_nr": "", "menge": "", "e_preis": "", "rabatt_wert": "", "rabatt_typ": "betrag", "ep_flag": "on"})
    s.expire_all()
    pruefe("v6", "EP-Kästchen je Position", s.get(type(pos1), pos1.id).ep_flag)
    client.post(f"/angebote/{ang.id}/position/{pos1.id}/aendern",
                data={"anzeige_nr": "", "menge": "", "e_preis": "", "rabatt_wert": "", "rabatt_typ": "betrag"})
    # Verfolgung
    client.post(f"/angebote/{ang.id}/verfolgung",
                data={"verfolgung_ampel": "heiss", "wiedervorlage_am": "2026-01-01", "notiz": "Abnahme"})
    s.expire_all()
    pruefe("v6", "Verfolgung: Ampel + fällige Wiedervorlage + Notiz",
           s.get(Angebot, ang.id).verfolgung_ampel == "heiss"
           and ang.nummer in client.get("/angebote?verfolgung=faellig").text
           and s.query(AngebotsNotiz).filter_by(angebot_id=ang.id).count() == 1)
    # Statistik
    stat = client.get("/statistik?zeitraum=jahr").text
    pruefe("v6", "Statistik-Seite (Jahr) mit Kacheln + Je Vertriebler",
           "Abschlussquote" in stat and "Je Vertriebler" in stat)
    # HTML-Mail + Signatur (Payload lag oben schon vor? Neu prüfen mit Signatur)
    signaturen.speichern(1, [("Sig.htm", b"<html><body><p>Abnahme-Signatur <img src=\"x/l.png\"></p></body></html>"), ("l.png", b"PNG")])
    payloads.clear()
    with mock.patch.object(graph_versand, "konfiguriert", return_value=True),             mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"),             mock.patch.object(graph_versand, "_token", return_value="tok"),             mock.patch.object(graph_versand, "_graph_aufruf", side_effect=fake_graph):
        client.post(f"/angebote/{a2.id}/email", follow_redirects=False)
    n2 = next((d for pfad, d in payloads if pfad == "/me/messages"), {}) or {}
    inline = [d for pfad, d in payloads if pfad.endswith("/attachments") and d.get("isInline")]
    pruefe("v6", "HTML-Mail mit Outlook-Signatur (cid + Inline-Bild)",
           n2.get("body", {}).get("contentType") == "html"
           and "Abnahme-Signatur" in n2.get("body", {}).get("content", "")
           and len(inline) == 1 and inline[0]["contentId"].startswith("sig1"))
    signaturen.entfernen(1)
    # Löschen versendeter mit Protokoll
    a2 = s.get(Angebot, a2.id); a2.status = "Versendet"; s.commit()
    n2_nummer, a2_id = a2.nummer, a2.id
    client.post(f"/angebote/{a2_id}/loeschen")
    s.expire_all()
    pruefe("v6", "Versendetes löschbar + Lösch-Protokoll + Nummer gesperrt",
           s.get(Angebot, a2_id) is None
           and s.query(AngebotsLoeschung).filter_by(nummer=n2_nummer).count() == 1
           and angebot_aufbau.naechste_angebotsnummer(s) != n2_nummer)
    # v6-Aufräumen
    s.query(AngebotsLoeschung).filter_by(nummer=n2_nummer).delete()
    s.query(AngebotsNotiz).filter_by(angebot_id=ang.id).delete()
    ang2 = s.get(Angebot, ang.id); ang2.verfolgung_ampel = ""; ang2.wiedervorlage_am = None
    s.delete(s.get(Lead, tl.id)); s.query(MondayPerson).filter_by(monday_name="abn.v6@friondo.de").delete()
    s.delete(s.get(Benutzer, tb.id)); s.commit()

    # ---------- Aufräumen ----------
    for a in s.query(Angebot).filter(Angebot.kunde_id == kunde_t.id):
        Path(f"data/angebote/{a.nummer}.pdf").unlink(missing_ok=True)
        s.delete(a)
    for e in s.query(Erfassung).filter(Erfassung.kunde_id == kunde_t.id):
        s.delete(e)
    for l in s.query(Lead).filter(Lead.monday_item_id == "abn-lead"):
        s.delete(l)
    from app.models import AngebotsMail as AM
    s.query(AM).filter(AM.graph_id.in_(["s1", "k1"])).delete(synchronize_session=False)
    s.delete(s.get(Benutzer, ad.id)) if s.get(Benutzer, ad.id) else None
    s.delete(s.get(Kunde, kunde_t.id))
    s.commit()

    # ---------- Übersicht ----------
    breite = max(len(n) for _, n, _, _ in ERGEBNISSE) + 2
    aktuell = None
    ok_gesamt = 0
    for bereich, name, ok, detail in ERGEBNISSE:
        if bereich != aktuell:
            print(f"\n[{bereich}]"); aktuell = bereich
        print(f"  {'OK ' if ok else 'FEHLER'} {name:<{breite}} {detail}")
        ok_gesamt += ok
    print(f"\n{ok_gesamt}/{len(ERGEBNISSE)} Abnahmepunkte bestanden.")
    return 0 if ok_gesamt == len(ERGEBNISSE) else 1


if __name__ == "__main__":
    sys.exit(main())
