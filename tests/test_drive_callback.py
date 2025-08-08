import pytest
from django.urls import reverse
from unittest.mock import patch

@pytest.mark.django_db
def test_drive_callback_saves_and_redirects(client, django_user_model):
    user = django_user_model.objects.create_user("u","u@x.com","p")
    client.force_login(user)
    with patch("agent.views.requests.post") as req:
        req.return_value.json.return_value = {
            "access_token":"ya29",
            "refresh_token":"r",
            "expires_in":3600
        }
        r = client.get(reverse("drive_callback"), {"code": "abc"})
    assert r.status_code in (301, 302)
    # If you redirect to "/": 
    # assert r["Location"] == "/"
    # If you keep "/chat", also make sure "/chat" is routed to your SPA:
    assert r["Location"] in {"/", "/chat"}

    from agent.models import DriveAuth
    assert DriveAuth.objects.filter(user=user, access_token="ya29").exists()

@pytest.mark.django_db
def test_token_endpoint_not_top_level_redirect_for_json(client):
    r = client.get(reverse("drive_token"), HTTP_ACCEPT="application/json")
    # If using the wrapper:
    assert r.status_code == 401
    assert r["Content-Type"].startswith("application/json")

