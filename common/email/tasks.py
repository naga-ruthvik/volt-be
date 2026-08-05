from celery import shared_task

from .service import send_otp_email


@shared_task()
def send_otp_email_task(email: str, otp: str):
    print(f"OTP for {email}: {otp}")
    send_otp_email(email, otp)
