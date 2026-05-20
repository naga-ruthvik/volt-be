from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class EmailService:
    @staticmethod
    def send_email(
        subject,
        recipient_email,
        template_name,
        context,
    ):

        if template_name:
            html_content = render_to_string(template_name, context)
            email = EmailMultiAlternatives(
                subject=subject,
                body="",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )
            email.attach_alternative(html_content, "text/html")
        else:
            email = EmailMultiAlternatives(
                subject=subject,
                body=f"otp for the email {recipient_email} is {context.get('otp')}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )

        email.send()

    @staticmethod
    def send_otp_email(email, otp):
        EmailService.send_email(
            subject="OTP Verification",
            recipient_email=email,
            # TODO: add a html template to send the email
            template_name="",
            context={"otp": otp},
        )
