# tests/conftest.py
import pytest
from django.contrib.auth import get_user_model

@pytest.fixture
def user(db):
    U = get_user_model()
    return U.objects.create_user(
        username="u"  # any unique value; tests don't depend on it
    )

@pytest.fixture
def auth_client(user, client):
    client.force_login(user)
    return client

# If you want to prevent accidental outbound HTTP globally, you can
# add a *no-op* autouse that only tweaks Responses when it's already active.
# (Do NOT create a new Responses mock here; it clashes with @responses.activate.)
try:
    import re
    import responses as _responses
    @pytest.fixture(autouse=True)
    def _no_external_http():
        rm = getattr(_responses, "_default_mock", None)
        if rm and getattr(rm, "_is_started", False):
            rm.add_passthru(re.compile(r"^http://testserver"))
        yield
except Exception:
    # If responses isn't available or its API changes, just do nothing.
    @pytest.fixture(autouse=True)
    def _no_external_http():
        yield

