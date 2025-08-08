# tests/test_drive_ingest.py
import json
import time
import pytest
import responses
from django.urls import reverse

from agent.drive_ingest import ingest_drive_file, _chunk_text

def test_chunk_text_exact():
    txt = "A" * 3500
    chunks = _chunk_text(txt, size=1000, overlap=100)
    # expected chunk starts: 0, 900, 1800, 2700
    starts = [s for _, s, *_ in chunks]
    assert starts == [0, 900, 1800, 2700]

@pytest.mark.django_db
@responses.activate
def test_ingest_drive_file_minimal(user, mocker):
    # 1) stub Drive metadata
    metadata_url = "https://www.googleapis.com/drive/v3/files/abc"
    responses.add(
        responses.GET,
        metadata_url,
        json={"name": "doc.txt", "mimeType": "text/plain"},
        match=[responses.matchers.query_param_matcher({"fields": "name,mimeType"})],
        status=200,
    )
    # 2) stub file download
    download_url = metadata_url + "?alt=media"
    responses.add(responses.GET, download_url, body=b"hello world", status=200)

    # Mock embedding call → deterministic vector
    mocker.patch("agent.drive_ingest._embed", return_value=[0.0] * 1536)

    ingest_drive_file(user, "abc", access_token="tok")

    from rag.models import RagChunk
    qs = RagChunk.objects.filter(user=user, file_id="abc")
    assert qs.count() == 1
    chunk = qs.first()
    assert chunk.char_end == len("hello world")

@pytest.mark.django_db
def test_store_selected_files_ingests(client, django_user_model):
    from agent.models import DriveAuth
    user = django_user_model.objects.create_user("u", "u@x.com", "p")
    client.force_login(user)
    DriveAuth.objects.create(user=user, access_token="tok", expiry_ts=time.time() + 3600)

    from unittest.mock import patch
    with patch("agent.views.ingest_drive_file") as ingest_mock:
        payload = {"files": [{"id": "file1", "name": "Doc 1"}]}
        res = client.post(
            reverse("store_selected_files"),
            data=json.dumps(payload),
            content_type="application/json",
        )
    assert res.status_code == 200
    ingest_mock.assert_called_once_with(user, "file1", "tok")

