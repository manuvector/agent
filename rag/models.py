# rag/models.py
from django.conf import settings
from django.db import models
from pgvector.django import VectorField

class RagChunk(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file_id    = models.CharField(max_length=128)
    file_name  = models.CharField(max_length=512)
    chunk_idx  = models.IntegerField()
    char_start = models.IntegerField()
    char_end   = models.IntegerField()
    embedding  = VectorField(dimensions=1536)  # <-- use "dimensions", not "dim"

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["file_id"]),
        ]
        unique_together = (("user", "file_id", "chunk_idx"),)

    def __str__(self):
        return f"{self.file_name} [{self.char_start}:{self.char_end}]"

