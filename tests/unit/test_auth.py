import pytest
from fastapi.testclient import TestClient


def test_token_endpoint(client: TestClient):
    """Test the token endpoint for authentication."""
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "secret"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_token_endpoint_invalid_credentials(client: TestClient):
    """Test the token endpoint with invalid credentials."""
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "wronguser", "password": "wrongpassword"}
    )
    assert response.status_code == 401


def test_me_endpoint(client: TestClient, auth_headers):
    """Test the /me endpoint with valid authentication."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"


def test_me_endpoint_no_auth(client: TestClient):
    """Test the /me endpoint without authentication."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401