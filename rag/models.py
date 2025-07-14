from django.db import models
from pgvector.django import VectorField

class Document(models.Model):
    content   = models.TextField()
    embedding = VectorField(dimensions=1536)   # pgvector column
    created   = models.DateTimeField(auto_now_add=True)
