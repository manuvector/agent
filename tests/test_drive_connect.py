import urllib.parse as up
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_drive_connect_redirects_to_google(client, django_user_model):
    user = django_user_model.objects.create_user("u","u@x.com","p")
    client.force_login(user)
    r = client.get(reverse("drive_connect"))
    assert r.status_code in (301, 302)
    assert "accounts.google.com/o/oauth2/v2/auth" in r["Location"]
    qs = dict(up.parse_qsl(up.urlsplit(r["Location"]).query))
    for p in ["client_id","redirect_uri","response_type","scope"]:
        assert p in qs
    assert qs["response_type"] == "code"
    # if you add state=picker:
    # assert qs.get("state") == "picker"

