# tests/conftest.py
import os
import pytest

@pytest.fixture(autouse=True)
def _env_settings(settings, monkeypatch):
    # keep external calls off by default
    os.environ.setdefault("OPENAI_API_KEY", "test")
    settings.SECRET_KEY = "test"
    return settings

@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user("u", "u@x.com", "p")

@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client

