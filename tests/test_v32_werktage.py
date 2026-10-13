# v32 (PLAN_V19 Phase 162): Werktagsrechner app/werktage.py – Kontrollwerte des Plans mit
# dem ECHTEN Kalender 2026 (Rückfrage im Bericht M): der Plan nennt „Fr 10.10.2026“, der
# 10.10.2026 ist ein Samstag; Fr 09.10. + 3 = Mi 14.10. (Sa 10.10. + 3 ebenso); Mi 30.09.
# + 3 = Mo 05.10. (3.10. ist 2026 ein Samstag, der Plan nennt Di 06.10.); Do 17.12. + 3 =
# Di 22.12. (wie im Plan). Dazu die Nachfass-Rechnung aus app/nachfassen.py (Parameter).
import unittest
from datetime import date, datetime

from app import nachfassen, werktage
from app.db import SessionLocal
from app.models import Kunde


class WerktageKontrollwerte(unittest.TestCase):
    def test_plan_kontrollwerte_mit_echtem_kalender(self):
        self.assertEqual(date(2026, 10, 10).weekday(), 5, "10.10.2026 ist ein Samstag")
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 9), 3), date(2026, 10, 14))   # Fr + 3 = Mi
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 10), 3), date(2026, 10, 14))  # Sa + 3 = Mi
        self.assertEqual(werktage.plus_werktage(date(2026, 9, 30), 3), date(2026, 10, 5))    # 3.10. = Sa
        self.assertEqual(werktage.plus_werktage(date(2026, 12, 17), 3), date(2026, 12, 22))  # Do + 3 = Di

    def test_mfh_und_parameter_sechs(self):
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 9), 5), date(2026, 10, 16))   # MFH: Fr + 5 = Fr
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 9), 6), date(2026, 10, 19))   # Parameter 6 → Mo
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 13), 7), date(2026, 10, 22))  # Bestellung +7 (N)

    def test_feiertage_und_jahreswechsel(self):
        # Mi 23.12.2026 + 3: Do 24.12. (Werktag), Fr 25.12./Sa 26.12. Feiertag/Wochenende,
        # Mo 28.12., Di 29.12. → Di 29.12.2026
        self.assertEqual(werktage.plus_werktage(date(2026, 12, 23), 3), date(2026, 12, 29))
        # Do 31.12.2026 + 1 → Mo 04.01.2027 (1.1. Feiertag, Wochenende)
        self.assertEqual(werktage.plus_werktage(date(2026, 12, 31), 1), date(2027, 1, 4))
        # Ostern 2027: 28.03.2027 → Karfreitag 26.03., Ostermontag 29.03.
        self.assertEqual(werktage.ostersonntag(2027), date(2027, 3, 28))
        self.assertEqual(werktage.plus_werktage(date(2027, 3, 25), 1), date(2027, 3, 30))
        self.assertEqual(werktage.plus_werktage(datetime(2026, 10, 9, 15, 30), 3), date(2026, 10, 14))
        self.assertEqual(werktage.plus_werktage(date(2026, 10, 10), 0), date(2026, 10, 10))
        self.assertFalse(werktage.ist_werktag(date(2026, 11, 1)))   # Allerheiligen (So)
        self.assertTrue(werktage.ist_werktag(date(2026, 11, 2)))


class NachfassRechnung(unittest.TestCase):
    """nachfassen.nachfass_datum liest die Parameter (Standard 3/5) und die Objektart."""

    def test_standard_und_mfh(self):
        s = SessionLocal()
        try:
            efh = Kunde(nachname="V32M-Werktage", objektart=None)
            mfh = Kunde(nachname="V32M-Werktage", objektart="MFH")
            self.assertFalse(nachfassen.ist_mfh(efh))
            self.assertTrue(nachfassen.ist_mfh(mfh))
            self.assertEqual(nachfassen.werktage_parameter(s, mfh=False), 3)
            self.assertEqual(nachfassen.werktage_parameter(s, mfh=True), 5)
            self.assertEqual(nachfassen.nachfass_datum(s, efh, date(2026, 10, 9)), date(2026, 10, 14))
            self.assertEqual(nachfassen.nachfass_datum(s, mfh, date(2026, 10, 9)), date(2026, 10, 16))
            self.assertEqual(nachfassen.nachfass_datum(s, None, datetime(2026, 10, 9, 17, 5)), date(2026, 10, 14))
        finally:
            s.rollback()
            s.close()

    def test_parameter_robust(self):
        self.assertEqual(nachfassen._ganzzahl("x", 3), 3)
        self.assertEqual(nachfassen._ganzzahl("6", 3), 6)
        self.assertEqual(nachfassen._ganzzahl("-2", 3), 0)
        self.assertEqual(nachfassen._ganzzahl("999", 3), nachfassen.WERKTAGE_MAX)


if __name__ == "__main__":
    unittest.main()
