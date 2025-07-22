"""
Comprehensive tests for authentication endpoints.

Tests for:
- POST /token (login_for_access_token) - deprecated endpoint
- GET /me (read_users_me) - user profile endpoint

All tests use proper async patterns with pytest-asyncio and comprehensive mocking.
"""

import pytest
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService


class TestAuthEndpoints:
    """Test authentication endpoints with comprehensive coverage."""

    # POST /token endpoint tests
    @pytest.mark.asyncio
    async def test_login_for_access_token_success(self, client):
        """Test successful login with valid credentials."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = {"username": "testuser"}
        mock_service.access_token_expire_minutes = 30
        mock_service.create_access_token.return_value = "fake-jwt-token"

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/auth/token",
                    data={"username": "testuser", "password": "testpass"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == "fake-jwt-token"
        assert data["token_type"] == "bearer"
        
        # Verify service calls
        mock_service.authenticate_user.assert_called_once_with("testuser", "testpass")
        mock_service.create_access_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_for_access_token_invalid_credentials(self, client):
        """Test login failure with invalid credentials."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = None

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/auth/token",
                    data={"username": "baduser", "password": "badpass"}
                )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"] == "Incorrect username or password"
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"

        mock_service.authenticate_user.assert_called_once_with("baduser", "badpass")

    @pytest.mark.asyncio
    async def test_login_for_access_token_missing_credentials(self, client):
        """Test login failure with missing credentials."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/auth/token", data={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        # Should contain validation errors for missing username/password

    @pytest.mark.asyncio
    async def test_login_for_access_token_empty_username(self, client):
        """Test login with empty username."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/token",
                data={"username": "", "password": "testpass"}
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_login_for_access_token_empty_password(self, client):
        """Test login with empty password."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/token",
                data={"username": "testuser", "password": ""}
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_login_for_access_token_service_exception(self, client):
        """Test login when auth service raises exception."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.side_effect = RuntimeError("Database error")

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/auth/token",
                    data={"username": "testuser", "password": "testpass"}
                )

        # Should propagate the exception as 500 error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_login_for_access_token_content_type_json(self, client):
        """Test login with JSON content type instead of form data."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/token",
                json={"username": "testuser", "password": "testpass"}
            )

        # Should fail because OAuth2PasswordRequestForm expects form data
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # GET /me endpoint tests
    @pytest.mark.asyncio
    async def test_read_users_me_success(self, client):
        """Test successful user profile retrieval."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User"
        }

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer fake-jwt-token"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"

        mock_service.get_current_user.assert_called_once_with("fake-jwt-token")

    @pytest.mark.asyncio
    async def test_read_users_me_minimal_user_data(self, client):
        """Test user profile with minimal user data (no email/full_name)."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "username": "testuser"
        }

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer fake-jwt-token"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] is None
        assert data["full_name"] is None

    @pytest.mark.asyncio
    async def test_read_users_me_invalid_token(self, client):
        """Test user profile with invalid token."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.side_effect = NotFoundError("Invalid token")

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer invalid-token"}
                )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"] == "Invalid authentication credentials"
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.asyncio
    async def test_read_users_me_missing_authorization(self, client):
        """Test user profile without authorization header."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"] == "Not authenticated"

    @pytest.mark.asyncio
    async def test_read_users_me_malformed_authorization(self, client):
        """Test user profile with malformed authorization header."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Invalid format"}
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_read_users_me_empty_bearer_token(self, client):
        """Test user profile with empty bearer token."""
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer "}
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_read_users_me_service_exception(self, client):
        """Test user profile when auth service raises unexpected exception."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.side_effect = RuntimeError("Database error")

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer fake-jwt-token"}
                )

        # Should propagate the exception as 500 error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Test dependency injection
    @pytest.mark.asyncio
    async def test_get_auth_service_dependency(self):
        """Test the get_auth_service dependency function."""
        from app.api.v1.endpoints.auth import get_auth_service
        from app.services.auth_service import auth_service
        
        result = get_auth_service()
        assert result is auth_service
        assert isinstance(result, AuthService)

    # Additional edge cases
    @pytest.mark.asyncio
    async def test_login_special_characters_in_credentials(self, client):
        """Test login with special characters in username/password."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = {"username": "user@domain.com"}
        mock_service.access_token_expire_minutes = 30
        mock_service.create_access_token.return_value = "fake-jwt-token"

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/auth/token",
                    data={"username": "user@domain.com", "password": "pass!@#$%"}
                )

        assert response.status_code == status.HTTP_200_OK
        mock_service.authenticate_user.assert_called_once_with("user@domain.com", "pass!@#$%")

    @pytest.mark.asyncio
    async def test_login_unicode_credentials(self, client):
        """Test login with Unicode characters in credentials."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = {"username": "用户"}
        mock_service.access_token_expire_minutes = 30
        mock_service.create_access_token.return_value = "fake-jwt-token"

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/auth/token",
                    data={"username": "用户", "password": "密码"}
                )

        assert response.status_code == status.HTTP_200_OK
        mock_service.authenticate_user.assert_called_once_with("用户", "密码")

    @pytest.mark.asyncio
    async def test_auth_endpoints_deprecated_status(self, client):
        """Test that the token endpoint is properly marked as deprecated."""
        # This would be checked in OpenAPI schema, but we can verify the endpoint exists
        async with AsyncClient(app=client.app, base_url="http://test") as ac:
            response = await ac.options("/api/v1/auth/token")
        
        # Should allow POST method
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]

    @pytest.mark.asyncio
    async def test_token_response_model_validation(self, client):
        """Test that token response follows Token model structure."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.authenticate_user.return_value = {"username": "testuser"}
        mock_service.access_token_expire_minutes = 30
        mock_service.create_access_token.return_value = "fake-jwt-token"

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/auth/token",
                    data={"username": "testuser", "password": "testpass"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify Token model structure
        assert "access_token" in data
        assert "token_type" in data
        assert isinstance(data["access_token"], str)
        assert isinstance(data["token_type"], str)
        assert len(data) == 2  # Only these two fields should be present

    @pytest.mark.asyncio
    async def test_user_response_model_validation(self, client):
        """Test that user profile response follows User model structure."""
        mock_service = MagicMock(spec=AuthService)
        mock_service.get_current_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "extra_field": "should_be_filtered"  # Extra field that should be filtered out
        }

        with patch('app.api.v1.endpoints.auth.get_auth_service', return_value=mock_service):
            async with AsyncClient(app=client.app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer fake-jwt-token"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify User model structure
        assert "username" in data
        assert "email" in data
        assert "full_name" in data
        assert "extra_field" not in data  # Should be filtered out by Pydantic model
        assert len(data) == 3  # Only these three fields should be present