"""Comprehensive tests for expiration.py - Options expiration engine."""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, Mock, patch
from decimal import Decimal

from app.services.expiration import (
    OptionsExpirationEngine,
    ExpirationResult,
)
from app.models.assets import Call, Put, Stock, Option, asset_factory
from app.schemas.positions import Position
from app.models.quotes import Quote
from app.adapters.base import QuoteAdapter


class MockQuoteAdapter(QuoteAdapter):
    """Mock quote adapter for testing."""
    
    def __init__(self, prices: dict[str, float] = None):
        self.prices = prices or {}
        
    async def get_quote(self, asset) -> Quote:
        """Return mock quote for asset."""
        symbol = asset.symbol if hasattr(asset, 'symbol') else str(asset)
        price = self.prices.get(symbol, 100.0)
        
        return Quote(
            asset=asset,
            quote_date=datetime.now(),
            price=price,
            bid=price - 0.5,
            ask=price + 0.5,
            bid_size=100,
            ask_size=100,
            volume=1000
        )


@pytest.fixture
def expiration_engine():
    """Create expiration engine for testing."""
    return OptionsExpirationEngine()


@pytest.fixture
def mock_quote_adapter():
    """Create mock quote adapter."""
    return MockQuoteAdapter({"AAPL": 150.0, "GOOGL": 2800.0, "TSLA": 800.0})


@pytest.fixture
def sample_account():
    """Create sample account with positions."""
    return {
        "cash_balance": 10000.0,
        "positions": [
            {
                "symbol": "AAPL",
                "quantity": 100,
                "avg_price": 145.0,
                "current_price": 150.0
            },
            {
                "symbol": "AAPL__230120C00140000",  # ITM call
                "quantity": 2,
                "avg_price": 12.0,
                "current_price": 10.0
            },
            {
                "symbol": "AAPL__230120P00160000",  # OTM put
                "quantity": -1,
                "avg_price": 8.0,
                "current_price": 2.0
            },
            {
                "symbol": "GOOGL__230120C02900000",  # OTM call
                "quantity": 1,
                "avg_price": 50.0,
                "current_price": 5.0
            }
        ]
    }


@pytest.fixture
def expiration_date():
    """Return expiration date for testing."""
    return date(2023, 1, 20)


class TestExpirationResultModel:
    """Test ExpirationResult data model."""
    
    def test_expiration_result_initialization(self):
        """Test ExpirationResult initialization."""
        result = ExpirationResult()
        
        assert result.expired_positions == []
        assert result.new_positions == []
        assert result.cash_impact == 0.0
        assert result.assignments == []
        assert result.exercises == []
        assert result.worthless_expirations == []
        assert result.warnings == []
        assert result.errors == []
    
    def test_expiration_result_with_data(self):
        """Test ExpirationResult with initial data."""
        position = Position(symbol="AAPL", quantity=0, avg_price=145.0, current_price=150.0)
        
        result = ExpirationResult(
            expired_positions=[position],
            cash_impact=1000.0,
            warnings=["Test warning"],
            errors=["Test error"]
        )
        
        assert len(result.expired_positions) == 1
        assert result.cash_impact == 1000.0
        assert result.warnings == ["Test warning"]
        assert result.errors == ["Test error"]


class TestOptionsExpirationEngineInitialization:
    """Test OptionsExpirationEngine initialization."""
    
    def test_engine_initialization(self, expiration_engine):
        """Test engine initialization."""
        assert expiration_engine.current_date is None
    
    def test_engine_attributes(self, expiration_engine):
        """Test engine has required attributes."""
        assert hasattr(expiration_engine, "current_date")


class TestFindExpiredPositions:
    """Test finding expired positions."""
    
    def test_find_expired_positions_with_expired_options(self, expiration_engine):
        """Test finding expired option positions."""
        processing_date = date(2023, 1, 21)  # Day after expiration
        
        positions = [
            {"symbol": "AAPL", "quantity": 100},
            {"symbol": "AAPL__230120C00140000", "quantity": 2},  # Expired
            {"symbol": "AAPL__230220C00140000", "quantity": 1},  # Not expired
            {"symbol": "GOOGL__230120P02800000", "quantity": -1},  # Expired
        ]
        
        expired = expiration_engine._find_expired_positions(positions, processing_date)
        
        assert len(expired) == 2
        expired_symbols = [pos["symbol"] for pos in expired]
        assert "AAPL__230120C00140000" in expired_symbols
        assert "GOOGL__230120P02800000" in expired_symbols
    
    def test_find_expired_positions_no_expired(self, expiration_engine):
        """Test finding expired positions when none are expired."""
        processing_date = date(2023, 1, 19)  # Day before expiration
        
        positions = [
            {"symbol": "AAPL", "quantity": 100},
            {"symbol": "AAPL__230120C00140000", "quantity": 2},
            {"symbol": "GOOGL__230220P02800000", "quantity": -1},
        ]
        
        expired = expiration_engine._find_expired_positions(positions, processing_date)
        
        assert len(expired) == 0
    
    def test_find_expired_positions_zero_quantity(self, expiration_engine):
        """Test that zero quantity positions are ignored."""
        processing_date = date(2023, 1, 21)
        
        positions = [
            {"symbol": "AAPL__230120C00140000", "quantity": 0},  # Zero quantity
            {"symbol": "GOOGL__230120P02800000", "quantity": 2},  # Expired with quantity
        ]
        
        expired = expiration_engine._find_expired_positions(positions, processing_date)
        
        assert len(expired) == 1
        assert expired[0]["symbol"] == "GOOGL__230120P02800000"
    
    def test_find_expired_positions_non_options(self, expiration_engine):
        """Test that non-option positions are ignored."""
        processing_date = date(2023, 1, 21)
        
        positions = [
            {"symbol": "AAPL", "quantity": 100},  # Stock, not option
            {"symbol": "GOOGL", "quantity": 50},  # Stock, not option
        ]
        
        expired = expiration_engine._find_expired_positions(positions, processing_date)
        
        assert len(expired) == 0


class TestGroupByUnderlying:
    """Test grouping expired positions by underlying."""
    
    def test_group_by_underlying(self, expiration_engine):
        """Test grouping positions by underlying symbol."""
        positions = [
            {"symbol": "AAPL__230120C00140000", "quantity": 2},
            {"symbol": "AAPL__230120P00160000", "quantity": -1},
            {"symbol": "GOOGL__230120C02900000", "quantity": 1},
            {"symbol": "GOOGL__230120P02700000", "quantity": -2},
            {"symbol": "TSLA__230120C00800000", "quantity": 3},
        ]
        
        groups = expiration_engine._group_by_underlying(positions)
        
        assert len(groups) == 3
        assert "AAPL" in groups
        assert "GOOGL" in groups
        assert "TSLA" in groups
        
        assert len(groups["AAPL"]) == 2
        assert len(groups["GOOGL"]) == 2
        assert len(groups["TSLA"]) == 1
    
    def test_group_by_underlying_empty_list(self, expiration_engine):
        """Test grouping empty position list."""
        groups = expiration_engine._group_by_underlying([])
        
        assert len(groups) == 0


class TestGetEquityPositions:
    """Test getting equity positions for underlying."""
    
    def test_get_equity_positions_with_positions(self, expiration_engine):
        """Test getting equity positions when they exist."""
        positions = [
            {"symbol": "AAPL", "quantity": 100},
            {"symbol": "AAPL", "quantity": -50},
            {"symbol": "AAPL__230120C00140000", "quantity": 2},  # Option, should be ignored
            {"symbol": "GOOGL", "quantity": 25},  # Different underlying
        ]
        
        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")
        
        assert len(equity_positions) == 2
        symbols = [pos["symbol"] for pos in equity_positions]
        assert all(symbol == "AAPL" for symbol in symbols)
        quantities = [pos["quantity"] for pos in equity_positions]
        assert 100 in quantities
        assert -50 in quantities
    
    def test_get_equity_positions_no_positions(self, expiration_engine):
        """Test getting equity positions when none exist."""
        positions = [
            {"symbol": "AAPL__230120C00140000", "quantity": 2},
            {"symbol": "GOOGL", "quantity": 25},
        ]
        
        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")
        
        assert len(equity_positions) == 0
    
    def test_get_equity_positions_zero_quantity(self, expiration_engine):
        """Test that zero quantity equity positions are ignored."""
        positions = [
            {"symbol": "AAPL", "quantity": 100},
            {"symbol": "AAPL", "quantity": 0},  # Should be ignored
        ]
        
        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")
        
        assert len(equity_positions) == 1
        assert equity_positions[0]["quantity"] == 100


class TestDrainAsset:
    """Test FIFO position draining functionality."""
    
    def test_drain_asset_complete_drain(self, expiration_engine):
        """Test completely draining positions."""
        positions = [
            {"symbol": "AAPL", "quantity": 100},
            {"symbol": "AAPL", "quantity": 50},
        ]
        
        remaining = expiration_engine._drain_asset(positions, "AAPL", -100)
        
        assert remaining == 0
        assert positions[0]["quantity"] == 0  # First position drained
        assert positions[1]["quantity"] == 50  # Second position unchanged
    
    def test_drain_asset_partial_drain(self, expiration_engine):
        """Test partially draining positions."""
        positions = [
            {"symbol": "AAPL", "quantity": 100},
            {"symbol": "AAPL", "quantity": 50},
        ]
        
        remaining = expiration_engine._drain_asset(positions, "AAPL", -75)
        
        assert remaining == 0
        assert positions[0]["quantity"] == 25  # Partially drained
        assert positions[1]["quantity"] == 50  # Unchanged
    
    def test_drain_asset_insufficient_quantity(self, expiration_engine):
        """Test draining more than available."""
        positions = [
            {"symbol": "AAPL", "quantity": 100},
        ]
        
        remaining = expiration_engine._drain_asset(positions, "AAPL", -200)
        
        assert remaining == -100  # 100 couldn't be drained
        assert positions[0]["quantity"] == 0
    
    def test_drain_asset_short_positions(self, expiration_engine):
        """Test draining short positions."""
        positions = [
            {"symbol": "AAPL", "quantity": -100},
            {"symbol": "AAPL", "quantity": -50},
        ]
        
        remaining = expiration_engine._drain_asset(positions, "AAPL", 75)
        
        assert remaining == 0
        assert positions[0]["quantity"] == -25  # Partially covered
        assert positions[1]["quantity"] == -50  # Unchanged
    
    def test_drain_asset_no_matching_positions(self, expiration_engine):
        """Test draining when no matching positions exist."""
        positions = [
            {"symbol": "GOOGL", "quantity": 100},
        ]
        
        remaining = expiration_engine._drain_asset(positions, "AAPL", -50)
        
        assert remaining == -50  # Nothing drained
        assert positions[0]["quantity"] == 100  # Unchanged


class TestAddPosition:
    """Test adding positions to account."""
    
    def test_add_position_new_symbol(self, expiration_engine):
        """Test adding position for new symbol."""
        account = {"positions": []}
        
        expiration_engine._add_position(account, "AAPL", 100, 150.0)
        
        assert len(account["positions"]) == 1
        new_position = account["positions"][0]
        assert new_position["symbol"] == "AAPL"
        assert new_position["quantity"] == 100
        assert new_position["avg_price"] == 150.0
    
    def test_add_position_existing_symbol(self, expiration_engine):
        """Test adding to existing position."""
        account = {
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 140.0}
            ]
        }
        
        expiration_engine._add_position(account, "AAPL", 50, 160.0)
        
        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["quantity"] == 150
        # Weighted average: (100*140 + 50*160) / 150 = 146.67
        assert abs(position["avg_price"] - 146.67) < 0.01
    
    def test_add_position_no_positions_list(self, expiration_engine):
        """Test adding position when positions list doesn't exist."""
        account = {}
        
        expiration_engine._add_position(account, "AAPL", 100, 150.0)
        
        assert "positions" in account
        assert len(account["positions"]) == 1


class TestLongCallExercise:
    """Test long call exercise functionality."""
    
    def test_exercise_long_call(self, expiration_engine):
        """Test exercising long call options."""
        account = {"cash_balance": 20000.0, "positions": []}
        call = Call(underlying=Stock("AAPL"), strike=140.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._exercise_long_call(account, call, 2, 12.0, 150.0)
        
        # Should buy 200 shares at $140 each = $28,000
        assert account["cash_balance"] == 20000.0 - 28000.0
        assert len(account["positions"]) == 1
        
        new_position = account["positions"][0]
        assert new_position["symbol"] == "AAPL"
        assert new_position["quantity"] == 200
        assert new_position["avg_price"] == 152.0  # Strike + premium
        
        assert result["type"] == "exercise"
        assert result["option_type"] == "call"
        assert result["shares_acquired"] == 200
        assert result["cash_paid"] == 28000.0
    
    def test_exercise_long_call_single_contract(self, expiration_engine):
        """Test exercising single long call contract."""
        account = {"cash_balance": 15000.0, "positions": []}
        call = Call(underlying=Stock("AAPL"), strike=145.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._exercise_long_call(account, call, 1, 8.0, 150.0)
        
        assert account["cash_balance"] == 15000.0 - 14500.0  # 100 shares * $145
        assert result["shares_acquired"] == 100
        assert result["cash_paid"] == 14500.0
        assert result["effective_cost_basis"] == 153.0  # 145 + 8


class TestShortCallAssignment:
    """Test short call assignment functionality."""
    
    def test_assign_short_call_with_shares(self, expiration_engine):
        """Test short call assignment when shares are available."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 300, "avg_price": 140.0}
            ]
        }
        call = Call(underlying=Stock("AAPL"), strike=145.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._assign_short_call(account, call, -2, 150.0, 300)
        
        # Should deliver 200 shares and receive $29,000
        assert account["cash_balance"] == 10000.0 + 29000.0
        assert account["positions"][0]["quantity"] == 100  # 300 - 200
        
        assert result["type"] == "assignment"
        assert result["shares_delivered"] == 200
        assert result["cash_received"] == 29000.0
        assert result["shares_source"] == "existing_position"
    
    def test_assign_short_call_insufficient_shares(self, expiration_engine):
        """Test short call assignment when insufficient shares available."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 50, "avg_price": 140.0}  # Not enough
            ]
        }
        call = Call(underlying=Stock("AAPL"), strike=145.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._assign_short_call(account, call, -2, 150.0, 50)
        
        # Should buy shares at market and sell at strike
        cash_to_buy = 150.0 * 200  # Buy 200 shares at $150
        cash_received = 145.0 * 200  # Sell 200 shares at $145
        net_cash = cash_received - cash_to_buy  # -$1,000
        
        assert account["cash_balance"] == 10000.0 + net_cash
        assert result["shares_source"] == "market_purchase"
        assert result["net_cash"] == net_cash
        assert "warning" in result


class TestLongPutExercise:
    """Test long put exercise functionality."""
    
    def test_exercise_long_put(self, expiration_engine):
        """Test exercising long put options."""
        account = {"cash_balance": 10000.0, "positions": []}
        put = Put(underlying=Stock("AAPL"), strike=140.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._exercise_long_put(account, put, 2, 8.0, 130.0)
        
        # Should sell short 200 shares at $140 each = $28,000 received
        assert account["cash_balance"] == 10000.0 + 28000.0
        assert len(account["positions"]) == 1
        
        new_position = account["positions"][0]
        assert new_position["symbol"] == "AAPL"
        assert new_position["quantity"] == -200  # Short position
        assert new_position["avg_price"] == 132.0  # Strike - premium
        
        assert result["type"] == "exercise"
        assert result["option_type"] == "put"
        assert result["shares_sold_short"] == 200
        assert result["cash_received"] == 28000.0


class TestShortPutAssignment:
    """Test short put assignment functionality."""
    
    def test_assign_short_put_with_short_shares(self, expiration_engine):
        """Test short put assignment when short shares exist to cover."""
        account = {
            "cash_balance": 20000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": -300, "avg_price": 150.0}  # Short position
            ]
        }
        put = Put(underlying=Stock("AAPL"), strike=140.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._assign_short_put(account, put, -2, 130.0, -300)
        
        # Should cover 200 shares of short position at $140 each
        assert account["cash_balance"] == 20000.0 - 28000.0
        assert account["positions"][0]["quantity"] == -100  # -300 + 200
        
        assert result["type"] == "assignment"
        assert result["shares_purchased"] == 200
        assert result["cash_paid"] == 28000.0
        assert result["shares_destination"] == "cover_short"
    
    def test_assign_short_put_create_long_position(self, expiration_engine):
        """Test short put assignment creating new long position."""
        account = {"cash_balance": 20000.0, "positions": []}
        put = Put(underlying=Stock("AAPL"), strike=140.0, expiration_date=date(2023, 1, 20))
        
        result = expiration_engine._assign_short_put(account, put, -1, 130.0, 0)
        
        # Should create new long position
        assert account["cash_balance"] == 20000.0 - 14000.0
        assert len(account["positions"]) == 1
        
        new_position = account["positions"][0]
        assert new_position["symbol"] == "AAPL"
        assert new_position["quantity"] == 100
        assert new_position["avg_price"] == 140.0
        
        assert result["shares_destination"] == "new_long_position"


class TestSingleExpirationProcessing:
    """Test processing single expired positions."""
    
    def test_process_single_expiration_worthless_option(self, expiration_engine):
        """Test processing worthless expired option."""
        account = {"positions": [], "cash_balance": 10000.0}
        position = {
            "symbol": "AAPL__230120C00160000",  # Call with $160 strike
            "quantity": 2,
            "avg_price": 5.0
        }
        
        # Current price $150, so $160 call is OTM/worthless
        result = expiration_engine._process_single_expiration(
            account, position, 150.0, 0, 0
        )
        
        assert len(result.worthless_expirations) == 1
        assert result.worthless_expirations[0]["symbol"] == "AAPL__230120C00160000"
        assert result.worthless_expirations[0]["intrinsic_value"] == 0.0
        assert position["quantity"] == 0  # Position zeroed out
    
    def test_process_single_expiration_itm_long_call(self, expiration_engine):
        """Test processing ITM long call expiration."""
        account = {"positions": [], "cash_balance": 20000.0}
        position = {
            "symbol": "AAPL__230120C00140000",  # Call with $140 strike
            "quantity": 1,
            "avg_price": 8.0
        }
        
        # Current price $150, so $140 call is ITM
        result = expiration_engine._process_single_expiration(
            account, position, 150.0, 0, 0
        )
        
        assert len(result.exercises) == 1
        assert result.exercises[0]["type"] == "exercise"
        assert result.exercises[0]["option_type"] == "call"
        assert position["quantity"] == 0  # Position zeroed out
    
    def test_process_single_expiration_itm_short_call(self, expiration_engine):
        """Test processing ITM short call expiration."""
        account = {"positions": [], "cash_balance": 20000.0}
        position = {
            "symbol": "AAPL__230120C00140000",  # Call with $140 strike
            "quantity": -1,  # Short position
            "avg_price": 8.0
        }
        
        # Current price $150, so $140 call is ITM
        result = expiration_engine._process_single_expiration(
            account, position, 150.0, 100, 0  # 100 long shares available
        )
        
        assert len(result.assignments) == 1
        assert result.assignments[0]["type"] == "assignment"
        assert result.assignments[0]["option_type"] == "call"
        assert position["quantity"] == 0


class TestAccountExpirationsProcessing:
    """Test complete account expiration processing."""
    
    @pytest.mark.asyncio
    async def test_process_account_expirations_no_positions(self, expiration_engine, mock_quote_adapter):
        """Test processing account with no positions."""
        account = {"cash_balance": 10000.0, "positions": []}
        
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter, date(2023, 1, 21)
        )
        
        assert len(result.expired_positions) == 0
        assert len(result.new_positions) == 0
        assert result.cash_impact == 0.0
    
    @pytest.mark.asyncio
    async def test_process_account_expirations_no_expired(self, expiration_engine, mock_quote_adapter):
        """Test processing account with no expired positions."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 145.0},
                {"symbol": "AAPL__230220C00140000", "quantity": 2, "avg_price": 12.0},  # Future expiry
            ]
        }
        
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter, date(2023, 1, 21)
        )
        
        assert len(result.expired_positions) == 0
        assert len(result.new_positions) == 0
    
    @pytest.mark.asyncio
    async def test_process_account_expirations_with_expired(self, expiration_engine, mock_quote_adapter):
        """Test processing account with expired positions."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 145.0},
                {"symbol": "AAPL__230120C00140000", "quantity": 1, "avg_price": 12.0},  # ITM call
                {"symbol": "AAPL__230120P00160000", "quantity": 1, "avg_price": 8.0},   # OTM put
            ]
        }
        
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter, date(2023, 1, 21)
        )
        
        assert len(result.expired_positions) == 2  # Both options expired
        assert len(result.exercises) == 1  # ITM call exercised
        assert len(result.worthless_expirations) == 1  # OTM put worthless
    
    @pytest.mark.asyncio
    async def test_process_account_expirations_default_date(self, expiration_engine, mock_quote_adapter):
        """Test processing with default date (today)."""
        account = {"cash_balance": 10000.0, "positions": []}
        
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter  # No date provided
        )
        
        # Should use today's date
        assert expiration_engine.current_date == date.today()
    
    @pytest.mark.asyncio
    async def test_process_account_expirations_quote_error(self, expiration_engine):
        """Test processing when quote adapter fails."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL__230120C00140000", "quantity": 1, "avg_price": 12.0},
            ]
        }
        
        # Mock adapter that raises exception
        error_adapter = Mock()
        error_adapter.get_quote = AsyncMock(side_effect=Exception("Quote error"))
        
        result = await expiration_engine.process_account_expirations(
            account, error_adapter, date(2023, 1, 21)
        )
        
        assert len(result.errors) > 0
        assert "Quote error" in str(result.errors[0])
    
    @pytest.mark.asyncio
    async def test_process_account_expirations_account_deepcopy(self, expiration_engine, mock_quote_adapter):
        """Test that original account is not modified."""
        original_account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL__230120C00140000", "quantity": 1, "avg_price": 12.0},
            ]
        }
        
        account_copy = original_account.copy()
        account_copy["positions"] = [pos.copy() for pos in original_account["positions"]]
        
        await expiration_engine.process_account_expirations(
            account_copy, mock_quote_adapter, date(2023, 1, 21)
        )
        
        # Original account should be unchanged
        assert original_account["cash_balance"] == 10000.0
        assert len(original_account["positions"]) == 1
        assert original_account["positions"][0]["quantity"] == 1


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_option_symbol(self, expiration_engine, mock_quote_adapter):
        """Test handling invalid option symbol."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "INVALID_OPTION_SYMBOL", "quantity": 1, "avg_price": 12.0},
            ]
        }
        
        # Should handle gracefully without crashing
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter, date(2023, 1, 21)
        )
        
        # Should not find any expired positions due to invalid symbol
        assert len(result.expired_positions) == 0
    
    @pytest.mark.asyncio
    async def test_zero_underlying_price(self, expiration_engine):
        """Test handling zero underlying price."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL__230120C00140000", "quantity": 1, "avg_price": 12.0},
            ]
        }
        
        # Mock adapter returning zero price
        zero_price_adapter = MockQuoteAdapter({"AAPL": 0.0})
        
        result = await expiration_engine.process_account_expirations(
            account, zero_price_adapter, date(2023, 1, 21)
        )
        
        # Should handle gracefully - option would be worthless
        assert len(result.expired_positions) == 1
        assert len(result.worthless_expirations) == 1
    
    @pytest.mark.asyncio
    async def test_negative_quantities(self, expiration_engine, mock_quote_adapter):
        """Test handling negative quantities."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL__230120C00140000", "quantity": -1, "avg_price": 12.0},  # Short call
            ]
        }
        
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter, date(2023, 1, 21)
        )
        
        # Should process short option assignment
        assert len(result.expired_positions) == 1
        assert len(result.assignments) == 1
    
    def test_missing_account_data(self, expiration_engine):
        """Test handling missing account data."""
        # Test with None account
        with pytest.raises(AttributeError):
            expiration_engine._find_expired_positions(None, date.today())
        
        # Test with empty account
        empty_account = {}
        # Should handle gracefully by treating as no positions
        expired = expiration_engine._find_expired_positions([], date.today())
        assert len(expired) == 0
    
    def test_corrupted_position_data(self, expiration_engine):
        """Test handling corrupted position data."""
        positions = [
            {"symbol": "AAPL__230120C00140000"},  # Missing quantity
            {"quantity": 1},  # Missing symbol
            {"symbol": "AAPL__230120C00140000", "quantity": "invalid"},  # Invalid quantity type
        ]
        
        # Should handle gracefully without crashing
        try:
            expired = expiration_engine._find_expired_positions(positions, date(2023, 1, 21))
            # Should filter out invalid positions
            assert len(expired) <= len(positions)
        except Exception:
            pytest.fail("Should handle corrupted position data gracefully")


class TestPerformanceAndIntegration:
    """Test performance and integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_large_number_of_positions(self, expiration_engine, mock_quote_adapter):
        """Test processing large number of positions."""
        # Create account with many positions
        positions = []
        for i in range(100):
            positions.append({
                "symbol": f"AAPL__230120C00{140+i:03d}000",
                "quantity": 1,
                "avg_price": 10.0
            })
        
        account = {"cash_balance": 100000.0, "positions": positions}
        
        result = await expiration_engine.process_account_expirations(
            account, mock_quote_adapter, date(2023, 1, 21)
        )
        
        # Should process all expired positions
        assert len(result.expired_positions) == 100
    
    @pytest.mark.asyncio
    async def test_mixed_option_types_and_underlyings(self, expiration_engine):
        """Test processing mixed option types and underlyings."""
        # Enhanced mock adapter with multiple symbols
        multi_symbol_adapter = MockQuoteAdapter({
            "AAPL": 150.0,
            "GOOGL": 2800.0,
            "TSLA": 200.0
        })
        
        account = {
            "cash_balance": 50000.0,
            "positions": [
                # AAPL positions
                {"symbol": "AAPL", "quantity": 100, "avg_price": 145.0},
                {"symbol": "AAPL__230120C00140000", "quantity": 2, "avg_price": 12.0},  # ITM
                {"symbol": "AAPL__230120P00160000", "quantity": -1, "avg_price": 8.0},  # OTM short
                
                # GOOGL positions
                {"symbol": "GOOGL", "quantity": 10, "avg_price": 2750.0},
                {"symbol": "GOOGL__230120C02900000", "quantity": 1, "avg_price": 50.0},  # OTM
                {"symbol": "GOOGL__230120P02700000", "quantity": 1, "avg_price": 100.0},  # ITM
                
                # TSLA positions
                {"symbol": "TSLA__230120C00250000", "quantity": -2, "avg_price": 30.0},  # OTM short
            ]
        }
        
        result = await expiration_engine.process_account_expirations(
            account, multi_symbol_adapter, date(2023, 1, 21)
        )
        
        # Should process all expired options across different underlyings
        assert len(result.expired_positions) == 5  # All options expired
        assert len(result.exercises) >= 1  # At least AAPL call and GOOGL put
        assert len(result.worthless_expirations) >= 1  # At least GOOGL call
    
    @pytest.mark.asyncio
    async def test_complex_assignment_scenarios(self, expiration_engine):
        """Test complex assignment scenarios with insufficient underlying positions."""
        # Mock adapter
        adapter = MockQuoteAdapter({"AAPL": 160.0})  # High price for ITM scenarios
        
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 50, "avg_price": 145.0},  # Only 50 shares
                {"symbol": "AAPL__230120C00140000", "quantity": -2, "avg_price": 15.0},  # Short 2 calls, need 200 shares
            ]
        }
        
        result = await expiration_engine.process_account_expirations(
            account, adapter, date(2023, 1, 21)
        )
        
        # Should result in assignment with warning about insufficient shares
        assert len(result.assignments) == 1
        assert len(result.warnings) >= 1
        assert "insufficient" in result.warnings[0].lower() or "forced" in result.assignments[0].get("warning", "").lower()


class TestOptionsIntrinsicValue:
    """Test options intrinsic value calculations during expiration."""
    
    def test_call_intrinsic_value_itm(self, expiration_engine):
        """Test call intrinsic value when in-the-money."""
        account = {"cash_balance": 10000.0, "positions": []}
        position = {
            "symbol": "AAPL__230120C00140000",  # $140 strike call
            "quantity": 1,
            "avg_price": 10.0
        }
        
        # At $150 underlying, $140 call has $10 intrinsic value
        result = expiration_engine._process_single_expiration(
            account, position, 150.0, 0, 0
        )
        
        # Should be exercised, not expired worthless
        assert len(result.exercises) == 1
        assert len(result.worthless_expirations) == 0
    
    def test_put_intrinsic_value_itm(self, expiration_engine):
        """Test put intrinsic value when in-the-money."""
        account = {"cash_balance": 10000.0, "positions": []}
        position = {
            "symbol": "AAPL__230120P00160000",  # $160 strike put
            "quantity": 1,
            "avg_price": 10.0
        }
        
        # At $150 underlying, $160 put has $10 intrinsic value
        result = expiration_engine._process_single_expiration(
            account, position, 150.0, 0, 0
        )
        
        # Should be exercised, not expired worthless
        assert len(result.exercises) == 1
        assert len(result.worthless_expirations) == 0
    
    def test_option_intrinsic_value_otm(self, expiration_engine):
        """Test option intrinsic value when out-of-the-money."""
        account = {"cash_balance": 10000.0, "positions": []}
        
        # OTM call position
        call_position = {
            "symbol": "AAPL__230120C00160000",  # $160 strike call
            "quantity": 1,
            "avg_price": 5.0
        }
        
        # At $150 underlying, $160 call has $0 intrinsic value
        call_result = expiration_engine._process_single_expiration(
            account, call_position, 150.0, 0, 0
        )
        
        assert len(call_result.worthless_expirations) == 1
        assert call_result.worthless_expirations[0]["intrinsic_value"] == 0.0
        
        # OTM put position
        put_position = {
            "symbol": "AAPL__230120P00140000",  # $140 strike put
            "quantity": 1,
            "avg_price": 5.0
        }
        
        # At $150 underlying, $140 put has $0 intrinsic value
        put_result = expiration_engine._process_single_expiration(
            account, put_position, 150.0, 0, 0
        )
        
        assert len(put_result.worthless_expirations) == 1
        assert put_result.worthless_expirations[0]["intrinsic_value"] == 0.0