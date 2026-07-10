import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class SendGridEmailBackend(BaseEmailBackend):
    def open(self):
        pass

    def close(self):
        pass

    def send_messages(self, email_messages):
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sent = 0
        for msg in email_messages:
            try:
                html_body = None
                for content, mimetype in getattr(msg, 'alternatives', []):
                    if mimetype == 'text/html':
                        html_body = content
                        break
                mail = Mail(
                    from_email=msg.from_email,
                    to_emails=msg.to,
                    subject=msg.subject,
                    plain_text_content=msg.body,
                    html_content=html_body,
                )
                sg.send(mail)
                sent += 1
            except Exception as e:
                if not self.fail_silently:
                    raise e
        return sent


class ResendEmailBackend(BaseEmailBackend):
    def open(self):
        resend.api_key = settings.RESEND_API_KEY

    def close(self):
        pass

    def send_messages(self, email_messages):
        self.open()
        sent = 0
        for msg in email_messages:
            try:
                resend.Emails.send({
                    "from": msg.from_email,
                    "to": msg.to,
                    "subject": msg.subject,
                    "text": msg.body,
                })
                sent += 1
            except Exception as e:
                if not self.fail_silently:
                    raise e
        return sent