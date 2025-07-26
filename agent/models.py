# agent/models.py
import time
from django.conf import settings
from django.db import models


class DriveAuth(models.Model):
    user          = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_token  = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expiry_ts     = models.FloatField()

    @property
    def expired(self) -> bool:
        return self.expiry_ts <= time.time() + 60

    def __str__(self):
        return f"DriveAuth({self.user})"


class NotionAuth(models.Model):  # ← NEW
    user          = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_token  = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    workspace_id  = models.CharField(max_length=64)
    expiry_ts     = models.FloatField()

    @property
    def expired(self) -> bool:
        return self.expiry_ts <= time.time() + 60

    def __str__(self):
        return f"NotionAuth({self.user})"


class UserFile(models.Model):
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file_id = models.CharField(max_length=128)
    name    = models.CharField(max_length=512)

    class Meta:
        unique_together = ("user", "file_id")

    def __str__(self):
        return f"{self.user} → {self.name}"

