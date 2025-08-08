import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_drive_token_anon_html_redirects_to_login(client):
    r = client.get(reverse("drive_token"), HTTP_ACCEPT="text/html")
    assert r.status_code in (301, 302)
    assert r["Location"].startswith("/accounts/login/?next=/api/drive/token")

# If you implement the login_required_json wrapper suggested earlier:
@pytest.mark.django_db
def test_drive_token_anon_json_returns_401(client):
    r = client.get(reverse("drive_token"), HTTP_ACCEPT="application/json")
    assert r.status_code == 401
    assert r.json()["error"] == "auth_required"

