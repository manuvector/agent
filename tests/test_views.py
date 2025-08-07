# tests/test_views.py
import json
import responses
from django.urls import reverse
from freezegun import freeze_time

@responses.activate
def test_get_csrf_token(client):
    r = client.get(reverse("get_csrf_token"))
    assert r.status_code == 200
    assert "csrfToken" in r.json()

def test_chat_requires_message(auth_client):
    url = reverse("chat_completion")
    resp = auth_client.post(url, json.dumps({}), content_type="application/json")
    assert resp.json()["response"].startswith("Please enter")

@freeze_time("2025-08-07")
@responses.activate
def test_chat_completion_basic(auth_client, mocker):
    # Patch vector search to avoid heavy PG setup
    mocker.patch("agent.views.get_relevant_context", return_value=[])
    # Patch OpenAI
    openai_mock = mocker.patch("agent.views.client.chat.completions.create")
    openai_mock.return_value.choices[0].message.content = "hi back"
    url = reverse("chat_completion")
    resp = auth_client.post(
        url,
        json.dumps({"message": "hello"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["response"] == "hi back"

