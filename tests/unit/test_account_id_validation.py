"""
Tests for account ID validation and generation.
"""
import pytest
from pydantic import ValidationError

from app.core.id_utils import generate_account_id, is_valid_account_id, validate_account_id
from app.schemas.accounts import Account


class TestAccountIdGeneration:
    """Test account ID generation."""

    def test_generate_account_id_format(self):
        """Test that generated account IDs meet format requirements."""
        for _ in range(100):  # Test multiple generations
            account_id = generate_account_id()
            assert len(account_id) == 10
            assert account_id.isalnum()
            assert account_id.isupper()

    def test_generate_account_id_uniqueness(self):
        """Test that generated account IDs are unique."""
        ids = set()
        for _ in range(1000):
            account_id = generate_account_id()
            assert account_id not in ids, f"Duplicate ID generated: {account_id}"
            ids.add(account_id)


class TestAccountIdValidation:
    """Test account ID validation logic."""

    def test_valid_account_ids(self):
        """Test that valid account IDs pass validation."""
        valid_ids = [
            "A1B2C3D4E5",
            "XYZ1234567",
            "ABCDEFGHIJ",
            "1234567890",
            "Z9Y8X7W6V5",
        ]
        
        for account_id in valid_ids:
            assert is_valid_account_id(account_id), f"Should be valid: {account_id}"
            assert validate_account_id(account_id) == account_id

    def test_invalid_account_ids(self):
        """Test that invalid account IDs fail validation."""
        invalid_ids = [
            "short",           # Too short
            "toolongforsure",  # Too long
            "a1b2c3d4e5",      # Lowercase letters
            "A1B2C3D4E",       # Only 9 characters
            "A1B2C3D4E5X",     # 11 characters
            "A1B2-C3D4E",      # Contains hyphen
            "A1B2_C3D4E",      # Contains underscore
            "A1B2 C3D4E",      # Contains space
            "",                # Empty
            None,              # None value
            123,               # Not a string
        ]
        
        for account_id in invalid_ids:
            assert not is_valid_account_id(account_id), f"Should be invalid: {account_id}"
            
            if isinstance(account_id, str):
                with pytest.raises(ValueError, match="Invalid account ID format"):
                    validate_account_id(account_id)


class TestAccountSchemaValidation:
    """Test account schema validation with new ID constraints."""

    def test_account_with_valid_id(self):
        """Test that account schema accepts valid IDs."""
        valid_account_data = {
            "id": "TEST123456",
            "cash_balance": 100000.0,
            "owner": "test_user",
            "positions": []
        }
        
        account = Account(**valid_account_data)
        assert account.id == "TEST123456"
        assert account.cash_balance == 100000.0

    def test_account_with_invalid_id(self):
        """Test that account schema rejects invalid IDs."""
        invalid_account_data = {
            "id": "invalid",  # Too short
            "cash_balance": 100000.0,
            "owner": "test_user",
            "positions": []
        }
        
        with pytest.raises(ValidationError) as exc_info:
            Account(**invalid_account_data)
        
        assert "Invalid account ID format" in str(exc_info.value)

    def test_account_schema_validation_comprehensive(self):
        """Test comprehensive account validation scenarios."""
        test_cases = [
            {
                "id": "TESTACCT01",
                "cash_balance": 50000.0,
                "owner": "trader1",
                "should_pass": True
            },
            {
                "id": "lowercase1",  # Invalid: lowercase
                "cash_balance": 50000.0,
                "owner": "trader2",
                "should_pass": False
            },
            {
                "id": "SHORT",  # Invalid: too short
                "cash_balance": 50000.0,
                "owner": "trader3",
                "should_pass": False
            },
            {
                "id": "TOOLONGACCOUNT",  # Invalid: too long
                "cash_balance": 50000.0,
                "owner": "trader4",
                "should_pass": False
            }
        ]
        
        for case in test_cases:
            if case["should_pass"]:
                account = Account(
                    id=case["id"],
                    cash_balance=case["cash_balance"],
                    owner=case["owner"],
                    positions=[]
                )
                assert account.id == case["id"]
            else:
                with pytest.raises(ValidationError):
                    Account(
                        id=case["id"],
                        cash_balance=case["cash_balance"],
                        owner=case["owner"],
                        positions=[]
                    )


class TestAccountIdIntegration:
    """Integration tests for account ID functionality."""

    def test_generated_ids_pass_validation(self):
        """Test that all generated IDs pass validation."""
        for _ in range(50):
            generated_id = generate_account_id()
            assert is_valid_account_id(generated_id)
            assert validate_account_id(generated_id) == generated_id
            
            # Should also work in Account schema
            account = Account(
                id=generated_id,
                cash_balance=100000.0,
                owner="test_user",
                positions=[]
            )
            assert account.id == generated_id