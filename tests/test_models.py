# tests/test_models.py
import pytest
from django.db import IntegrityError
from agent.models import DriveAuth
from rag.models import RagChunk

def test_ragchunk_uniqueness(user):
    c1 = RagChunk.objects.create(
        user=user, file_id="foo", file_name="doc", chunk_idx=0,
        char_start=0, char_end=10, embedding=[0.1]*1536
    )
    payload = {
    "user": c1.user,
    "file_id": c1.file_id,
    "file_name": c1.file_name,
    "chunk_idx": c1.chunk_idx,
    "char_start": c1.char_start,
    "char_end": c1.char_end,
    "embedding": c1.embedding,
    }
    with pytest.raises(IntegrityError):
        RagChunk.objects.create(**payload)

def test_driveauth_expired_property(user):
    auth = DriveAuth.objects.create(
        user=user, access_token="tok", expiry_ts=1_000_000_000
    )
    assert auth.expired is True
    auth.expiry_ts = 9_999_999_999
    assert auth.expired is False

