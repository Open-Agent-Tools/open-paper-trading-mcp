"""
Advanced test coverage for account schemas.

Tests account schema validation, serialization, deserialization,
validation mixins, and backward compatibility patterns.
"""

import pytest
from pydantic import ValidationError

from app.models.assets import Stock
from app.schemas.accounts import Account
from app.schemas.positions import Position


class TestAccountSchema:
    """Test Account schema validation and serialization."""

    def test_account_creation_minimal(self):
        """Test creating account with minimal required fields."""
        account = Account(
            id="test_123",
            cash_balance=1000.0
        )
        
        assert account.id == "test_123"
        assert account.cash_balance == 1000.0
        assert account.positions == []
        assert account.name is None
        assert account.owner is None

    def test_account_creation_full(self):
        """Test creating account with all fields."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0
        )
        
        account = Account(
            id="test_456",
            cash_balance=5000.0,
            positions=[position],
            name="Test Account",
            owner="Test Owner"
        )
        
        assert account.id == "test_456"
        assert account.cash_balance == 5000.0
        assert len(account.positions) == 1
        assert account.positions[0].symbol == "AAPL"
        assert account.name == "Test Account"
        assert account.owner == "Test Owner"

    def test_cash_property_alias(self):
        """Test backward compatibility cash property."""
        account = Account(
            id="test_789",
            cash_balance=2500.0
        )
        
        assert account.cash == 2500.0
        assert account.cash_balance == 2500.0

    def test_account_serialization(self):
        """Test account model serialization."""
        position = Position(
            symbol="GOOGL",
            quantity=50,
            avg_price=2800.0,
            current_price=2850.0,
            unrealized_pnl=2500.0
        )
        
        account = Account(
            id="serialize_test",
            cash_balance=10000.0,
            positions=[position],
            name="Serialization Test",
            owner="Test User"
        )
        
        data = account.model_dump()
        
        assert data["id"] == "serialize_test"
        assert data["cash_balance"] == 10000.0
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "GOOGL"
        assert data["name"] == "Serialization Test"
        assert data["owner"] == "Test User"

    def test_account_deserialization(self):
        """Test creating account from dictionary data."""
        data = {
            "id": "deserialize_test",
            "cash_balance": 7500.0,
            "positions": [
                {
                    "symbol": "MSFT",
                    "quantity": 200,
                    "avg_price": 300.0,
                    "current_price": 310.0,
                    "unrealized_pnl": 2000.0,
                    "realized_pnl": 0.0
                }
            ],
            "name": "Deserialization Test",
            "owner": "Test Owner"
        }
        
        account = Account(**data)
        
        assert account.id == "deserialize_test"
        assert account.cash_balance == 7500.0
        assert len(account.positions) == 1
        assert account.positions[0].symbol == "MSFT"
        assert account.positions[0].quantity == 200


class TestAccountValidationMixin:
    """Test AccountValidationMixin validation rules."""

    def test_valid_cash_balance(self):
        """Test valid cash balance validation."""
        account = Account(
            id="cash_test",
            cash_balance=1000.0
        )
        assert account.cash_balance == 1000.0

    def test_zero_cash_balance(self):
        """Test zero cash balance is allowed."""
        account = Account(
            id="zero_cash_test",
            cash_balance=0.0
        )
        assert account.cash_balance == 0.0

    def test_negative_cash_balance_validation(self):
        """Test negative cash balance validation."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="negative_test",
                cash_balance=-1000.0
            )
        
        error = exc_info.value.errors()[0]
        assert "Cash balance cannot be negative" in error["msg"]

    def test_valid_owner_validation(self):
        """Test valid owner field validation."""
        account = Account(
            id="owner_test",
            cash_balance=1000.0,
            owner="Valid Owner"
        )
        assert account.owner == "Valid Owner"

    def test_empty_owner_validation(self):
        """Test empty owner string validation."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="empty_owner_test",
                cash_balance=1000.0,
                owner=""
            )
        
        error = exc_info.value.errors()[0]
        assert "Owner cannot be empty" in error["msg"]

    def test_whitespace_only_owner_validation(self):
        """Test whitespace-only owner validation."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="whitespace_owner_test",
                cash_balance=1000.0,
                owner="   "
            )
        
        error = exc_info.value.errors()[0]
        assert "Owner cannot be empty" in error["msg"]

    def test_owner_trimming(self):
        """Test owner field gets trimmed."""
        account = Account(
            id="trim_owner_test",
            cash_balance=1000.0,
            owner="  Trimmed Owner  "
        )
        assert account.owner == "Trimmed Owner"

    def test_valid_name_validation(self):
        """Test valid name field validation."""
        account = Account(
            id="name_test",
            cash_balance=1000.0,
            name="Valid Name"
        )
        assert account.name == "Valid Name"

    def test_empty_name_validation(self):
        """Test empty name string validation."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="empty_name_test",
                cash_balance=1000.0,
                name=""
            )
        
        error = exc_info.value.errors()[0]
        assert "Name cannot be empty" in error["msg"]

    def test_whitespace_only_name_validation(self):
        """Test whitespace-only name validation."""
        with pytest.raises(ValidationError) as exc_info:
            Account(
                id="whitespace_name_test",
                cash_balance=1000.0,
                name="   "
            )
        
        error = exc_info.value.errors()[0]
        assert "Name cannot be empty" in error["msg"]

    def test_name_trimming(self):
        """Test name field gets trimmed."""
        account = Account(
            id="trim_name_test",
            cash_balance=1000.0,
            name="  Trimmed Name  "
        )
        assert account.name == "Trimmed Name"

    def test_none_owner_and_name_allowed(self):
        """Test None values are allowed for optional fields."""
        account = Account(
            id="none_test",
            cash_balance=1000.0,
            owner=None,
            name=None
        )
        assert account.owner is None
        assert account.name is None


class TestAccountPositionsIntegration:
    """Test account schema with positions integration."""

    def test_account_with_stock_positions(self):
        """Test account with stock positions."""
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                current_price=155.0
            ),
            Position(
                symbol="GOOGL",
                quantity=50,
                avg_price=2800.0,
                current_price=2850.0
            )
        ]
        
        account = Account(
            id="stock_positions_test",
            cash_balance=5000.0,
            positions=positions
        )
        
        assert len(account.positions) == 2
        assert account.positions[0].symbol == "AAPL"
        assert account.positions[1].symbol == "GOOGL"

    def test_account_with_options_positions(self):
        """Test account with options positions."""
        option_position = Position(
            symbol="AAPL240119C00195000",
            quantity=10,
            avg_price=5.50,
            current_price=6.00,
            option_type="call",
            strike=195.0,
            underlying_symbol="AAPL"
        )
        
        account = Account(
            id="options_positions_test",
            cash_balance=3000.0,
            positions=[option_position]
        )
        
        assert len(account.positions) == 1
        position = account.positions[0]
        assert position.option_type == "call"
        assert position.strike == 195.0
        assert position.underlying_symbol == "AAPL"

    def test_account_with_mixed_positions(self):
        """Test account with mixed stock and options positions."""
        stock_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0
        )
        
        option_position = Position(
            symbol="AAPL240119P00145000",
            quantity=-5,
            avg_price=3.50,
            option_type="put",
            strike=145.0,
            underlying_symbol="AAPL"
        )
        
        account = Account(
            id="mixed_positions_test",
            cash_balance=8000.0,
            positions=[stock_position, option_position]
        )
        
        assert len(account.positions) == 2
        assert account.positions[0].symbol == "AAPL"
        assert account.positions[1].option_type == "put"

    def test_account_empty_positions_default(self):
        """Test account with default empty positions list."""
        account = Account(
            id="empty_positions_test",
            cash_balance=1000.0
        )
        
        assert account.positions == []
        assert isinstance(account.positions, list)


class TestAccountFromAttributesConfig:
    """Test Account model from_attributes configuration."""

    def test_from_attributes_configuration(self):
        """Test model can be created from object attributes."""
        # Simulate database object with attributes
        class MockDbAccount:
            def __init__(self):
                self.id = "from_attrs_test"
                self.cash_balance = 2500.0
                self.positions = []
                self.name = "From Attributes"
                self.owner = "DB Owner"
        
        db_account = MockDbAccount()
        account = Account.model_validate(db_account)
        
        assert account.id == "from_attrs_test"
        assert account.cash_balance == 2500.0
        assert account.name == "From Attributes"
        assert account.owner == "DB Owner"


class TestAccountEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_cash_balance(self):
        """Test account with very large cash balance."""
        large_balance = 1e12  # 1 trillion
        account = Account(
            id="large_balance_test",
            cash_balance=large_balance
        )
        assert account.cash_balance == large_balance

    def test_very_long_id(self):
        """Test account with very long ID."""
        long_id = "a" * 1000
        account = Account(
            id=long_id,
            cash_balance=1000.0
        )
        assert account.id == long_id

    def test_special_characters_in_fields(self):
        """Test special characters in string fields."""
        account = Account(
            id="special-chars_123!@#",
            cash_balance=1000.0,
            name="Account with Special Chars! @#$%",
            owner="Owner with Émojis 🚀📈"
        )
        
        assert account.id == "special-chars_123!@#"
        assert account.name == "Account with Special Chars! @#$%"
        assert account.owner == "Owner with Émojis 🚀📈"

    def test_unicode_in_fields(self):
        """Test Unicode characters in string fields."""
        account = Account(
            id="unicode_测试_123",
            cash_balance=1000.0,
            name="测试账户",
            owner="用户名"
        )
        
        assert account.id == "unicode_测试_123"
        assert account.name == "测试账户"
        assert account.owner == "用户名"


class TestAccountJSONSerialization:
    """Test JSON serialization and deserialization patterns."""

    def test_json_serialization_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original_account = Account(
            id="json_test",
            cash_balance=5000.0,
            name="JSON Test",
            owner="JSON Owner"
        )
        
        # Serialize to JSON-compatible dict
        json_data = original_account.model_dump()
        
        # Deserialize back to model
        restored_account = Account(**json_data)
        
        assert restored_account.id == original_account.id
        assert restored_account.cash_balance == original_account.cash_balance
        assert restored_account.name == original_account.name
        assert restored_account.owner == original_account.owner

    def test_json_with_positions_roundtrip(self):
        """Test JSON serialization with positions roundtrip."""
        position = Position(
            symbol="TSLA",
            quantity=25,
            avg_price=800.0,
            current_price=850.0,
            unrealized_pnl=1250.0
        )
        
        original_account = Account(
            id="json_positions_test",
            cash_balance=3000.0,
            positions=[position]
        )
        
        # Serialize to JSON-compatible dict
        json_data = original_account.model_dump()
        
        # Deserialize back to model
        restored_account = Account(**json_data)
        
        assert len(restored_account.positions) == 1
        assert restored_account.positions[0].symbol == "TSLA"
        assert restored_account.positions[0].quantity == 25
        assert restored_account.positions[0].avg_price == 800.0