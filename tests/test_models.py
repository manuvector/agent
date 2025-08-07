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
    with pytest.raises(IntegrityError):
        RagChunk.objects.create(**c1.__dict__, id=None)  # duplicate key

def test_driveauth_expired_property(user):
    auth = DriveAuth.objects.create(
        user=user, access_token="tok", expiry_ts=1_000_000_000
    )
    assert auth.expired is True
    auth.expiry_ts = 9_999_999_999
    assert auth.expired is False

