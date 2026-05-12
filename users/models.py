import uuid
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


# Create your models here.
def get_expiry_time():
    return timezone.now() + timedelta(minutes=10)


class OTPSessions(models.Model):
    id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=254)
    otp = models.CharField(max_length=128)  # Increased length for hashed OTP
    created_at = models.DateField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_expiry_time)
    verified = models.BooleanField(default=False)
    is_valid = models.BooleanField(default=False)

    class Meta:
        db_table = "otp_sessions"

    def __str__(self):
        return self.email[:6] + "-[MASKED-OTP]"


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password) if password else user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(unique=True)
    token_version = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.username

    def invalidate_all_tokens(self):
        """Invalidate all existing JWT tokens (single session enforcement)"""
        self.token_version += 1
        self.save(update_fields=["token_version"])
