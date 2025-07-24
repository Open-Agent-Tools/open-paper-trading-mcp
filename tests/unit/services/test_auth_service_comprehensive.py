"""
Comprehensive test suite for AuthService.

Tests all authentication and authorization functionality including:
- Password hashing and verification
- JWT token creation and validation
- User authentication workflows
- Error handling and edge cases
- Security validations
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from jose import JWTError, jwt

from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService, auth_service


class TestAuthService:
    """Test suite for AuthService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = AuthService()
        self.test_password = "test_password_123"
        self.test_username = "test@example.com"
        self.test_user_data = {
            "username": self.test_username,
            "full_name": "Test User",
            "email": self.test_username,
            "disabled": False,
        }

    def test_auth_service_initialization(self):
        """Test AuthService initialization."""
        service = AuthService()

        assert service.pwd_context is not None
        assert service.algorithm == "HS256"
        assert service.access_token_expire_minutes == 30
        assert isinstance(service.users_db, dict)
        assert "user@example.com" in service.users_db

    def test_auth_service_initialization_with_settings(self):
        """Test AuthService initialization with custom settings."""
        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.SECRET_KEY = "custom_secret"
            service = AuthService()
            assert service.secret_key == "custom_secret"

    def test_auth_service_initialization_without_settings(self):
        """Test AuthService initialization without SECRET_KEY in settings."""
        with patch("app.services.auth_service.settings", spec=[]):
            service = AuthService()
            assert service.secret_key == "secret"

    def test_get_password_hash(self):
        """Test password hashing functionality."""
        password_hash = self.auth_service.get_password_hash(self.test_password)

        assert password_hash is not None
        assert password_hash != self.test_password
        assert isinstance(password_hash, str)
        assert len(password_hash) > 20

    def test_get_password_hash_different_passwords(self):
        """Test that different passwords produce different hashes."""
        hash1 = self.auth_service.get_password_hash("password1")
        hash2 = self.auth_service.get_password_hash("password2")

        assert hash1 != hash2

    def test_get_password_hash_same_password_different_salts(self):
        """Test that same password produces different hashes due to salt."""
        hash1 = self.auth_service.get_password_hash(self.test_password)
        hash2 = self.auth_service.get_password_hash(self.test_password)

        # Due to salt, hashes should be different
        assert hash1 != hash2

    def test_verify_password_success(self):
        """Test successful password verification."""
        password_hash = self.auth_service.get_password_hash(self.test_password)

        result = self.auth_service.verify_password(self.test_password, password_hash)
        assert result is True

    def test_verify_password_failure(self):
        """Test failed password verification."""
        password_hash = self.auth_service.get_password_hash(self.test_password)

        result = self.auth_service.verify_password("wrong_password", password_hash)
        assert result is False

    def test_verify_password_empty_password(self):
        """Test password verification with empty password."""
        password_hash = self.auth_service.get_password_hash(self.test_password)

        result = self.auth_service.verify_password("", password_hash)
        assert result is False

    def test_verify_password_empty_hash(self):
        """Test password verification with empty hash."""
        result = self.auth_service.verify_password(self.test_password, "")
        assert result is False

    def test_get_user_existing(self):
        """Test getting an existing user."""
        user = self.auth_service.get_user("user@example.com")

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"
        assert "hashed_password" in user

    def test_get_user_nonexistent(self):
        """Test getting a non-existent user."""
        user = self.auth_service.get_user("nonexistent@example.com")
        assert user is None

    def test_get_user_none_username(self):
        """Test getting user with None username."""
        user = self.auth_service.get_user(None)
        assert user is None

    def test_get_user_empty_username(self):
        """Test getting user with empty username."""
        user = self.auth_service.get_user("")
        assert user is None

    def test_authenticate_user_success(self):
        """Test successful user authentication."""
        user = self.auth_service.authenticate_user("user@example.com", "password123")

        assert user is not None
        assert user["username"] == "user@example.com"
        assert user["email"] == "user@example.com"

    def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password."""
        user = self.auth_service.authenticate_user("user@example.com", "wrong_password")
        assert user is None

    def test_authenticate_user_nonexistent_user(self):
        """Test authentication with non-existent user."""
        user = self.auth_service.authenticate_user(
            "nonexistent@example.com", "password123"
        )
        assert user is None

    def test_authenticate_user_empty_credentials(self):
        """Test authentication with empty credentials."""
        user = self.auth_service.authenticate_user("", "")
        assert user is None

    def test_authenticate_user_none_credentials(self):
        """Test authentication with None credentials."""
        user = self.auth_service.authenticate_user(None, None)
        assert user is None

    def test_create_access_token_default_expiration(self):
        """Test creating access token with default expiration."""
        data = {"sub": self.test_username}
        token = self.auth_service.create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20

        # Decode and verify the token
        payload = jwt.decode(
            token,
            self.auth_service.secret_key,
            algorithms=[self.auth_service.algorithm],
        )
        assert payload["sub"] == self.test_username
        assert "exp" in payload

    def test_create_access_token_custom_expiration(self):
        """Test creating access token with custom expiration."""
        data = {"sub": self.test_username}
        expires_delta = timedelta(minutes=60)
        token = self.auth_service.create_access_token(data, expires_delta)

        assert token is not None

        # Decode and verify the token
        payload = jwt.decode(
            token,
            self.auth_service.secret_key,
            algorithms=[self.auth_service.algorithm],
        )
        assert payload["sub"] == self.test_username

        # Check expiration is roughly 60 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + expires_delta
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 10  # Within 10 seconds

    def test_create_access_token_additional_claims(self):
        """Test creating access token with additional claims."""
        data = {
            "sub": self.test_username,
            "role": "admin",
            "permissions": ["read", "write"],
        }
        token = self.auth_service.create_access_token(data)

        payload = jwt.decode(
            token,
            self.auth_service.secret_key,
            algorithms=[self.auth_service.algorithm],
        )
        assert payload["sub"] == self.test_username
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]

    def test_create_access_token_empty_data(self):
        """Test creating access token with empty data."""
        token = self.auth_service.create_access_token({})

        assert token is not None
        payload = jwt.decode(
            token,
            self.auth_service.secret_key,
            algorithms=[self.auth_service.algorithm],
        )
        assert "exp" in payload

    def test_get_current_user_valid_token(self):
        """Test getting current user with valid token."""
        # Create a valid token
        data = {"sub": "user@example.com"}
        token = self.auth_service.create_access_token(data)

        user = self.auth_service.get_current_user(token)

        assert user is not None
        assert user["username"] == "user@example.com"

    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        invalid_token = "invalid.token.string"

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(invalid_token)

    def test_get_current_user_expired_token(self):
        """Test getting current user with expired token."""
        # Create an expired token
        data = {"sub": "user@example.com"}
        past_time = datetime.utcnow() - timedelta(minutes=1)
        data["exp"] = past_time.timestamp()

        expired_token = jwt.encode(
            data, self.auth_service.secret_key, algorithm=self.auth_service.algorithm
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(expired_token)

    def test_get_current_user_malformed_token(self):
        """Test getting current user with malformed token."""
        malformed_token = "not.a.jwt"

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(malformed_token)

    def test_get_current_user_token_without_sub(self):
        """Test getting current user with token missing 'sub' claim."""
        data = {"role": "admin"}  # No 'sub' claim
        token = jwt.encode(
            data, self.auth_service.secret_key, algorithm=self.auth_service.algorithm
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(token)

    def test_get_current_user_token_with_none_sub(self):
        """Test getting current user with token having None 'sub' claim."""
        data = {"sub": None}
        token = jwt.encode(
            data, self.auth_service.secret_key, algorithm=self.auth_service.algorithm
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(token)

    def test_get_current_user_token_with_non_string_sub(self):
        """Test getting current user with token having non-string 'sub' claim."""
        data = {"sub": 123}  # Integer instead of string
        token = jwt.encode(
            data, self.auth_service.secret_key, algorithm=self.auth_service.algorithm
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(token)

    def test_get_current_user_nonexistent_user_in_token(self):
        """Test getting current user when user in token doesn't exist."""
        data = {"sub": "nonexistent@example.com"}
        token = self.auth_service.create_access_token(data)

        with pytest.raises(NotFoundError, match="User not found"):
            self.auth_service.get_current_user(token)

    def test_get_current_user_wrong_algorithm_token(self):
        """Test getting current user with token using wrong algorithm."""
        data = {"sub": "user@example.com"}
        wrong_algo_token = jwt.encode(
            data, self.auth_service.secret_key, algorithm="HS512"
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(wrong_algo_token)

    def test_get_current_user_wrong_secret_token(self):
        """Test getting current user with token signed with wrong secret."""
        data = {"sub": "user@example.com"}
        wrong_secret_token = jwt.encode(
            data, "wrong_secret", algorithm=self.auth_service.algorithm
        )

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(wrong_secret_token)

    @patch("app.services.auth_service.jwt.decode")
    def test_get_current_user_jwt_error(self, mock_decode):
        """Test JWT error handling in get_current_user."""
        mock_decode.side_effect = JWTError("JWT Error")

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user("any_token")

    def test_password_context_configuration(self):
        """Test password context is properly configured."""
        # Test that bcrypt is used and deprecated schemes are handled
        service = AuthService()

        assert "bcrypt" in service.pwd_context.schemes()
        assert service.pwd_context.deprecated == "auto"

    def test_user_database_initialization(self):
        """Test that user database is properly initialized."""
        service = AuthService()

        # Test default user exists
        assert "user@example.com" in service.users_db
        default_user = service.users_db["user@example.com"]

        assert default_user["username"] == "user@example.com"
        assert default_user["full_name"] == "Test User"
        assert default_user["email"] == "user@example.com"
        assert default_user["disabled"] is False
        assert "hashed_password" in default_user

        # Test password is properly hashed
        assert service.verify_password("password123", default_user["hashed_password"])

    def test_concurrent_token_operations(self):
        """Test concurrent token creation and validation."""
        import threading
        import time

        results = []
        errors = []

        def create_and_validate_token(username):
            try:
                data = {"sub": f"{username}@example.com"}
                token = self.auth_service.create_access_token(data)

                # Small delay to simulate concurrent access
                time.sleep(0.01)

                payload = jwt.decode(
                    token,
                    self.auth_service.secret_key,
                    algorithms=[self.auth_service.algorithm],
                )
                results.append(payload["sub"])
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=create_and_validate_token, args=[f"user{i}"]
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert len(set(results)) == 10  # All usernames should be unique

    def test_token_tampering_detection(self):
        """Test detection of tampered tokens."""
        # Create a valid token
        data = {"sub": "user@example.com"}
        token = self.auth_service.create_access_token(data)

        # Tamper with the token
        tampered_token = token[:-5] + "XXXXX"

        with pytest.raises(NotFoundError, match="Invalid token"):
            self.auth_service.get_current_user(tampered_token)

    def test_token_with_special_characters(self):
        """Test token creation with special characters in username."""
        special_username = "user+test@example-domain.com"
        data = {"sub": special_username}
        token = self.auth_service.create_access_token(data)

        # Verify token can be decoded
        payload = jwt.decode(
            token,
            self.auth_service.secret_key,
            algorithms=[self.auth_service.algorithm],
        )
        assert payload["sub"] == special_username

    def test_password_hash_collision_resistance(self):
        """Test that similar passwords produce different hashes."""
        similar_passwords = [
            "password123",
            "password124",
            "password12",
            "Password123",
            "passwoRd123",
        ]

        hashes = []
        for password in similar_passwords:
            hash_val = self.auth_service.get_password_hash(password)
            hashes.append(hash_val)

        # All hashes should be unique
        assert len(set(hashes)) == len(hashes)

    def test_auth_service_memory_usage(self):
        """Test that AuthService doesn't store sensitive data inappropriately."""
        service = AuthService()

        # Create a token
        data = {"sub": "test@example.com", "secret_data": "sensitive"}
        token = service.create_access_token(data)

        # The service itself shouldn't store the token or secret data
        service_dict = service.__dict__
        assert "secret_data" not in str(service_dict)
        assert token not in str(service_dict)

    def test_multiple_auth_service_instances(self):
        """Test multiple AuthService instances work independently."""
        service1 = AuthService()
        service2 = AuthService()

        # They should have same configuration but be different instances
        assert service1 is not service2
        assert service1.secret_key == service2.secret_key
        assert service1.algorithm == service2.algorithm

        # Tokens should be interchangeable
        data = {"sub": "user@example.com"}
        token1 = service1.create_access_token(data)

        # Service2 should be able to validate token from service1
        payload = jwt.decode(
            token1, service2.secret_key, algorithms=[service2.algorithm]
        )
        assert payload["sub"] == "user@example.com"


class TestGlobalAuthService:
    """Test the global auth_service instance."""

    def test_global_instance_exists(self):
        """Test that global auth_service instance exists."""
        assert auth_service is not None
        assert isinstance(auth_service, AuthService)

    def test_global_instance_functionality(self):
        """Test that global auth_service instance works correctly."""
        # Test password operations
        password = "test_password"
        hash_val = auth_service.get_password_hash(password)
        assert auth_service.verify_password(password, hash_val)

        # Test token operations
        data = {"sub": "test@example.com"}
        token = auth_service.create_access_token(data)
        assert token is not None


class TestAuthServiceErrorHandling:
    """Test error handling in AuthService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = AuthService()

    @patch("app.services.auth_service.CryptContext")
    def test_password_context_initialization_error(self, mock_context):
        """Test handling of password context initialization errors."""
        mock_context.side_effect = Exception("Context initialization failed")

        with pytest.raises(Exception):
            AuthService()

    @patch("app.services.auth_service.jwt.encode")
    def test_token_creation_error(self, mock_encode):
        """Test handling of token creation errors."""
        mock_encode.side_effect = Exception("Token encoding failed")

        with pytest.raises(Exception):
            self.auth_service.create_access_token({"sub": "test"})

    def test_invalid_password_hash_format(self):
        """Test handling of invalid password hash format."""
        # This should not raise an exception, just return False
        result = self.auth_service.verify_password("password", "invalid_hash_format")
        assert result is False

    def test_extremely_long_password(self):
        """Test handling of extremely long passwords."""
        long_password = "a" * 10000  # 10KB password

        # Should work without errors
        hash_val = self.auth_service.get_password_hash(long_password)
        assert self.auth_service.verify_password(long_password, hash_val)

    def test_unicode_password(self):
        """Test handling of Unicode passwords."""
        unicode_password = "пароль123αβγ🔒"

        hash_val = self.auth_service.get_password_hash(unicode_password)
        assert self.auth_service.verify_password(unicode_password, hash_val)

    def test_empty_token_validation(self):
        """Test validation of empty token."""
        with pytest.raises(NotFoundError):
            self.auth_service.get_current_user("")

    def test_whitespace_only_token(self):
        """Test validation of whitespace-only token."""
        with pytest.raises(NotFoundError):
            self.auth_service.get_current_user("   ")


class TestAuthServiceIntegration:
    """Integration tests for AuthService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = AuthService()

    def test_full_authentication_flow(self):
        """Test complete authentication flow."""
        username = "user@example.com"
        password = "password123"

        # 1. Authenticate user
        user = self.auth_service.authenticate_user(username, password)
        assert user is not None

        # 2. Create token
        token_data = {"sub": user["username"]}
        token = self.auth_service.create_access_token(token_data)

        # 3. Validate token
        current_user = self.auth_service.get_current_user(token)
        assert current_user["username"] == username

    def test_authentication_with_disabled_user(self):
        """Test authentication with disabled user."""
        # Add a disabled user to the database
        disabled_user = {
            "username": "disabled@example.com",
            "full_name": "Disabled User",
            "email": "disabled@example.com",
            "hashed_password": self.auth_service.get_password_hash("password"),
            "disabled": True,
        }
        self.auth_service.users_db["disabled@example.com"] = disabled_user

        # Authentication should still work (business logic handles disabled check)
        user = self.auth_service.authenticate_user("disabled@example.com", "password")
        assert user is not None
        assert user["disabled"] is True

    def test_token_refresh_simulation(self):
        """Test token refresh simulation."""
        username = "user@example.com"

        # Create initial token
        data = {"sub": username}
        old_token = self.auth_service.create_access_token(data)

        # Validate old token works
        user = self.auth_service.get_current_user(old_token)
        assert user["username"] == username

        # Create new token (refresh)
        new_token = self.auth_service.create_access_token(data)

        # Both tokens should work (until old one expires)
        user1 = self.auth_service.get_current_user(old_token)
        user2 = self.auth_service.get_current_user(new_token)
        assert user1["username"] == user2["username"]


class TestAuthServicePerformance:
    """Performance tests for AuthService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth_service = AuthService()

    def test_password_hashing_performance(self):
        """Test password hashing performance."""
        import time

        password = "test_password_123"
        start_time = time.time()

        # Hash 10 passwords
        for _ in range(10):
            self.auth_service.get_password_hash(password)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        assert duration < 5.0, f"Password hashing took too long: {duration}s"

    def test_token_creation_performance(self):
        """Test token creation performance."""
        import time

        data = {"sub": "user@example.com"}
        start_time = time.time()

        # Create 100 tokens
        for _ in range(100):
            self.auth_service.create_access_token(data)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly
        assert duration < 1.0, f"Token creation took too long: {duration}s"

    def test_token_validation_performance(self):
        """Test token validation performance."""
        import time

        # Create a token first
        data = {"sub": "user@example.com"}
        token = self.auth_service.create_access_token(data)

        start_time = time.time()

        # Validate token 100 times
        for _ in range(100):
            self.auth_service.get_current_user(token)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly
        assert duration < 1.0, f"Token validation took too long: {duration}s"
