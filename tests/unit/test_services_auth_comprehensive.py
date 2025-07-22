"""
Comprehensive tests for AuthService module.

Tests all authentication functionality including:
- Password hashing and verification
- JWT token creation and validation
- User authentication and management
- Error handling and edge cases
- Service initialization and configuration
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from jose import JWTError, jwt

from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService, auth_service


class TestAuthServiceInitialization:
    """Test suite for AuthService initialization and configuration."""

    def test_auth_service_initialization(self):
        """Test AuthService initialization with default settings."""
        service = AuthService()

        assert service.pwd_context is not None
        assert service.algorithm == "HS256"
        assert service.access_token_expire_minutes == 30
        assert isinstance(service.users_db, dict)
        assert len(service.users_db) == 1  # Default test user

    def test_auth_service_secret_key_from_settings(self):
        """Test AuthService uses secret key from settings when available."""
        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test_secret_key"
            service = AuthService()
            assert service.secret_key == "test_secret_key"

    def test_auth_service_default_secret_key(self):
        """Test AuthService uses default secret key when settings unavailable."""
        with patch("app.services.auth_service.settings", spec=[]):
            # Mock settings without SECRET_KEY attribute
            service = AuthService()
            assert service.secret_key == "secret"

    def test_auth_service_default_user_creation(self):
        """Test that default test user is created properly."""
        service = AuthService()

        assert "user@example.com" in service.users_db
        user = service.users_db["user@example.com"]

        assert user["username"] == "user@example.com"
        assert user["full_name"] == "Test User"
        assert user["email"] == "user@example.com"
        assert user["disabled"] is False
        assert "hashed_password" in user

        # Verify password is properly hashed
        assert service.verify_password("password123", user["hashed_password"])

    def test_global_auth_service_instance(self):
        """Test that global auth_service instance is properly created."""
        assert isinstance(auth_service, AuthService)
        assert auth_service.algorithm == "HS256"


class TestPasswordHashing:
    """Test suite for password hashing and verification."""

    def test_get_password_hash(self):
        """Test password hashing functionality."""
        service = AuthService()
        password = "test_password_123"

        hashed = service.get_password_hash(password)

        assert hashed != password  # Should be hashed, not plain text
        assert len(hashed) > 20  # Bcrypt hashes are long
        assert hashed.startswith("$2b$")  # Bcrypt format

    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes (salt)."""
        service = AuthService()
        password = "same_password"

        hash1 = service.get_password_hash(password)
        hash2 = service.get_password_hash(password)

        assert hash1 != hash2  # Should be different due to salt

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        service = AuthService()
        password = "correct_password"
        hashed = service.get_password_hash(password)

        assert service.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        service = AuthService()
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        hashed = service.get_password_hash(correct_password)

        assert service.verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_strings(self):
        """Test password verification with empty strings."""
        service = AuthService()

        # Empty password should not verify against any hash
        hashed = service.get_password_hash("some_password")
        assert service.verify_password("", hashed) is False

        # Empty hash should not verify
        with pytest.raises(Exception):  # bcrypt will raise an exception
            service.verify_password("password", "")

    def test_verify_password_special_characters(self):
        """Test password verification with special characters."""
        service = AuthService()
        special_password = "p@ssw0rd!#$%^&*()"
        hashed = service.get_password_hash(special_password)

        assert service.verify_password(special_password, hashed) is True
        assert service.verify_password("p@ssw0rd!#$%^&*()X", hashed) is False


class TestUserManagement:
    """Test suite for user management functionality."""

    def test_get_user_existing(self):
        """Test retrieving an existing user."""
        service = AuthService()

        user = service.get_user("user@example.com")

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"
        assert user["full_name"] == "Test User"

    def test_get_user_nonexistent(self):
        """Test retrieving a non-existent user."""
        service = AuthService()

        user = service.get_user("nonexistent@example.com")

        assert user is None

    def test_get_user_case_sensitivity(self):
        """Test that user lookup is case sensitive."""
        service = AuthService()

        # Should not find user with different case
        user = service.get_user("USER@EXAMPLE.COM")
        assert user is None

        user = service.get_user("User@Example.Com")
        assert user is None

    def test_get_user_empty_username(self):
        """Test retrieving user with empty username."""
        service = AuthService()

        user = service.get_user("")
        assert user is None

    def test_users_db_modification(self):
        """Test that users_db can be modified for testing."""
        service = AuthService()

        # Add a new user
        new_user = {
            "username": "newuser@test.com",
            "full_name": "New User",
            "email": "newuser@test.com",
            "hashed_password": service.get_password_hash("newpass"),
            "disabled": False,
        }
        service.users_db["newuser@test.com"] = new_user

        # Verify user can be retrieved
        retrieved = service.get_user("newuser@test.com")
        assert retrieved == new_user


class TestUserAuthentication:
    """Test suite for user authentication functionality."""

    def test_authenticate_user_success(self):
        """Test successful user authentication."""
        service = AuthService()

        user = service.authenticate_user("user@example.com", "password123")

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"

    def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password."""
        service = AuthService()

        user = service.authenticate_user("user@example.com", "wrong_password")

        assert user is None

    def test_authenticate_user_nonexistent_user(self):
        """Test authentication with non-existent user."""
        service = AuthService()

        user = service.authenticate_user("nonexistent@example.com", "password123")

        assert user is None

    def test_authenticate_user_empty_credentials(self):
        """Test authentication with empty credentials."""
        service = AuthService()

        assert service.authenticate_user("", "password123") is None
        assert service.authenticate_user("user@example.com", "") is None
        assert service.authenticate_user("", "") is None

    def test_authenticate_user_disabled_user(self):
        """Test authentication with disabled user."""
        service = AuthService()

        # Create disabled user
        disabled_user = {
            "username": "disabled@example.com",
            "full_name": "Disabled User",
            "email": "disabled@example.com",
            "hashed_password": service.get_password_hash("password"),
            "disabled": True,
        }
        service.users_db["disabled@example.com"] = disabled_user

        # Authentication should still work (business logic may handle disabled status elsewhere)
        user = service.authenticate_user("disabled@example.com", "password")
        assert user is not None
        assert user["disabled"] is True


class TestJWTTokens:
    """Test suite for JWT token creation and validation."""

    def test_create_access_token_basic(self):
        """Test basic JWT token creation."""
        service = AuthService()
        data = {"sub": "user@example.com"}

        token = service.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

        # Verify token can be decoded
        payload = jwt.decode(token, service.secret_key, algorithms=[service.algorithm])
        assert payload["sub"] == "user@example.com"
        assert "exp" in payload

    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        service = AuthService()
        data = {"sub": "user@example.com"}
        expires_delta = timedelta(minutes=60)

        token = service.create_access_token(data, expires_delta)

        payload = jwt.decode(token, service.secret_key, algorithms=[service.algorithm])

        # Check expiry is approximately 60 minutes from now
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + expires_delta

        # Allow 5 second tolerance for test execution time
        assert abs((exp_time - expected_exp).total_seconds()) < 5

    def test_create_access_token_default_expiry(self):
        """Test JWT token creation with default expiry."""
        service = AuthService()
        data = {"sub": "user@example.com"}

        token = service.create_access_token(data)

        payload = jwt.decode(token, service.secret_key, algorithms=[service.algorithm])

        # Check expiry is approximately 30 minutes from now (default)
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(minutes=30)

        assert abs((exp_time - expected_exp).total_seconds()) < 5

    def test_create_access_token_additional_data(self):
        """Test JWT token creation with additional data."""
        service = AuthService()
        data = {
            "sub": "user@example.com",
            "role": "admin",
            "permissions": ["read", "write"],
        }

        token = service.create_access_token(data)

        payload = jwt.decode(token, service.secret_key, algorithms=[service.algorithm])
        assert payload["sub"] == "user@example.com"
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]

    def test_get_current_user_valid_token(self):
        """Test getting current user with valid token."""
        service = AuthService()
        data = {"sub": "user@example.com"}
        token = service.create_access_token(data)

        user = service.get_current_user(token)

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"

    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        service = AuthService()
        invalid_token = "invalid.jwt.token"

        with pytest.raises(NotFoundError, match="Invalid token"):
            service.get_current_user(invalid_token)

    def test_get_current_user_expired_token(self):
        """Test getting current user with expired token."""
        service = AuthService()
        data = {"sub": "user@example.com"}

        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)
        token = service.create_access_token(data, expires_delta)

        with pytest.raises(NotFoundError, match="Invalid token"):
            service.get_current_user(token)

    def test_get_current_user_malformed_token(self):
        """Test getting current user with malformed token."""
        service = AuthService()

        malformed_tokens = [
            "",
            "not.a.jwt",
            "header.payload",  # Missing signature
            "too.many.parts.here.invalid",
        ]

        for token in malformed_tokens:
            with pytest.raises(NotFoundError, match="Invalid token"):
                service.get_current_user(token)

    def test_get_current_user_no_subject(self):
        """Test getting current user with token missing subject."""
        service = AuthService()
        data = {"role": "admin"}  # No 'sub' field
        token = service.create_access_token(data)

        with pytest.raises(NotFoundError, match="Invalid token"):
            service.get_current_user(token)

    def test_get_current_user_nonexistent_user(self):
        """Test getting current user for non-existent user."""
        service = AuthService()
        data = {"sub": "nonexistent@example.com"}
        token = service.create_access_token(data)

        with pytest.raises(NotFoundError, match="User not found"):
            service.get_current_user(token)

    def test_get_current_user_wrong_secret(self):
        """Test token validation with wrong secret key."""
        service = AuthService()
        data = {"sub": "user@example.com"}

        # Create token with one secret
        original_secret = service.secret_key
        token = service.create_access_token(data)

        # Try to validate with different secret
        service.secret_key = "different_secret"

        with pytest.raises(NotFoundError, match="Invalid token"):
            service.get_current_user(token)

        # Restore original secret
        service.secret_key = original_secret


class TestAuthServiceIntegration:
    """Integration tests for AuthService components."""

    def test_full_authentication_flow(self):
        """Test complete authentication flow from login to token validation."""
        service = AuthService()

        # Step 1: Authenticate user
        user = service.authenticate_user("user@example.com", "password123")
        assert user is not None

        # Step 2: Create token for authenticated user
        token_data = {"sub": user["username"]}
        token = service.create_access_token(token_data)

        # Step 3: Validate token and get current user
        current_user = service.get_current_user(token)

        assert current_user["username"] == user["username"]
        assert current_user["email"] == user["email"]

    def test_password_change_simulation(self):
        """Test simulating password change workflow."""
        service = AuthService()

        # Original authentication
        user = service.authenticate_user("user@example.com", "password123")
        assert user is not None

        # Simulate password change
        new_password = "new_secure_password"
        new_hash = service.get_password_hash(new_password)
        service.users_db["user@example.com"]["hashed_password"] = new_hash

        # Old password should no longer work
        user = service.authenticate_user("user@example.com", "password123")
        assert user is None

        # New password should work
        user = service.authenticate_user("user@example.com", new_password)
        assert user is not None

    def test_multiple_users_management(self):
        """Test managing multiple users."""
        service = AuthService()

        # Add multiple users
        users_data = [
            ("admin@test.com", "admin_pass", "Admin User"),
            ("user1@test.com", "user1_pass", "User One"),
            ("user2@test.com", "user2_pass", "User Two"),
        ]

        for email, password, full_name in users_data:
            service.users_db[email] = {
                "username": email,
                "full_name": full_name,
                "email": email,
                "hashed_password": service.get_password_hash(password),
                "disabled": False,
            }

        # Test authentication for each user
        for email, password, full_name in users_data:
            user = service.authenticate_user(email, password)
            assert user is not None
            assert user["full_name"] == full_name

            # Test token creation and validation
            token = service.create_access_token({"sub": email})
            current_user = service.get_current_user(token)
            assert current_user["username"] == email

    def test_concurrent_token_validation(self):
        """Test that multiple tokens can be validated concurrently."""
        service = AuthService()

        # Create multiple tokens
        tokens = []
        for i in range(5):
            data = {"sub": "user@example.com", "session_id": i}
            token = service.create_access_token(data)
            tokens.append(token)

        # Validate all tokens
        for i, token in enumerate(tokens):
            user = service.get_current_user(token)
            assert user["username"] == "user@example.com"

            # Verify session_id is preserved
            payload = jwt.decode(
                token, service.secret_key, algorithms=[service.algorithm]
            )
            assert payload["session_id"] == i


class TestAuthServiceErrorHandling:
    """Test suite for error handling and edge cases."""

    def test_jwt_error_handling(self):
        """Test handling of various JWT errors."""
        service = AuthService()

        # Test with completely invalid token format
        with pytest.raises(NotFoundError):
            service.get_current_user("not_a_token_at_all")

    def test_service_with_corrupted_users_db(self):
        """Test service behavior with corrupted users database."""
        service = AuthService()

        # Corrupt the users database
        service.users_db["user@example.com"]["hashed_password"] = "corrupted_hash"

        # Authentication should fail gracefully
        user = service.authenticate_user("user@example.com", "password123")
        assert user is None

    def test_service_resilience_to_missing_attributes(self):
        """Test service resilience when user objects are missing attributes."""
        service = AuthService()

        # Create user with missing attributes
        incomplete_user = {
            "username": "incomplete@test.com",
            "hashed_password": service.get_password_hash("password"),
            # Missing full_name, email, disabled
        }
        service.users_db["incomplete@test.com"] = incomplete_user

        # Should still be able to authenticate
        user = service.authenticate_user("incomplete@test.com", "password")
        assert user is not None
        assert user["username"] == "incomplete@test.com"

    @patch("app.services.auth_service.jwt.decode")
    def test_jwt_decode_exception_handling(self, mock_decode):
        """Test handling of JWT decode exceptions."""
        service = AuthService()
        mock_decode.side_effect = JWTError("Token decode failed")

        with pytest.raises(NotFoundError, match="Invalid token"):
            service.get_current_user("any_token")

    def test_token_with_non_string_subject(self):
        """Test token validation with non-string subject."""
        service = AuthService()

        # Manually create token with non-string subject
        payload = {"sub": 12345, "exp": datetime.utcnow() + timedelta(minutes=30)}
        token = jwt.encode(payload, service.secret_key, algorithm=service.algorithm)

        with pytest.raises(NotFoundError, match="Invalid token"):
            service.get_current_user(token)
