# Outlook-Versand (Phase 8): öffnet über COM einen E-Mail-Entwurf im klassischen
# Outlook-Desktop mit Betreff, Standardtext und Angebots-PDF als Anhang.
# Gesendet wird vom Vertrieb selbst; das Tool verschickt nichts automatisch.
# Fallback bei fehlendem Outlook: Hinweis + PDF-Download.

from pathlib import Path

from app.models import Angebot, Kunde


def _anrede(kunde: Kunde) -> str:
    if kunde.anrede == "Herr" and kunde.nachname:
        return f"Sehr geehrter Herr {kunde.nachname},"
    if kunde.anrede == "Frau" and kunde.nachname:
        return f"Sehr geehrte Frau {kunde.nachname},"
    if kunde.anrede == "Familie" and kunde.nachname:
        return f"Sehr geehrte Familie {kunde.nachname},"
    return "Sehr geehrte Damen und Herren,"


def standardtext(kunde: Kunde, angebot: Angebot) -> str:
    return (f"{_anrede(kunde)}\n\n"
            f"vielen Dank für Ihr Interesse an einer Wärmepumpe der Friondo GmbH.\n\n"
            f"Anbei erhalten Sie Ihr individuelles Angebot {angebot.nummer} "
            f"als PDF-Datei. Wir halten uns freibleibend 30 Tage an dieses "
            f"Angebot gebunden.\n\n"
            f"Bei Fragen stehen wir Ihnen jederzeit gerne zur Verfügung – "
            f"telefonisch unter 0203 - 3965 710 oder per E-Mail an info@friondo.de.\n\n"
            f"Mit freundlichen Grüßen\n"
            f"Ihr Friondo-Team\n\n"
            f"Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg\n"
            f"www.friondo.de")


def entwurf_oeffnen(kunde: Kunde, angebot: Angebot, pdf_pfad: Path) -> tuple[bool, str]:
    """Erzeugt den Outlook-Entwurf und zeigt ihn an. Liefert (erfolg, meldung)."""
    if not kunde.email:
        return False, "Der Kunde hat keine E-Mail-Adresse – bitte zuerst in der Kundenverwaltung ergänzen."
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # olMailItem
            mail.To = kunde.email
            mail.Subject = f"Ihr Wärmepumpen-Angebot {angebot.nummer} der Friondo GmbH"
            mail.Body = standardtext(kunde, angebot)
            mail.Attachments.Add(str(pdf_pfad))
            mail.Display()  # Entwurf anzeigen – Versand erfolgt manuell durch den Vertrieb
        finally:
            pythoncom.CoUninitialize()
        return True, ("Outlook-Entwurf geöffnet – bitte prüfen und senden. "
                      "Danach hier den Status auf „Versendet“ setzen.")
    except Exception as fehler:  # COM nicht verfügbar / kein klassisches Outlook
        return False, ("Outlook konnte nicht geöffnet werden (klassisches "
                       f"Outlook-Desktop erforderlich): {fehler}. "
                       "Alternativ das PDF herunterladen und manuell versenden.")
