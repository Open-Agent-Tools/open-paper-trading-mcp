"""Advanced comprehensive tests for app.core.exceptions module.

Tests custom exception classes, HTTP exception handling, error response patterns,
status codes, and exception hierarchy used in the paper trading platform.
"""

import pytest
from fastapi import HTTPException

from app.core.exceptions import (
    ConflictError,
    CustomException,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


class TestCustomExceptionBase:
    """Test CustomException base class functionality."""

    def test_custom_exception_inheritance(self):
        """Test that CustomException properly inherits from HTTPException."""
        assert issubclass(CustomException, HTTPException)

        # Test instantiation
        exception = CustomException(status_code=500, detail="Test error")
        assert isinstance(exception, HTTPException)
        assert isinstance(exception, CustomException)

    def test_custom_exception_basic_initialization(self):
        """Test basic CustomException initialization."""
        status_code = 500
        detail = "Internal server error"

        exception = CustomException(status_code=status_code, detail=detail)

        assert exception.status_code == status_code
        assert exception.detail == detail
        assert exception.headers is None

    def test_custom_exception_with_headers(self):
        """Test CustomException initialization with headers."""
        status_code = 401
        detail = "Unauthorized access"
        headers = {"WWW-Authenticate": "Bearer"}

        exception = CustomException(
            status_code=status_code, detail=detail, headers=headers
        )

        assert exception.status_code == status_code
        assert exception.detail == detail
        assert exception.headers == headers

    def test_custom_exception_none_detail(self):
        """Test CustomException with None detail."""
        exception = CustomException(status_code=400, detail=None)

        assert exception.status_code == 400
        assert exception.detail is None

    def test_custom_exception_none_headers(self):
        """Test CustomException with explicitly None headers."""
        exception = CustomException(status_code=400, detail="Bad request", headers=None)

        assert exception.status_code == 400
        assert exception.detail == "Bad request"
        assert exception.headers is None

    def test_custom_exception_str_representation(self):
        """Test string representation of CustomException."""
        detail = "Test error message"
        exception = CustomException(status_code=500, detail=detail)

        # HTTPException's __str__ method should be used
        str_repr = str(exception)
        assert isinstance(str_repr, str)

    def test_custom_exception_with_complex_detail(self):
        """Test CustomException with complex detail objects."""
        complex_detail = {
            "error": "Validation failed",
            "fields": ["username", "email"],
            "code": "VALIDATION_ERROR",
        }

        exception = CustomException(status_code=422, detail=complex_detail)

        assert exception.status_code == 422
        assert exception.detail == complex_detail
        assert isinstance(exception.detail, dict)


class TestValidationErrorException:
    """Test ValidationError exception class."""

    def test_validation_error_default_initialization(self):
        """Test ValidationError with default parameters."""
        exception = ValidationError()

        assert exception.status_code == 422
        assert exception.detail == "Validation error"
        assert isinstance(exception, CustomException)
        assert isinstance(exception, HTTPException)

    def test_validation_error_custom_detail(self):
        """Test ValidationError with custom detail message."""
        custom_detail = "Username must be at least 3 characters long"
        exception = ValidationError(detail=custom_detail)

        assert exception.status_code == 422
        assert exception.detail == custom_detail

    def test_validation_error_inheritance_chain(self):
        """Test ValidationError inheritance chain."""
        exception = ValidationError()

        assert isinstance(exception, ValidationError)
        assert isinstance(exception, CustomException)
        assert isinstance(exception, HTTPException)
        assert issubclass(ValidationError, CustomException)
        assert issubclass(ValidationError, HTTPException)

    def test_validation_error_status_code_immutable(self):
        """Test that ValidationError status code is fixed at 422."""
        # Even if we try to pass different status_code in initialization,
        # it should be 422 due to super().__init__ call
        exception = ValidationError(detail="Custom validation error")
        assert exception.status_code == 422

    def test_validation_error_with_structured_detail(self):
        """Test ValidationError with structured detail information."""
        structured_detail = {
            "message": "Validation failed",
            "errors": [
                {"field": "email", "message": "Invalid email format"},
                {"field": "age", "message": "Must be positive integer"},
            ],
        }

        exception = ValidationError(detail=structured_detail)

        assert exception.status_code == 422
        assert exception.detail == structured_detail
        assert "errors" in exception.detail


class TestNotFoundErrorException:
    """Test NotFoundError exception class."""

    def test_not_found_error_default_initialization(self):
        """Test NotFoundError with default parameters."""
        exception = NotFoundError()

        assert exception.status_code == 404
        assert exception.detail == "Resource not found"
        assert isinstance(exception, CustomException)

    def test_not_found_error_custom_detail(self):
        """Test NotFoundError with custom detail message."""
        custom_detail = "User with ID 123 not found"
        exception = NotFoundError(detail=custom_detail)

        assert exception.status_code == 404
        assert exception.detail == custom_detail

    def test_not_found_error_resource_specific(self):
        """Test NotFoundError with resource-specific messages."""
        test_cases = [
            "Account not found",
            "Order with ID 456 does not exist",
            "Position not found for symbol AAPL",
            "Trading session not found",
        ]

        for detail in test_cases:
            exception = NotFoundError(detail=detail)
            assert exception.status_code == 404
            assert exception.detail == detail

    def test_not_found_error_inheritance(self):
        """Test NotFoundError inheritance chain."""
        exception = NotFoundError()

        assert isinstance(exception, NotFoundError)
        assert isinstance(exception, CustomException)
        assert isinstance(exception, HTTPException)


class TestUnauthorizedErrorException:
    """Test UnauthorizedError exception class."""

    def test_unauthorized_error_default_initialization(self):
        """Test UnauthorizedError with default parameters."""
        exception = UnauthorizedError()

        assert exception.status_code == 401
        assert exception.detail == "Unauthorized"
        assert isinstance(exception, CustomException)

    def test_unauthorized_error_custom_detail(self):
        """Test UnauthorizedError with custom detail message."""
        custom_detail = "Invalid authentication credentials"
        exception = UnauthorizedError(detail=custom_detail)

        assert exception.status_code == 401
        assert exception.detail == custom_detail

    def test_unauthorized_error_authentication_scenarios(self):
        """Test UnauthorizedError for different authentication scenarios."""
        scenarios = [
            "Missing authentication token",
            "Invalid JWT token",
            "Token has expired",
            "Authentication failed",
        ]

        for detail in scenarios:
            exception = UnauthorizedError(detail=detail)
            assert exception.status_code == 401
            assert exception.detail == detail

    def test_unauthorized_error_with_headers(self):
        """Test UnauthorizedError usage with authentication headers."""
        # Note: Headers would be set at a higher level, but we can test the structure
        exception = UnauthorizedError(detail="Token required")

        assert exception.status_code == 401
        assert exception.detail == "Token required"
        # Headers would typically be added by FastAPI middleware or route handlers


class TestForbiddenErrorException:
    """Test ForbiddenError exception class."""

    def test_forbidden_error_default_initialization(self):
        """Test ForbiddenError with default parameters."""
        exception = ForbiddenError()

        assert exception.status_code == 403
        assert exception.detail == "Forbidden"
        assert isinstance(exception, CustomException)

    def test_forbidden_error_custom_detail(self):
        """Test ForbiddenError with custom detail message."""
        custom_detail = "Insufficient permissions to access this resource"
        exception = ForbiddenError(detail=custom_detail)

        assert exception.status_code == 403
        assert exception.detail == custom_detail

    def test_forbidden_error_authorization_scenarios(self):
        """Test ForbiddenError for different authorization scenarios."""
        scenarios = [
            "Access denied",
            "User does not have permission to perform this action",
            "Admin privileges required",
            "Resource access restricted",
        ]

        for detail in scenarios:
            exception = ForbiddenError(detail=detail)
            assert exception.status_code == 403
            assert exception.detail == detail

    def test_forbidden_vs_unauthorized_distinction(self):
        """Test distinction between ForbiddenError (403) and UnauthorizedError (401)."""
        # 401 - Authentication required
        unauthorized = UnauthorizedError(detail="Please log in")
        assert unauthorized.status_code == 401

        # 403 - Authorization failed (user is authenticated but lacks permission)
        forbidden = ForbiddenError(detail="Admin access required")
        assert forbidden.status_code == 403

        assert unauthorized.status_code != forbidden.status_code


class TestConflictErrorException:
    """Test ConflictError exception class."""

    def test_conflict_error_default_initialization(self):
        """Test ConflictError with default parameters."""
        exception = ConflictError()

        assert exception.status_code == 409
        assert exception.detail == "Conflict"
        assert isinstance(exception, CustomException)

    def test_conflict_error_custom_detail(self):
        """Test ConflictError with custom detail message."""
        custom_detail = "Username already exists"
        exception = ConflictError(detail=custom_detail)

        assert exception.status_code == 409
        assert exception.detail == custom_detail

    def test_conflict_error_business_logic_scenarios(self):
        """Test ConflictError for business logic conflict scenarios."""
        scenarios = [
            "Order already filled",
            "Account already exists",
            "Position conflict detected",
            "Duplicate transaction detected",
            "Resource state conflict",
        ]

        for detail in scenarios:
            exception = ConflictError(detail=detail)
            assert exception.status_code == 409
            assert exception.detail == detail

    def test_conflict_error_trading_scenarios(self):
        """Test ConflictError for trading-specific conflict scenarios."""
        trading_conflicts = [
            "Cannot sell more shares than owned",
            "Order already exists for this symbol",
            "Market is closed for trading",
            "Insufficient buying power",
        ]

        for detail in trading_conflicts:
            exception = ConflictError(detail=detail)
            assert exception.status_code == 409
            assert exception.detail == detail


class TestExceptionHierarchyAndPolymorphism:
    """Test exception hierarchy and polymorphic behavior."""

    def test_all_exceptions_inherit_from_custom_exception(self):
        """Test that all custom exceptions inherit from CustomException."""
        exception_classes = [
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
        ]

        for exception_class in exception_classes:
            assert issubclass(exception_class, CustomException)

            # Test instantiation
            instance = exception_class()
            assert isinstance(instance, CustomException)
            assert isinstance(instance, HTTPException)

    def test_polymorphic_exception_handling(self):
        """Test polymorphic exception handling patterns."""
        exceptions = [
            ValidationError("Validation failed"),
            NotFoundError("Resource not found"),
            UnauthorizedError("Auth failed"),
            ForbiddenError("Access denied"),
            ConflictError("Conflict occurred"),
        ]

        for exception in exceptions:
            # All should be treatable as CustomException
            assert isinstance(exception, CustomException)
            assert isinstance(exception, HTTPException)
            assert hasattr(exception, "status_code")
            assert hasattr(exception, "detail")

    def test_exception_status_code_uniqueness(self):
        """Test that different exception types have different status codes."""
        status_codes = {
            ValidationError: 422,
            NotFoundError: 404,
            UnauthorizedError: 401,
            ForbiddenError: 403,
            ConflictError: 409,
        }

        for exception_class, expected_status in status_codes.items():
            instance = exception_class()
            assert instance.status_code == expected_status

        # Verify all status codes are different
        all_status_codes = list(status_codes.values())
        assert len(all_status_codes) == len(set(all_status_codes))

    def test_exception_catching_hierarchy(self):
        """Test exception catching hierarchy patterns."""
        # Test that CustomException can catch all custom exceptions
        for exception_class in [
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
        ]:
            try:
                raise exception_class("Test error")
            except CustomException as e:
                assert isinstance(e, exception_class)
                assert isinstance(e, CustomException)
            except Exception:
                pytest.fail(f"{exception_class} should be catchable as CustomException")


class TestExceptionUsagePatterns:
    """Test common exception usage patterns in the application."""

    def test_exception_with_fastapi_error_handling(self):
        """Test exception integration with FastAPI error handling patterns."""

        # Simulate FastAPI endpoint raising custom exceptions
        def mock_endpoint_validation():
            raise ValidationError("Invalid input data")

        def mock_endpoint_not_found():
            raise NotFoundError("Order not found")

        def mock_endpoint_unauthorized():
            raise UnauthorizedError("Token expired")

        # Test that exceptions can be raised and caught appropriately
        with pytest.raises(ValidationError) as exc_info:
            mock_endpoint_validation()
        assert exc_info.value.status_code == 422

        with pytest.raises(NotFoundError) as exc_info:
            mock_endpoint_not_found()
        assert exc_info.value.status_code == 404

        with pytest.raises(UnauthorizedError) as exc_info:
            mock_endpoint_unauthorized()
        assert exc_info.value.status_code == 401

    def test_exception_detail_formatting_patterns(self):
        """Test different detail formatting patterns."""
        # String detail
        str_exception = ValidationError("Simple string error")
        assert isinstance(str_exception.detail, str)

        # Dictionary detail
        dict_detail = {
            "message": "Validation error",
            "field": "email",
            "value": "invalid-email",
        }
        dict_exception = ValidationError(detail=dict_detail)
        assert isinstance(dict_exception.detail, dict)

        # List detail
        list_detail = ["Error 1", "Error 2", "Error 3"]
        list_exception = ValidationError(detail=list_detail)
        assert isinstance(list_exception.detail, list)

    def test_exception_chaining_patterns(self):
        """Test exception chaining and cause tracking patterns."""
        # Test that exceptions can be raised with cause information
        original_error = ValueError("Original error")

        try:
            try:
                raise original_error
            except ValueError as e:
                raise ValidationError("Validation failed due to value error") from e
        except ValidationError as validation_error:
            assert validation_error.status_code == 422
            assert validation_error.__cause__ is original_error

    def test_exception_context_manager_patterns(self):
        """Test exception usage in context manager patterns."""

        # Test that exceptions work properly in context managers
        class MockContextManager:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is ValueError:
                    # Convert ValueError to ValidationError
                    raise ValidationError("Invalid value in context") from exc_val
                return False

        with pytest.raises(ValidationError), MockContextManager():
            raise ValueError("Test error")


class TestExceptionAPIDesignPatterns:
    """Test exception API design and integration patterns."""

    def test_exception_serialization_compatibility(self):
        """Test that exceptions are compatible with FastAPI serialization."""
        exceptions = [
            ValidationError("Validation error"),
            NotFoundError("Not found"),
            UnauthorizedError("Unauthorized"),
            ForbiddenError("Forbidden"),
            ConflictError("Conflict"),
        ]

        for exception in exceptions:
            # Test that exception attributes are accessible
            assert hasattr(exception, "status_code")
            assert hasattr(exception, "detail")
            assert hasattr(exception, "headers")

            # Test that status_code is an integer
            assert isinstance(exception.status_code, int)

            # Test that detail can be various types
            assert exception.detail is not None

    def test_exception_logging_integration(self):
        """Test exception integration with logging patterns."""
        import logging

        # Test that exceptions can be logged with proper context
        logger = logging.getLogger("test_logger")

        exceptions = [
            ValidationError("Validation failed for user input"),
            NotFoundError("User ID 123 not found"),
            UnauthorizedError("Invalid API key"),
        ]

        for exception in exceptions:
            # Should be able to log exception details
            try:
                error_context = {
                    "status_code": exception.status_code,
                    "detail": exception.detail,
                    "exception_type": type(exception).__name__,
                }
                logger.error("Exception occurred: %s", error_context)
            except Exception as e:
                pytest.fail(f"Exception logging should not fail: {e}")

    def test_exception_middleware_compatibility(self):
        """Test exception compatibility with FastAPI middleware patterns."""

        # Simulate middleware exception handling
        def simulate_exception_middleware(exception: HTTPException):
            return {
                "error": True,
                "status_code": exception.status_code,
                "detail": exception.detail,
                "type": type(exception).__name__,
            }

        test_exceptions = [
            ValidationError("Invalid data"),
            NotFoundError("Resource missing"),
            UnauthorizedError("Access denied"),
            ForbiddenError("Permission denied"),
            ConflictError("State conflict"),
        ]

        for exception in test_exceptions:
            result = simulate_exception_middleware(exception)

            assert result["error"] is True
            assert result["status_code"] == exception.status_code
            assert result["detail"] == exception.detail
            assert result["type"] == type(exception).__name__

    def test_exception_response_structure(self):
        """Test that exceptions provide consistent response structure."""
        # All exceptions should provide consistent interface for FastAPI
        exception_types = [
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
        ]

        for exception_type in exception_types:
            # Test with default initialization
            default_exception = exception_type()
            assert hasattr(default_exception, "status_code")
            assert hasattr(default_exception, "detail")
            assert default_exception.status_code > 0
            assert default_exception.detail is not None

            # Test with custom detail
            custom_exception = exception_type(detail="Custom error message")
            assert custom_exception.detail == "Custom error message"


class TestExceptionDocumentationAndMetadata:
    """Test exception documentation and metadata patterns."""

    def test_exception_class_docstrings(self):
        """Test that exception classes have appropriate documentation."""
        exception_classes = [
            CustomException,
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
        ]

        # Note: The actual exception classes might not have docstrings,
        # but we can test that they're accessible for documentation
        for exception_class in exception_classes:
            assert hasattr(exception_class, "__name__")
            assert hasattr(exception_class, "__module__")
            assert exception_class.__name__ is not None
            assert exception_class.__module__ is not None

    def test_exception_module_structure(self):
        """Test exception module structure and exports."""
        import app.core.exceptions as exceptions_module

        # Test that all exceptions are properly exported
        expected_exceptions = [
            "CustomException",
            "ValidationError",
            "NotFoundError",
            "UnauthorizedError",
            "ForbiddenError",
            "ConflictError",
        ]

        for exception_name in expected_exceptions:
            assert hasattr(exceptions_module, exception_name)
            exception_class = getattr(exceptions_module, exception_name)
            assert callable(exception_class)
            assert issubclass(exception_class, Exception)

    def test_exception_type_annotations(self):
        """Test that exception constructors have proper type annotations."""
        from typing import get_type_hints

        # Test CustomException annotations
        custom_exception_hints = get_type_hints(CustomException.__init__)
        # Check that status_code is annotated as int
        assert "status_code" in custom_exception_hints
        assert custom_exception_hints["status_code"] == int
