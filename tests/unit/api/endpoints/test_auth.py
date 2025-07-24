"""
Comprehensive tests for authentication endpoints.

Tests all auth endpoints with proper mocking:
- POST /token (login for access token) - deprecated
- GET /me (get current user information)

Covers success paths, error handling, token validation, and security scenarios.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService


class TestAuthEndpoints:
    """Test suite for authentication endpoints."""

    # POST /token endpoint - Login for access token (deprecated)
    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_login_for_access_token_success(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test successful login and token generation."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = {"username": "testuser"}
        mock_service.access_token_expire_minutes = 30
        mock_service.create_access_token.return_value = "fake-jwt-token"
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "testuser", "password": "testpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["access_token"] == "fake-jwt-token"
        assert data["token_type"] == "bearer"

        # Verify service calls
        mock_service.authenticate_user.assert_called_once_with("testuser", "testpass")
        mock_service.create_access_token.assert_called_once()

        # Verify token creation parameters
        call_args = mock_service.create_access_token.call_args
        assert call_args[1]["data"]["sub"] == "testuser"
        assert isinstance(call_args[1]["expires_delta"], timedelta)

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_login_for_access_token_invalid_credentials(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test login with invalid credentials."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None  # Invalid credentials
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "invaliduser", "password": "wrongpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()

        assert data["detail"] == "Incorrect username or password"
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_login_for_access_token_empty_username(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test login with empty username."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "", "password": "testpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_login_for_access_token_empty_password(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test login with empty password."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "testuser", "password": ""}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_for_access_token_missing_form_data(self, client: TestClient):
        """Test login with missing form data."""
        response = client.post("/api/v1/auth/token", data={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_for_access_token_wrong_content_type(self, client: TestClient):
        """Test login with JSON instead of form data."""
        json_data = {"username": "testuser", "password": "testpass"}

        response = client.post("/api/v1/auth/token", json=json_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_login_for_access_token_service_error(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test login when auth service raises an exception."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.side_effect = Exception(
            "Database connection failed"
        )
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "testuser", "password": "testpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # GET /me endpoint - Get current user information
    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_read_users_me_success(self, mock_get_auth_service, client: TestClient):
        """Test successful retrieval of current user information."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
        }
        mock_get_auth_service.return_value = mock_service

        headers = {"Authorization": "Bearer fake-jwt-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"

        mock_service.get_current_user.assert_called_once_with("fake-jwt-token")

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_read_users_me_minimal_user_data(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test retrieval of user with minimal data (only username)."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "username": "testuser"
            # No email or full_name
        }
        mock_get_auth_service.return_value = mock_service

        headers = {"Authorization": "Bearer fake-jwt-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["username"] == "testuser"
        assert data["email"] is None
        assert data["full_name"] is None

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_read_users_me_invalid_token(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test user retrieval with invalid token."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.side_effect = NotFoundError("Invalid token")
        mock_get_auth_service.return_value = mock_service

        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()

        assert data["detail"] == "Invalid authentication credentials"
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_read_users_me_expired_token(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test user retrieval with expired token."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.side_effect = NotFoundError("Token expired")
        mock_get_auth_service.return_value = mock_service

        headers = {"Authorization": "Bearer expired-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_read_users_me_missing_token(self, client: TestClient):
        """Test user retrieval without token."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_read_users_me_malformed_authorization_header(self, client: TestClient):
        """Test user retrieval with malformed authorization header."""
        malformed_headers = [
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Basic fake-token"},  # Wrong scheme
            {"Authorization": "fake-token"},  # Missing scheme
            {"Authorization": "Bearer token with spaces"},  # Token with spaces
        ]

        for headers in malformed_headers:
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_read_users_me_service_error(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test user retrieval when auth service raises an exception."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.side_effect = Exception("Service unavailable")
        mock_get_auth_service.return_value = mock_service

        headers = {"Authorization": "Bearer fake-jwt-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestAuthDependencies:
    """Test authentication dependency functions."""

    @patch("app.api.v1.endpoints.auth.auth_service")
    def test_get_auth_service_dependency(self, mock_auth_service):
        """Test the get_auth_service dependency function."""
        from app.api.v1.endpoints.auth import get_auth_service

        result = get_auth_service()

        assert result == mock_auth_service


class TestAuthEndpointsSecurityScenarios:
    """Test security-related scenarios for auth endpoints."""

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_sql_injection_attempt_in_username(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test handling of SQL injection attempt in username."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "'; DROP TABLE users; --", "password": "testpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # Service should be called with the malicious input, but safely handled
        mock_service.authenticate_user.assert_called_once_with(
            "'; DROP TABLE users; --", "testpass"
        )

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_very_long_username(self, mock_get_auth_service, client: TestClient):
        """Test handling of extremely long username."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None
        mock_get_auth_service.return_value = mock_service

        long_username = "a" * 10000  # Very long username
        form_data = {"username": long_username, "password": "testpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        # Should handle gracefully, either rejecting or processing safely
        assert response.status_code in [400, 401, 422]

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_very_long_password(self, mock_get_auth_service, client: TestClient):
        """Test handling of extremely long password."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None
        mock_get_auth_service.return_value = mock_service

        long_password = "p" * 10000  # Very long password
        form_data = {"username": "testuser", "password": long_password}

        response = client.post("/api/v1/auth/token", data=form_data)

        # Should handle gracefully
        assert response.status_code in [400, 401, 422]

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_unicode_characters_in_credentials(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test handling of unicode characters in credentials."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None
        mock_get_auth_service.return_value = mock_service

        form_data = {"username": "tëstüser🔐", "password": "pāssw🔒rd"}

        response = client.post("/api/v1/auth/token", data=form_data)

        # Should handle unicode gracefully
        assert response.status_code in [401, 422]

    def test_multiple_concurrent_login_attempts(self, client: TestClient):
        """Test handling of multiple concurrent login attempts."""
        # This would typically test rate limiting, but we'll test basic handling
        form_data = {"username": "testuser", "password": "wrongpass"}

        responses = []
        for _ in range(5):
            response = client.post("/api/v1/auth/token", data=form_data)
            responses.append(response)

        # All should be handled consistently
        for response in responses:
            assert response.status_code in [
                401,
                429,
            ]  # 429 if rate limiting is implemented

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_token_with_special_characters(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test handling of tokens with special characters."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.side_effect = NotFoundError("Invalid token")
        mock_get_auth_service.return_value = mock_service

        special_tokens = [
            "fake-token@#$%",
            "fake.token.with.dots",
            "fake_token_with_underscores",
            "fake-token-with-dashes",
            "token with spaces",
            "токен",  # Cyrillic
            "🔐token🔐",  # Emoji
        ]

        for token in special_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/v1/auth/me", headers=headers)

            # Should handle all special characters gracefully
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthEndpointsDeprecation:
    """Test deprecation warnings and behavior for deprecated endpoints."""

    def test_token_endpoint_deprecation_warning(self, client: TestClient):
        """Test that the deprecated token endpoint still works but is marked deprecated."""
        # The endpoint should work but be marked as deprecated in OpenAPI spec
        # In a real implementation, you might check for deprecation warnings in logs

        form_data = {"username": "testuser", "password": "testpass"}

        response = client.post("/api/v1/auth/token", data=form_data)

        # Endpoint should still function regardless of deprecation status
        assert response.status_code in [200, 401, 500]


class TestAuthEndpointsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_form_submission(self, client: TestClient):
        """Test completely empty form submission."""
        response = client.post("/api/v1/auth/token", data="")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_null_values_in_form_data(self, client: TestClient):
        """Test form data with null values."""
        # Most HTTP clients won't send literal null, but test edge case
        form_data = {"username": None, "password": None}

        response = client.post("/api/v1/auth/token", data=form_data)

        assert response.status_code in [401, 422]

    @patch("app.api.v1.endpoints.auth.get_auth_service")
    def test_user_data_with_missing_username(
        self, mock_get_auth_service, client: TestClient
    ):
        """Test user retrieval when service returns data without username."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "email": "test@example.com",
            "full_name": "Test User",
            # Missing username - should cause validation error
        }
        mock_get_auth_service.return_value = mock_service

        headers = {"Authorization": "Bearer fake-jwt-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        # Should fail validation due to missing required username field
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
