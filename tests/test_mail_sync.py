# Tests für den Mail-Verlauf (Phase 27) – mit Mock-Daten statt echtem
# Graph-Token: geprüft wird die Verarbeitung (Dedup, eingehend/ausgehend,
# Konversations-Filter) gegen eine In-Memory-Datenbank.
import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import mail_sync
from app.db import Base
from app.models import Angebot, AngebotsMail


def _nachricht(graph_id: str, absender: str, name: str = "",
               conversation_id: str = "konv-1",
               empfangen: str = "2026-08-14T09:30:00Z",
               betreff: str = "AW: Ihr Wärmepumpen-Angebot AN-C-260001") -> dict:
    return {
        "id": graph_id,
        "conversationId": conversation_id,
        "subject": betreff,
        "bodyPreview": "Vielen Dank, wir haben noch eine Frage ...",
        "receivedDateTime": empfangen,
        "from": {"emailAddress": {"address": absender, "name": name}},
    }


class TestMailVerarbeitung(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.angebot = Angebot(nummer="AN-C-260001", kunde_id=1,
                               status="Versendet",
                               graph_conversation_id="konv-1")
        self.session.add(self.angebot)
        self.session.commit()

    def test_neue_nachrichten_werden_gespeichert(self):
        nachrichten = [
            _nachricht("m1", "info@friondo.de", "Friondo Innendienst"),
            _nachricht("m2", "erika@beispiel.de", "Erika Beispiel"),
        ]
        neu = mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                                nachrichten, "info@friondo.de")
        self.session.commit()
        self.assertEqual(neu, 2)
        mails = self.session.query(AngebotsMail).order_by(AngebotsMail.graph_id).all()
        self.assertEqual(len(mails), 2)
        # eigene Mail = ausgehend, Kundenmail = eingehend (Antwort)
        self.assertFalse(mails[0].eingehend)
        self.assertTrue(mails[1].eingehend)
        self.assertEqual(mails[1].von_name, "Erika Beispiel")
        self.assertEqual(mails[1].empfangen_am,
                         datetime.datetime(2026, 8, 14, 9, 30))

    def test_dedup_ueber_graph_id(self):
        nachrichten = [_nachricht("m1", "erika@beispiel.de")]
        mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                          nachrichten, "info@friondo.de")
        self.session.commit()
        # zweiter Lauf mit derselben Nachricht ändert nichts
        neu = mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                                nachrichten, "info@friondo.de")
        self.session.commit()
        self.assertEqual(neu, 0)
        self.assertEqual(self.session.query(AngebotsMail).count(), 1)

    def test_fremde_konversation_wird_verworfen(self):
        # Betreff-Suche kann Fremdtreffer liefern – bei bekannter
        # Konversations-ID werden andere Konversationen ignoriert
        nachrichten = [_nachricht("m9", "spam@anderswo.de",
                                  conversation_id="konv-FREMD")]
        neu = mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                                nachrichten, "info@friondo.de")
        self.assertEqual(neu, 0)

    def test_fallback_ohne_konversations_id(self):
        # ohne gespeicherte Konversations-ID (ältere Angebote) zählt der Treffer
        self.angebot.graph_conversation_id = None
        nachrichten = [_nachricht("m3", "erika@beispiel.de",
                                  conversation_id="konv-egal")]
        neu = mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                                nachrichten, "info@friondo.de")
        self.assertEqual(neu, 1)

    def test_gross_kleinschreibung_postfach(self):
        nachrichten = [_nachricht("m4", "Info@Friondo.de")]
        mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                          nachrichten, "info@friondo.de")
        mail = self.session.query(AngebotsMail).one()
        self.assertFalse(mail.eingehend)

    # --- Phase 31: Versand-Erkennung + Shared Mailbox --------------------

    def test_entwurf_wird_nicht_gespeichert(self):
        entwurf = _nachricht("d1", "angebot@friondo.de"); entwurf["isDraft"] = True
        neu = mail_sync.nachrichten_verarbeiten(self.session, self.angebot,
                                                [entwurf], {"angebot@friondo.de"})
        self.assertEqual(neu, 0)

    def test_versand_erkannt_nur_bei_gesendeter_nachricht(self):
        self.angebot.status = "Versand vorbereitet"
        eigene = {"angebot@friondo.de", "ida@friondo.de"}
        entwurf = _nachricht("d1", "angebot@friondo.de"); entwurf["isDraft"] = True
        # nur Entwurf vorhanden → bleibt „Versand vorbereitet“
        self.assertFalse(mail_sync.versand_erkennen(self.session, self.angebot, [entwurf], eigene))
        self.assertEqual(self.angebot.status, "Versand vorbereitet")
        # Kundenantwort allein reicht nicht (nicht von uns)
        antwort = _nachricht("k1", "erika@beispiel.de"); antwort["sentDateTime"] = "2026-08-14T10:00:00Z"
        self.assertFalse(mail_sync.versand_erkennen(self.session, self.angebot, [antwort], eigene))
        # gesendete Nachricht von angebot@ → Versendet
        gesendet = _nachricht("s1", "angebot@friondo.de")
        gesendet["isDraft"] = False; gesendet["sentDateTime"] = "2026-08-14T09:31:00Z"
        self.assertTrue(mail_sync.versand_erkennen(self.session, self.angebot,
                                                   [entwurf, gesendet], eigene))
        self.assertEqual(self.angebot.status, "Versendet")
        # zweiter Lauf ändert nichts mehr
        self.assertFalse(mail_sync.versand_erkennen(self.session, self.angebot, [gesendet], eigene))

    def test_versand_erkennung_nur_im_status_vorbereitet(self):
        self.angebot.status = "Entwurf"
        gesendet = _nachricht("s1", "angebot@friondo.de"); gesendet["sentDateTime"] = "2026-08-14T09:31:00Z"
        self.assertFalse(mail_sync.versand_erkennen(self.session, self.angebot, [gesendet],
                                                    {"angebot@friondo.de"}))
        self.assertEqual(self.angebot.status, "Entwurf")

    def test_eigene_adressen_mehrere(self):
        # Mail von angebot@ (Shared Mailbox) gilt als ausgehend, auch wenn das
        # angemeldete Konto ida@ ist
        nachrichten = [_nachricht("m5", "angebot@friondo.de"),
                       _nachricht("m6", "erika@beispiel.de")]
        mail_sync.nachrichten_verarbeiten(self.session, self.angebot, nachrichten,
                                          {"ida@friondo.de", "angebot@friondo.de"})
        mails = {m.graph_id: m for m in self.session.query(AngebotsMail)}
        self.assertFalse(mails["m5"].eingehend)
        self.assertTrue(mails["m6"].eingehend)

    def test_graph_pfad_shared_mailbox(self):
        self.assertEqual(mail_sync._basis(""), "/me")
        self.assertEqual(mail_sync._basis("angebot@friondo.de"), "/users/angebot%40friondo.de")


if __name__ == "__main__":
    unittest.main()
