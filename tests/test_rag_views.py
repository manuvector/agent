# tests/test_rag_views.py
import json
from django.urls import reverse
from rag.models import RagChunk

def test_list_files_empty(auth_client):
    r = auth_client.get(reverse("list_files"))
    assert r.status_code == 200
    assert json.loads(r.content) == []

def test_list_files_similarity(auth_client, mocker, user):
    RagChunk.objects.create(
        user=user, file_id="x", file_name="α.txt", chunk_idx=0,
        char_start=0, char_end=5, embedding=[0.1]*1536
    )
    mocker.patch("rag.views._embed_query", return_value=[0.0]*1536)
    r = auth_client.get(reverse("list_files") + "?q=anything")
    data = r.json()
    assert data[0]["file_name"] == "α.txt"
    assert "distance" in data[0]

