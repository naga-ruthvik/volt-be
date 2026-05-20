from django.contrib import admin

# Register your models here.
from .models import OTPSessions, User

admin.site.register(OTPSessions)
admin.site.register(User)
