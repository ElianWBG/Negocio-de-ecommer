import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


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