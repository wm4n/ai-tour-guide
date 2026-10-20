import pytest
from fastapi.testclient import TestClient

from buddy_host.app import create_app
from buddy_host.config import HostConfig


def make_client(token: str | None, tmp_path) -> TestClient:
    config = HostConfig(home=tmp_path, listen_host="127.0.0.1", listen_port=8765, token=token)
    return TestClient(create_app(config))


def test_health_is_open_and_minimal(tmp_path):
    client = make_client("s3cret", tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_requires_token_when_configured(tmp_path):
    client = make_client("s3cret", tmp_path)

    assert client.get("/v1/status").status_code == 401
    assert client.get("/v1/status", headers={"X-Buddy-Token": "wrong"}).status_code == 401


def test_status_accepts_correct_token(tmp_path):
    client = make_client("s3cret", tmp_path)

    response = client.get("/v1/status", headers={"X-Buddy-Token": "s3cret"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_status_open_when_no_token_configured(tmp_path):
    client = make_client(None, tmp_path)

    assert client.get("/v1/status").status_code == 200


@pytest.mark.parametrize("path", ["/health", "/v1/status"])
def test_responses_do_not_leak_secrets(tmp_path, path):
    client = make_client("s3cret", tmp_path)

    response = client.get(path, headers={"X-Buddy-Token": "s3cret"})

    assert "s3cret" not in response.text
    assert str(tmp_path) not in response.text
