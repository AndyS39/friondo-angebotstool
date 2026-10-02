# Lead-Management V2 (v23) – Router boards (PLAN_LEAD_V2). Eigener Router mit
# demselben Präfix; in app/main.py VOR dem V1-Router eingebunden, damit gleiche
# Pfade hier Vorrang haben. Wird in der zugehörigen Phase gefüllt.

from fastapi import APIRouter

router = APIRouter(prefix="/lead-management")
