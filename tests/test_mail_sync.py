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


if __name__ == "__main__":
    unittest.main()
