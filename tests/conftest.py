import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def member(client):
    response = client.post(
        "/api/members",
        json={
            "name": "Maya Singh",
            "email": "maya@example.com",
            "membership": "Premium",
            "joined_on": "2026-01-10",
        },
    )
    return response.get_json()
