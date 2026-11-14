import os
import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient

# configure env before import
tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tmpdir, 'test.db')}"
os.environ["STORAGE_DIR"] = os.path.join(tmpdir, "uploads")
os.environ["OPENAI_API_KEY"] = ""

from app.main import app  # noqa
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

TEST_PASSWORD = "test-password-123"


@pytest.fixture
def anon_client():
    return TestClient(app)


@pytest.fixture
def client(anon_client):
    """An authenticated client with a fresh account per test."""
    username = f"user_{uuid.uuid4().hex[:12]}"
    r = anon_client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    anon_client.headers.update({"Authorization": f"Bearer {token}"})
    return anon_client
