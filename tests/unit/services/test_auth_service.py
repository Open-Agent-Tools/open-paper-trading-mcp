"""
Comprehensive tests for AuthService - authentication and authorization service.

Tests cover:
- User authentication with username and password
- Password hashing and verification
- JWT token creation and validation
- User data retrieval and management
- Token expiration handling
- Authentication error scenarios
- Security best practices validation
- Mock user database operations
- Token payload validation
- Service initialization and configuration
- Edge cases and error handling
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from jose import JWTError, jwt

from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService, auth_service


@pytest.fixture
def auth_service_instance():
    """Create a fresh auth service instance for testing."""
    return AuthService()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""

    class MockSettings:
        SECRET_KEY = "test-secret-key-for-testing"

    return MockSettings()


@pytest.fixture
def test_user_data():
    """Test user data for authentication."""
    return {
        "username": "testuser@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
        "email": "testuser@example.com",
    }


@pytest.fixture
def expired_token_data():
    """Token data that is expired."""
    return {
        "sub": "testuser@example.com",
        "exp": datetime.utcnow() - timedelta(minutes=10),  # Expired 10 minutes ago
    }


class TestAuthServiceInitialization:
    """Test authentication service initialization and setup."""

    def test_default_initialization(self):
        """Test auth service initialization with defaults."""
        service = AuthService()

        assert service.pwd_context is not None
        assert service.secret_key == "secret"  # Default when no settings
        assert service.algorithm == "HS256"
        assert service.access_token_expire_minutes == 30
        assert isinstance(service.users_db, dict)
        assert len(service.users_db) == 1  # Default test user

    def test_initialization_with_settings(self, mock_settings):
        """Test auth service initialization with custom settings."""
        with patch("app.services.auth_service.settings", mock_settings):
            service = AuthService()

            assert service.secret_key == "test-secret-key-for-testing"

    def test_default_user_exists(self, auth_service_instance):
        """Test that default test user exists in database."""
        default_user = auth_service_instance.get_user("user@example.com")

        assert default_user is not None
        assert default_user["username"] == "user@example.com"
        assert default_user["full_name"] == "Test User"
        assert default_user["email"] == "user@example.com"
        assert default_user["disabled"] is False
        assert "hashed_password" in default_user

    def test_password_context_setup(self, auth_service_instance):
        """Test password context is properly configured."""
        # Test that password hashing works
        test_password = "test123"
        hashed = auth_service_instance.get_password_hash(test_password)

        assert hashed != test_password
        assert auth_service_instance.verify_password(test_password, hashed)

    def test_global_service_instance(self):
        """Test global auth service instance."""
        service = auth_service
        assert isinstance(service, AuthService)


class TestPasswordManagement:
    """Test password hashing and verification functionality."""

    def test_get_password_hash_creates_hash(self, auth_service_instance):
        """Test password hashing creates valid hash."""
        password = "mypassword123"
        hashed = auth_service_instance.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are long
        assert hashed.startswith("$2b$")  # Bcrypt format

    def test_get_password_hash_different_for_same_password(self, auth_service_instance):
        """Test that same password creates different hashes (salt)."""
        password = "samepassword"
        hash1 = auth_service_instance.get_password_hash(password)
        hash2 = auth_service_instance.get_password_hash(password)

        assert hash1 != hash2  # Different due to salt
        # But both should verify correctly
        assert auth_service_instance.verify_password(password, hash1)
        assert auth_service_instance.verify_password(password, hash2)

    def test_verify_password_correct_password(self, auth_service_instance):
        """Test password verification with correct password."""
        password = "correctpassword"
        hashed = auth_service_instance.get_password_hash(password)

        assert auth_service_instance.verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self, auth_service_instance):
        """Test password verification with incorrect password."""
        correct_password = "correctpassword"
        wrong_password = "wrongpassword"
        hashed = auth_service_instance.get_password_hash(correct_password)

        assert auth_service_instance.verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_password(self, auth_service_instance):
        """Test password verification with empty password."""
        password = "password123"
        hashed = auth_service_instance.get_password_hash(password)

        assert auth_service_instance.verify_password("", hashed) is False

    def test_verify_password_empty_hash(self, auth_service_instance):
        """Test password verification with empty hash."""
        assert auth_service_instance.verify_password("password", "") is False

    def test_password_special_characters(self, auth_service_instance):
        """Test password hashing with special characters."""
        special_password = "p@ssw0rd!#$%^&*()_+-=[]{}|;:,.<>?"
        hashed = auth_service_instance.get_password_hash(special_password)

        assert auth_service_instance.verify_password(special_password, hashed) is True

    def test_password_unicode_characters(self, auth_service_instance):
        """Test password hashing with unicode characters."""
        unicode_password = "pássw0rd中文🔒"
        hashed = auth_service_instance.get_password_hash(unicode_password)

        assert auth_service_instance.verify_password(unicode_password, hashed) is True


class TestUserManagement:
    """Test user retrieval and management functionality."""

    def test_get_user_existing_user(self, auth_service_instance):
        """Test retrieving existing user."""
        user = auth_service_instance.get_user("user@example.com")

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"
        assert "hashed_password" in user

    def test_get_user_nonexistent_user(self, auth_service_instance):
        """Test retrieving non-existent user returns None."""
        user = auth_service_instance.get_user("nonexistent@example.com")

        assert user is None

    def test_get_user_empty_username(self, auth_service_instance):
        """Test retrieving user with empty username."""
        user = auth_service_instance.get_user("")

        assert user is None

    def test_get_user_none_username(self, auth_service_instance):
        """Test retrieving user with None username."""
        user = auth_service_instance.get_user(None)

        assert user is None

    def test_get_user_case_sensitivity(self, auth_service_instance):
        """Test that user lookup is case sensitive."""
        # Default user is "user@example.com"
        user_lower = auth_service_instance.get_user("user@example.com")
        user_upper = auth_service_instance.get_user("USER@EXAMPLE.COM")

        assert user_lower is not None
        assert user_upper is None  # Case sensitive

    def test_users_db_structure(self, auth_service_instance):
        """Test user database structure."""
        users_db = auth_service_instance.users_db

        assert isinstance(users_db, dict)

        # Check default user structure
        default_user = users_db["user@example.com"]
        required_fields = [
            "username",
            "full_name",
            "email",
            "hashed_password",
            "disabled",
        ]

        for field in required_fields:
            assert field in default_user


class TestUserAuthentication:
    """Test user authentication functionality."""

    def test_authenticate_user_valid_credentials(self, auth_service_instance):
        """Test authentication with valid credentials."""
        # Use default test user
        user = auth_service_instance.authenticate_user(
            "user@example.com", "password123"
        )

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"

    def test_authenticate_user_invalid_password(self, auth_service_instance):
        """Test authentication with invalid password."""
        user = auth_service_instance.authenticate_user(
            "user@example.com", "wrongpassword"
        )

        assert user is None

    def test_authenticate_user_invalid_username(self, auth_service_instance):
        """Test authentication with invalid username."""
        user = auth_service_instance.authenticate_user(
            "invalid@example.com", "password123"
        )

        assert user is None

    def test_authenticate_user_empty_credentials(self, auth_service_instance):
        """Test authentication with empty credentials."""
        user = auth_service_instance.authenticate_user("", "")

        assert user is None

    def test_authenticate_user_none_credentials(self, auth_service_instance):
        """Test authentication with None credentials."""
        user = auth_service_instance.authenticate_user(None, None)

        assert user is None

    def test_authenticate_user_empty_password(self, auth_service_instance):
        """Test authentication with empty password."""
        user = auth_service_instance.authenticate_user("user@example.com", "")

        assert user is None

    def test_authenticate_user_disabled_user(self, auth_service_instance):
        """Test authentication with disabled user."""
        # Create disabled user
        auth_service_instance.users_db["disabled@example.com"] = {
            "username": "disabled@example.com",
            "full_name": "Disabled User",
            "email": "disabled@example.com",
            "hashed_password": auth_service_instance.get_password_hash("password123"),
            "disabled": True,
        }

        # Authentication should still work (business logic to check disabled status elsewhere)
        user = auth_service_instance.authenticate_user(
            "disabled@example.com", "password123"
        )

        assert user is not None
        assert user["disabled"] is True

    def test_authenticate_user_special_characters_in_password(
        self, auth_service_instance
    ):
        """Test authentication with special characters in password."""
        # Create user with special character password
        special_password = "p@ssw0rd!#$"
        auth_service_instance.users_db["special@example.com"] = {
            "username": "special@example.com",
            "full_name": "Special User",
            "email": "special@example.com",
            "hashed_password": auth_service_instance.get_password_hash(
                special_password
            ),
            "disabled": False,
        }

        user = auth_service_instance.authenticate_user(
            "special@example.com", special_password
        )

        assert user is not None
        assert user["username"] == "special@example.com"


class TestJWTTokenCreation:
    """Test JWT token creation functionality."""

    def test_create_access_token_basic(self, auth_service_instance):
        """Test basic JWT token creation."""
        data = {"sub": "user@example.com"}
        token = auth_service_instance.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are long
        assert token.count(".") == 2  # JWT format: header.payload.signature

    def test_create_access_token_with_expiration(self, auth_service_instance):
        """Test JWT token creation with custom expiration."""
        data = {"sub": "user@example.com"}
        expires_delta = timedelta(minutes=15)
        token = auth_service_instance.create_access_token(data, expires_delta)

        # Decode to verify expiration
        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )

        assert "exp" in payload
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + expires_delta

        # Allow 5 second tolerance for timing
        assert abs((exp_time - expected_exp).total_seconds()) < 5

    def test_create_access_token_default_expiration(self, auth_service_instance):
        """Test JWT token creation with default expiration."""
        data = {"sub": "user@example.com"}
        token = auth_service_instance.create_access_token(data)

        # Decode to verify expiration
        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )

        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(minutes=30)  # Default 30 minutes

        # Allow 5 second tolerance
        assert abs((exp_time - expected_exp).total_seconds()) < 5

    def test_create_access_token_custom_data(self, auth_service_instance):
        """Test JWT token creation with custom data."""
        data = {
            "sub": "user@example.com",
            "role": "admin",
            "permissions": ["read", "write"],
            "custom_field": "custom_value",
        }
        token = auth_service_instance.create_access_token(data)

        # Decode to verify data
        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )

        assert payload["sub"] == "user@example.com"
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]
        assert payload["custom_field"] == "custom_value"

    def test_create_access_token_empty_data(self, auth_service_instance):
        """Test JWT token creation with empty data."""
        data = {}
        token = auth_service_instance.create_access_token(data)

        # Should still create valid token with expiration
        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )

        assert "exp" in payload

    def test_create_access_token_modifies_original_data(self, auth_service_instance):
        """Test that token creation doesn't modify original data dict."""
        original_data = {"sub": "user@example.com", "role": "user"}
        data_copy = original_data.copy()

        auth_service_instance.create_access_token(original_data)

        # Original data should be unchanged (except exp might be added to copy)
        assert original_data == data_copy


class TestJWTTokenValidation:
    """Test JWT token validation and user retrieval."""

    def test_get_current_user_valid_token(self, auth_service_instance):
        """Test getting current user with valid token."""
        # Create token for existing user
        data = {"sub": "user@example.com"}
        token = auth_service_instance.create_access_token(data)

        user = auth_service_instance.get_current_user(token)

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"

    def test_get_current_user_expired_token(self, auth_service_instance):
        """Test getting current user with expired token."""
        # Create expired token
        data = {"sub": "user@example.com"}
        expires_delta = timedelta(seconds=-10)  # Expired 10 seconds ago
        token = auth_service_instance.create_access_token(data, expires_delta)

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(token)

    def test_get_current_user_invalid_token(self, auth_service_instance):
        """Test getting current user with invalid token."""
        invalid_token = "invalid.token.string"

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(invalid_token)

    def test_get_current_user_malformed_token(self, auth_service_instance):
        """Test getting current user with malformed token."""
        malformed_token = "not.a.jwt"

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(malformed_token)

    def test_get_current_user_wrong_secret(self, auth_service_instance):
        """Test getting current user with token signed with wrong secret."""
        # Create token with different secret
        data = {"sub": "user@example.com"}
        wrong_secret_token = jwt.encode(data, "wrong_secret", algorithm="HS256")

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(wrong_secret_token)

    def test_get_current_user_no_sub_claim(self, auth_service_instance):
        """Test getting current user with token missing 'sub' claim."""
        data = {"username": "user@example.com"}  # No 'sub' field
        token = auth_service_instance.create_access_token(data)

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(token)

    def test_get_current_user_none_sub_claim(self, auth_service_instance):
        """Test getting current user with None 'sub' claim."""
        data = {"sub": None}
        token = auth_service_instance.create_access_token(data)

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(token)

    def test_get_current_user_numeric_sub_claim(self, auth_service_instance):
        """Test getting current user with numeric 'sub' claim."""
        data = {"sub": 12345}  # Not a string
        token = auth_service_instance.create_access_token(data)

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(token)

    def test_get_current_user_nonexistent_user(self, auth_service_instance):
        """Test getting current user for non-existent user."""
        data = {"sub": "nonexistent@example.com"}
        token = auth_service_instance.create_access_token(data)

        with pytest.raises(NotFoundError, match="User not found"):
            auth_service_instance.get_current_user(token)

    def test_get_current_user_empty_token(self, auth_service_instance):
        """Test getting current user with empty token."""
        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user("")

    def test_get_current_user_token_different_algorithm(self, auth_service_instance):
        """Test getting current user with token using different algorithm."""
        # Create token with HS512 instead of HS256
        data = {"sub": "user@example.com"}
        wrong_alg_token = jwt.encode(
            data, auth_service_instance.secret_key, algorithm="HS512"
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            auth_service_instance.get_current_user(wrong_alg_token)


class TestSecurityFeatures:
    """Test security features and best practices."""

    def test_password_hash_salt_randomness(self, auth_service_instance):
        """Test that password hashes include random salt."""
        password = "testpassword"
        hash1 = auth_service_instance.get_password_hash(password)
        hash2 = auth_service_instance.get_password_hash(password)

        # Same password should produce different hashes due to salt
        assert hash1 != hash2

        # But both should verify correctly
        assert auth_service_instance.verify_password(password, hash1)
        assert auth_service_instance.verify_password(password, hash2)

    def test_jwt_token_uniqueness(self, auth_service_instance):
        """Test that JWT tokens are unique even for same user."""
        data = {"sub": "user@example.com"}
        token1 = auth_service_instance.create_access_token(data)
        token2 = auth_service_instance.create_access_token(data)

        # Tokens should be different due to timestamp precision
        assert token1 != token2

    def test_jwt_algorithm_consistency(self, auth_service_instance):
        """Test that JWT algorithm is consistently used."""
        assert auth_service_instance.algorithm == "HS256"

        # Create and verify token uses same algorithm
        data = {"sub": "user@example.com"}
        token = auth_service_instance.create_access_token(data)

        # Should decode successfully with same algorithm
        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )
        assert payload["sub"] == "user@example.com"

    def test_secret_key_protection(self, auth_service_instance):
        """Test that secret key is properly protected."""
        # Secret key should not be empty or default in production
        assert auth_service_instance.secret_key is not None
        assert len(auth_service_instance.secret_key) > 0

        # Test that different secret produces different tokens
        service2 = AuthService()
        service2.secret_key = "different_secret"

        data = {"sub": "user@example.com"}
        token1 = auth_service_instance.create_access_token(data)
        token2 = service2.create_access_token(data)

        assert token1 != token2

    def test_bcrypt_hash_format(self, auth_service_instance):
        """Test that bcrypt hash format is correct."""
        password = "testpassword"
        hashed = auth_service_instance.get_password_hash(password)

        # Bcrypt hash should start with $2b$ and have correct format
        assert hashed.startswith("$2b$")
        parts = hashed.split("$")
        assert len(parts) == 4  # ['', '2b', 'rounds', 'salt+hash']
        assert parts[1] == "2b"  # Bcrypt version
        assert len(parts[2]) == 2  # Round count (e.g., "12")
        assert len(parts[3]) == 53  # Salt (22 chars) + hash (31 chars)


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_jwt_decode_error_handling(self, auth_service_instance):
        """Test JWT decode error handling."""
        # Mock JWT decode to raise different errors
        with patch("app.services.auth_service.jwt.decode") as mock_decode:
            mock_decode.side_effect = JWTError("Token decode error")

            with pytest.raises(NotFoundError, match="Invalid token"):
                auth_service_instance.get_current_user("some_token")

    def test_password_verification_error_handling(self, auth_service_instance):
        """Test password verification error handling."""
        # Test with malformed hash
        with pytest.raises(Exception):
            auth_service_instance.verify_password("password", "malformed_hash")

    def test_users_db_corruption_handling(self, auth_service_instance):
        """Test handling of corrupted user database."""
        # Corrupt the users database
        auth_service_instance.users_db["corrupt@example.com"] = "not_a_dict"

        # Should handle gracefully
        user = auth_service_instance.get_user("corrupt@example.com")
        assert user == "not_a_dict"  # Returns whatever is stored

    def test_token_creation_with_invalid_data_types(self, auth_service_instance):
        """Test token creation with invalid data types."""
        # JWT should handle most data types
        data = {
            "sub": "user@example.com",
            "number": 123,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        token = auth_service_instance.create_access_token(data)

        # Should create valid token
        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )

        assert payload["sub"] == "user@example.com"
        assert payload["number"] == 123
        assert payload["boolean"] is True
        assert payload["null"] is None


class TestIntegrationScenarios:
    """Test complete authentication workflows."""

    def test_complete_authentication_flow(self, auth_service_instance):
        """Test complete authentication flow from login to token validation."""
        username = "user@example.com"
        password = "password123"

        # Step 1: Authenticate user
        user = auth_service_instance.authenticate_user(username, password)
        assert user is not None

        # Step 2: Create access token
        token_data = {"sub": user["username"]}
        access_token = auth_service_instance.create_access_token(token_data)
        assert isinstance(access_token, str)

        # Step 3: Validate token and get current user
        current_user = auth_service_instance.get_current_user(access_token)
        assert current_user["username"] == username
        assert current_user["email"] == user["email"]

    def test_failed_authentication_flow(self, auth_service_instance):
        """Test failed authentication flow."""
        username = "user@example.com"
        wrong_password = "wrongpassword"

        # Step 1: Try to authenticate with wrong password
        user = auth_service_instance.authenticate_user(username, wrong_password)
        assert user is None

        # Should not proceed to token creation in real app

    def test_expired_token_flow(self, auth_service_instance):
        """Test expired token handling flow."""
        username = "user@example.com"

        # Create immediately expired token
        token_data = {"sub": username}
        expired_token = auth_service_instance.create_access_token(
            token_data, timedelta(seconds=-1)
        )

        # Try to use expired token
        with pytest.raises(NotFoundError):
            auth_service_instance.get_current_user(expired_token)

    def test_user_management_flow(self, auth_service_instance):
        """Test user management operations."""
        new_username = "newuser@example.com"
        new_password = "newpassword123"

        # Add new user
        auth_service_instance.users_db[new_username] = {
            "username": new_username,
            "full_name": "New User",
            "email": new_username,
            "hashed_password": auth_service_instance.get_password_hash(new_password),
            "disabled": False,
        }

        # Test new user can authenticate
        user = auth_service_instance.authenticate_user(new_username, new_password)
        assert user is not None
        assert user["username"] == new_username

        # Test token creation and validation for new user
        token_data = {"sub": new_username}
        token = auth_service_instance.create_access_token(token_data)
        current_user = auth_service_instance.get_current_user(token)
        assert current_user["username"] == new_username


class TestConfigurationAndSettings:
    """Test configuration and settings handling."""

    def test_custom_token_expiration(self, auth_service_instance):
        """Test custom token expiration configuration."""
        # Change default expiration
        auth_service_instance.access_token_expire_minutes = 60

        data = {"sub": "user@example.com"}
        token = auth_service_instance.create_access_token(data)

        payload = jwt.decode(
            token,
            auth_service_instance.secret_key,
            algorithms=[auth_service_instance.algorithm],
        )

        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(minutes=60)

        # Should use new expiration time
        assert abs((exp_time - expected_exp).total_seconds()) < 5

    def test_custom_algorithm_configuration(self, auth_service_instance):
        """Test custom algorithm configuration."""
        # Change algorithm
        auth_service_instance.algorithm = "HS512"

        data = {"sub": "user@example.com"}
        token = auth_service_instance.create_access_token(data)

        # Should decode with new algorithm
        payload = jwt.decode(
            token, auth_service_instance.secret_key, algorithms=["HS512"]
        )
        assert payload["sub"] == "user@example.com"

        # Should fail with old algorithm
        with pytest.raises(JWTError):
            jwt.decode(token, auth_service_instance.secret_key, algorithms=["HS256"])

    def test_settings_integration(self, mock_settings):
        """Test integration with application settings."""
        with patch("app.services.auth_service.settings", mock_settings):
            service = AuthService()

            assert service.secret_key == mock_settings.SECRET_KEY

            # Test that tokens work with settings secret
            data = {"sub": "user@example.com"}
            token = service.create_access_token(data)
            user = service.get_current_user(token)
            assert user["username"] == "user@example.com"
