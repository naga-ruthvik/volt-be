from datetime import timedelta

from django.db import models
from django.utils import timezone

# Create your models here.


def get_expiry_time():
    return timezone.now() + timedelta(minutes=15)


class OTPSessions(models.Model):
    id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=254)
    otp = models.CharField(max_length=6)
    created_at = models.DateField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_expiry_time)
    verified = models.BooleanField(default=False)
    is_valid = models.BooleanField(default=False)

    def __str__(self):
        return self.email[:6] + "-" + self.otp[2:]
