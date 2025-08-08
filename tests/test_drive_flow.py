import time, pytest
from django.urls import reverse
from unittest.mock import patch

@pytest.mark.django_db
def test_drive_callback_then_drive_token(client, django_user_model, settings):
    user = django_user_model.objects.create_user("u", "u@x.com", "p")
    client.force_login(user)

    cb_url = reverse("drive_callback")
    with patch("agent.views.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "access_token": "ya29.token",
            "refresh_token": "1//refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        res = client.get(cb_url, {"code": "abc"})
        assert res.status_code in (301, 302)

    # now token endpoint should return JSON token
    res = client.get(reverse("drive_token"))
    assert res.status_code == 200
    assert res.json()["token"] == "ya29.token"

@pytest.mark.django_db
def test_drive_token_refresh(client, django_user_model):
    from agent.models import DriveAuth
    user = django_user_model.objects.create_user("u","u@x.com","p")
    client.force_login(user)
    DriveAuth.objects.create(
        user=user, access_token="old", refresh_token="r",
        expiry_ts=time.time() - 5
    )

    with patch("agent.views.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "access_token": "new", "expires_in": 3600
        }
        res = client.get(reverse("drive_token"))
    assert res.status_code == 200
    assert res.json()["token"] == "new"


@pytest.mark.django_db
def test_drive_token_not_connected(client, django_user_model):
    user = django_user_model.objects.create_user("u","u@x.com","p")
    client.force_login(user)
    res = client.get(reverse("drive_token"))
    assert res.status_code == 400
    assert res.json()["error"] == "not_connected"

