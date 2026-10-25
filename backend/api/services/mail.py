from datetime import UTC, datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from api.configs.config import Setting
from jinja2 import Environment, FileSystemLoader, Template
from api.configs import logging as logSVC


base_dir = os.path.dirname(os.path.abspath(__file__))
html_folder_path = os.path.join(base_dir, "../html/email")
env = Environment(loader=FileSystemLoader(html_folder_path))


def send_email(receiver_email: str | list[str], message_text: str, object: str) -> bool:
    """Envoyer un e-mail HTML à une adresse ou une liste d’adresses.

    Les espaces entourant les adresses sont supprimés et les doublons retirés.
    Une chaîne représente une seule adresse ; utiliser une liste pour plusieurs
    destinataires. Retourne False si la liste est vide, si un destinataire est
    refusé ou si l’envoi SMTP échoue. Aucun envoi n’est effectué sans destinataire.
    """
    addresses = [receiver_email] if isinstance(receiver_email, str) else receiver_email
    if not isinstance(addresses, list) or not all(
        isinstance(item, str) for item in addresses
    ):
        return False
    recipients = list(
        dict.fromkeys(address.strip() for address in addresses if address.strip())
    )
    if not recipients:
        return False

    from_email = f"notification@{Setting.EMAIL_DOMAIN}"
    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = ", ".join(recipients)
    message["Subject"] = object
    message.attach(MIMEText(str(message_text), "html", "utf-8"))

    try:
        with smtplib.SMTP(Setting.EMAIL_HOST, Setting.EMAIL_PORT, timeout=10) as server:
            server.starttls()
            server.login(user=Setting.EMAIL_USERNAME, password=Setting.EMAIL_PASSWORD)
            refused = server.sendmail(from_email, recipients, message.as_string())
        if refused:
            logSVC.logError(
                "Certains destinataires ont été refusés par le serveur SMTP."
            )
            return False
        logSVC.logInfo(f"E-mail envoyé à {len(recipients)} destinataire(s).")
        return True
    except Exception:
        logSVC.logError("Échec de l’envoi de l’e-mail par SMTP.")
        return False


def send_app_exception_to_admin(
    email_list: list[str] | None = None,
    error_message: str = None,
    error_type: str = "Exception | Error | Bug",
) -> bool:
    """
    Envoyer individuellement une alerte HTML aux administrateurs.

    Retourne False si au moins un envoi échoue ; tous les destinataires sont traités.
    """

    try:
        params = {
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S"),
            "app_name": Setting.APP_NAME,
        }
        template: Template = env.get_template("error500_admin_mail.html")
        recipients = (
            email_list if email_list is not None else Setting.ADMINS_EMAIL.split(",")
        )
        success = True
        for email in recipients:
            message = template.render(**params)
            sent = send_email(
                receiver_email=email,
                message_text=message,
                object=f"{Setting.APP_NAME} - Error 500",
            )
            success = sent and success
        return success if recipients else False
    except Exception as e:
        print(e)
        logSVC.logError(e)
        return False


def send_password_reset(
    receiver: str, link: str, minutes: int, language: str, app_name: str
) -> bool:
    """Envoyer le lien de récupération dans la langue demandée, sans journaliser son contenu."""
    english = language == "en"
    message = env.get_template("password_reset.html").render(
        app_name=app_name,
        link=link,
        minutes=minutes,
        english=english,
    )
    subject = "Reset your password" if english else "Réinitialiser votre mot de passe"
    return send_email(receiver, message, f"{app_name} — {subject}")


def send_password_changed(receiver: str, language: str, app_name: str) -> bool:
    """Notifier la modification sans transmettre de mot de passe ni de jeton."""
    english = language == "en"
    message = env.get_template("password_changed.html").render(
        app_name=app_name, english=english
    )
    subject = "Password changed" if english else "Mot de passe modifié"
    return send_email(receiver, message, f"{app_name} — {subject}")


def send_recovery_email_changed(receiver: str, language: str, app_name: str) -> bool:
    """Prévenir l’ancienne adresse après un changement des coordonnées de récupération."""
    english = language == "en"
    message = env.get_template("recovery_email_changed.html").render(
        app_name=app_name, english=english
    )
    subject = (
        "Recovery email changed" if english else "Adresse de récupération modifiée"
    )
    return send_email(receiver, message, f"{app_name} — {subject}")


def send_email_verification(
    receiver: str, link: str, minutes: int, language: str, app_name: str
) -> bool:
    """Envoyer un lien de confirmation, dans la langue du parcours d’inscription."""
    english = language == "en"
    message = env.get_template("email_verification.html").render(
        app_name=app_name, link=link, minutes=minutes, english=english
    )
    subject = (
        "Confirm your email address" if english else "Confirmez votre adresse e-mail"
    )
    return send_email(receiver, message, f"{app_name} — {subject}")
