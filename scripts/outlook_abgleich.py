# v33 (PLAN_V20 Phase 170): Vorab-Abgleich TAIFUN – NUR LESEN. Liest den Outlook-Kalender
# eines Monteurs mit laufendem Outlook→TAIFUN-Abgleich (calendarView) und gibt je Eintrag
# Betreff, Kategorien, Frei/Belegt, Ersteller und das Friondo-Kennzeichen als
# Markdown-Tabelle aus, damit Betreff-Muster, Kategorie und Kennzeichen der TAIFUN-Termine
# in docs/outlook-sync.md (Abschnitt 1) festgehalten werden können. Es wird nichts
# gespeichert und nichts geschrieben (kein POST/PATCH/DELETE).
#
# Aufruf (Server mit Graph-Zugang – .env mit GRAPH_CLIENT_ID/GRAPH_TENANT_ID und Geheimnis
# bzw. Anmeldung unter /versand im Modus delegiert):
#   venv\Scripts\python scripts\outlook_abgleich.py --postfach monteur@friondo.de --tage 14
#   … --muster          Betreff nur als Muster (Buchstaben → a, Ziffern → 0): keine Kundendaten
#   … --erweiterungen 5 zusätzlich die offenen Erweiterungen der ersten 5 Einträge lesen
#                       (/events/{id}/extensions – Kennzeichen fremder Systeme)
#   … --top 100         höchstens so viele Einträge (Standard 100)
# Ohne Token endet das Skript mit einem Hinweis (auf dem Entwicklungsrechner gibt es keinen
# Graph-Zugang). Der Betreff ist für den Abgleich nötig – die Ausgabe nicht ablegen.
import argparse
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))
os.chdir(PROJEKT)


def argumente() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vorab-Abgleich TAIFUN: Outlook-Kalender eines "
                                            "Monteurs nur lesen (Betreff, Kategorie, Kennzeichen)")
    p.add_argument("--postfach", required=True, help="UPN des Monteurs, z. B. vorname.nachname@friondo.de")
    p.add_argument("--tage", type=int, default=14, help="Zeitraum ab heute in Tagen (Standard 14)")
    p.add_argument("--ab", default="", help="Beginn JJJJ-MM-TT (Standard heute)")
    p.add_argument("--top", type=int, default=100, help="höchstens so viele Einträge (Standard 100)")
    p.add_argument("--muster", action="store_true", help="Betreff nur als Muster ausgeben")
    p.add_argument("--erweiterungen", type=int, default=0,
                   help="offene Erweiterungen der ersten N Einträge zusätzlich lesen")
    return p.parse_args()


def muster(text: str) -> str:
    return re.sub(r"\d", "0", re.sub(r"[^\W\d_]", "a", text or ""))


def zeit(daten: dict | None) -> str:
    roh = ((daten or {}).get("dateTime") or "")[:16].replace("T", " ")
    zone = (daten or {}).get("timeZone") or ""
    return f"{roh} {zone}".strip()


def main() -> int:
    args = argumente()
    from app import graph_versand, outlook_sync
    if not graph_versand.konfiguriert():
        print("Abbruch: Graph ist nicht eingerichtet (GRAPH_CLIENT_ID fehlt in der .env).")
        return 2
    token = graph_versand._token()
    if token is None:
        print("Abbruch: kein Graph-Token – Modus anwendung braucht GRAPH_CLIENT_SECRET und den "
              "grünen Verbindungstest unter /versand, Modus delegiert die Anmeldung „Mit Microsoft "
              "anmelden“. Auf dem Entwicklungsrechner gibt es keinen Graph-Zugang.")
        return 3
    try:
        von = datetime.strptime(args.ab, "%Y-%m-%d") if args.ab else datetime.now()
    except ValueError:
        print("Abbruch: --ab erwartet JJJJ-MM-TT.")
        return 2
    von = von.replace(hour=0, minute=0, second=0, microsecond=0)
    bis = von + timedelta(days=max(1, args.tage))
    basis = graph_versand.basis_pfad(args.postfach)
    pfad = (f"{basis}/calendarView?startDateTime={von:%Y-%m-%dT%H:%M:%S}"
            f"&endDateTime={bis:%Y-%m-%dT%H:%M:%S}&$top={max(1, min(args.top, 500))}"
            "&$orderby=start/dateTime"
            "&$select=id,subject,categories,showAs,isAllDay,start,end,organizer,isOrganizer,"
            "createdDateTime,lastModifiedDateTime,singleValueExtendedProperties"
            "&$expand=singleValueExtendedProperties($filter=id%20eq%20'"
            + urllib.parse.quote(outlook_sync.PROPERTY_ID) + "')")
    print(f"Modus {graph_versand.modus()} · Postfach {args.postfach} · {von:%d.%m.%Y} bis {bis:%d.%m.%Y}"
          f" · nur lesend (GET calendarView)")
    try:
        antwort = graph_versand._graph_aufruf("GET", pfad, token)
    except graph_versand.GraphZugriffVerweigert as problem:
        print(f"Abbruch: {problem} – Postfach in die Zugriffsgruppe aufnehmen (docs/graph-einrichtung.md).")
        return 4
    except Exception as problem:   # noqa: BLE001 – Handlauf: Fehler nur ausgeben
        print(f"Abbruch: Graph-Abruf fehlgeschlagen: {type(problem).__name__}: {problem}")
        return 4
    eintraege = antwort.get("value", []) or []
    print(f"{len(eintraege)} Einträge\n")
    print("| Beginn | Ende | Betreff | Kategorien | showAs | Ersteller (organizer) | selbst | "
          "Friondo-Kennzeichen | angelegt | geändert |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for e in eintraege:
        betreff = (e.get("subject") or "").replace("|", "/")
        if args.muster:
            betreff = muster(betreff)
        organizer = ((e.get("organizer") or {}).get("emailAddress") or {}).get("address", "")
        kennzeichen = outlook_sync._kennzeichen_aus_event(e) or "–"
        print(f"| {zeit(e.get('start'))}{' (ganztägig)' if e.get('isAllDay') else ''} | {zeit(e.get('end'))} "
              f"| {betreff} | {', '.join(e.get('categories') or []) or '–'} | {e.get('showAs', '')} "
              f"| {organizer or '–'} | {'ja' if e.get('isOrganizer') else 'nein'} | {kennzeichen} "
              f"| {(e.get('createdDateTime') or '')[:16]} | {(e.get('lastModifiedDateTime') or '')[:16]} |")
    if args.erweiterungen:
        print("\nOffene Erweiterungen (Kennzeichen fremder Systeme) der ersten Einträge:")
        for e in eintraege[:max(0, args.erweiterungen)]:
            try:
                erw = graph_versand._graph_aufruf(
                    "GET", f"{basis}/events/{urllib.parse.quote(e.get('id', ''))}/extensions", token)
                namen = [x.get("extensionName") or x.get("id", "?") for x in erw.get("value", []) or []]
            except Exception as problem:   # noqa: BLE001
                namen = [f"Fehler: {type(problem).__name__}"]
            betreff = muster(e.get("subject") or "") if args.muster else (e.get("subject") or "")
            print(f"- {zeit(e.get('start'))} {betreff[:60]}: {', '.join(namen) or 'keine'}")
    print("\nErgebnis in docs/outlook-sync.md (Abschnitt 1, Tabelle) eintragen; Entscheidung Andreas: "
          "sichtbar für TAIFUN (gleiches Muster) oder nicht (eigene Kategorie).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
