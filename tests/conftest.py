import uuid
import pytest
from django.contrib.auth import get_user_model
from django.test.client import Client

@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username=f"u{uuid.uuid4().hex[:8]}", email="u@example.com", password="pw"
    )

@pytest.fixture
def auth_client(user):
    client = Client()
    assert client.login(username=user.username, password="pw")
    return client

@pytest.fixture(autouse=True)
def _no_external_http(responses):
    """Fail test if *any* unexpected URL is requested."""
    responses.add_passthru("http://testserver")   # allow local test-client calls
    yield
    # responses lib will raise if any un-stubbed call happened

