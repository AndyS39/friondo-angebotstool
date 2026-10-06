# v27 (PLAN_V17 Phase 130): Die Login-Härtung zählt Fehlversuche je IP (30 je
# 15 Minuten). Im Sammellauf melden sich viele Testklassen vom selben TestClient
# („testclient“) an – damit sich Testmodule nicht gegenseitig aussperren, wird der
# IP-Zähler je Test zurückgesetzt. Tests der IP-Grenze selbst (test_v27_login)
# setzen ihn in setUp ohnehin zurück.
#
# Diagnose „Pool-Leck“ (nur mit Umgebungsvariable POOL_LECK_DIAGNOSE=1): merkt sich
# je entnommener Pool-Verbindung den Aufruf-Stack und schreibt am Ende jedes
# Testmoduls die noch nicht zurückgegebenen Verbindungen nach
# diagnose/test_v27_final/pool_leck.txt – so findet man Tests oder Code, die eine
# Sitzung (und damit die SQLite-Schreibsperre) offen lassen.
import os
import traceback
from pathlib import Path

import pytest

_STACKS: dict[int, str] = {}
_DIAGNOSE = os.getenv("POOL_LECK_DIAGNOSE", "") == "1"


def pytest_configure(config):
    if not _DIAGNOSE:
        return
    from sqlalchemy import event
    from app import db

    @event.listens_for(db.engine, "checkout")
    def _entnommen(dbapi_con, con_record, con_proxy):
        _STACKS[id(con_record)] = "".join(traceback.format_stack(limit=25))

    @event.listens_for(db.engine, "checkin")
    def _zurueck(dbapi_con, con_record):
        _STACKS.pop(id(con_record), None)


@pytest.fixture(autouse=True, scope="function")
def _ip_zaehler_frei():
    from app import auth
    auth.ip_zaehler_zuruecksetzen()
    yield
    auth.ip_zaehler_zuruecksetzen()


@pytest.fixture(autouse=True, scope="module")
def _pool_leck_pruefen(request):
    yield
    if not _DIAGNOSE:
        return
    from app import db
    offen = db.engine.pool.checkedout()
    if offen <= 0:
        return
    ziel = Path("diagnose/test_v27_final/pool_leck.txt")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("a", encoding="utf-8") as f:
        f.write(f"\n=== nach Modul {request.node.name}: {offen} Verbindung(en) offen ===\n")
        for stack in list(_STACKS.values()):
            f.write(stack + "\n---\n")
