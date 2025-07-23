"""
Authentication service for handling user authentication and authorization.
"""

from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import NotFoundError


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = (
            settings.SECRET_KEY if hasattr(settings, "SECRET_KEY") else "secret"
        )
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30

        # Mock user database - in production this would be in a real database
        self.users_db = {
            "user@example.com": {
                "username": "user@example.com",
                "full_name": "Test User",
                "email": "user@example.com",
                "hashed_password": self.get_password_hash("password123"),
                "disabled": False,
            }
        }

    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return str(self.pwd_context.hash(password))

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bool(self.pwd_context.verify(plain_password, hashed_password))

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Get user by username."""
        if username in self.users_db:
            return self.users_db[username]
        return None

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        """Authenticate a user with username and password."""
        user = self.get_user(username)
        if not user:
            return None
        if not self.verify_password(password, user["hashed_password"]):
            return None
        return user

    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.access_token_expire_minutes
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return str(encoded_jwt)

    def get_current_user(self, token: str) -> dict[str, Any]:
        """Get current user from JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username = payload.get("sub")
            if not isinstance(username, str) or username is None:
                raise NotFoundError("Invalid token")
        except JWTError:
            raise NotFoundError("Invalid token")

        user = self.get_user(username)
        if user is None:
            raise NotFoundError("User not found")
        return user


# Global service instance
auth_service = AuthService()
