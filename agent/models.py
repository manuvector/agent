# agent/models.py
import time
from django.conf import settings
from django.db import models


class DriveAuth(models.Model):
    """
    Stores the user’s Google OAuth tokens.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expiry_ts = models.FloatField()  # seconds since epoch

    @property
    def expired(self) -> bool:
        # 60-second grace so we refresh early
        return self.expiry_ts <= time.time() + 60

    def __str__(self):
        return f"DriveAuth({self.user})"


class UserFile(models.Model):
    """
    One row per Google-Drive file the user picked in Google Picker.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file_id = models.CharField(max_length=128)
    name = models.CharField(max_length=512)

    class Meta:
        unique_together = ("user", "file_id")

    def __str__(self):
        return f"{self.user} → {self.name}"

