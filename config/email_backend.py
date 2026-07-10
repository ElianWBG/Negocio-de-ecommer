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

                # Adjuntos (ej. la factura XML)
                import base64
                from sendgrid.helpers.mail import (
                    Attachment, Disposition, FileContent, FileName, FileType,
                )
                for att in msg.attachments:
                    if isinstance(att, tuple):
                        filename, content, mimetype = att
                        raw = content.encode("utf-8") if isinstance(content, str) else content
                    else:  # MIMEBase
                        filename = att.get_filename() or "adjunto"
                        raw = att.get_payload(decode=True) or b""
                        mimetype = att.get_content_type()
                    mail.add_attachment(Attachment(
                        FileContent(base64.b64encode(raw).decode("ascii")),
                        FileName(filename),
                        FileType(mimetype or "application/octet-stream"),
                        Disposition("attachment"),
                    ))

                sg.send(mail)
                sent += 1
            except Exception as e:
                if not self.fail_silently:
                    raise e
        return sent