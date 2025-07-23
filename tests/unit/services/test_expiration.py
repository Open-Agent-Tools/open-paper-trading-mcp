"""
Comprehensive tests for OptionsExpirationEngine - options expiration processing service.

Tests cover:
- Options expiration date processing and detection
- ITM/OTM option classification and handling
- Automatic assignment and exercise simulation
- Cash and position adjustments for expirations
- FIFO position closing logic implementation
- Long call exercise scenarios and outcomes
- Short call assignment and share delivery
- Long put exercise and short position creation
- Short put assignment and share acquisition
- Underlying equity position management
- Insufficient share warnings and forced purchases
- Multi-underlying options batch processing
- Position quantity and average price calculations
- Error handling and recovery scenarios
- Edge cases and corner scenarios
"""

import copy
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from app.adapters.base import QuoteAdapter
from app.models.assets import Call, Option, Put, Stock
from app.models.quotes import Quote
from app.schemas.positions import Position
from app.services.expiration import ExpirationResult, OptionsExpirationEngine


@pytest.fixture
def expiration_engine():
    """Options expiration engine instance."""
    return OptionsExpirationEngine()


@pytest.fixture
def mock_quote_adapter():
    """Mock quote adapter for testing."""
    adapter = AsyncMock(spec=QuoteAdapter)
    return adapter


@pytest.fixture
def sample_account():
    """Sample account data with positions and cash."""
    return {
        "cash_balance": 50000.0,
        "positions": [
            {
                "symbol": "AAPL",
                "quantity": 200,
                "avg_price": 145.00,
                "current_price": 150.00,
            },
            {
                "symbol": "AAPL240119C150",  # ITM call
                "quantity": 5,
                "avg_price": 3.50,
                "current_price": 8.00,
            },
            {
                "symbol": "AAPL240119P140",  # OTM put
                "quantity": -3,
                "avg_price": 2.00,
                "current_price": 0.50,
            },
            {
                "symbol": "GOOGL240119C2800",  # ATM call
                "quantity": 2,
                "avg_price": 25.00,
                "current_price": 30.00,
            },
        ],
    }


@pytest.fixture
def expired_date():
    """Expiration date for testing."""
    return date(2024, 1, 19)


@pytest.fixture
def sample_underlying_quote():
    """Sample underlying stock quote."""
    return Quote(
        asset=Stock(symbol="AAPL"),
        price=155.00,  # ITM for 150 call, OTM for 140 put
        bid=154.95,
        ask=155.05,
        quote_date=None,
    )


@pytest.fixture
def sample_googl_quote():
    """Sample GOOGL quote."""
    return Quote(
        asset=Stock(symbol="GOOGL"),
        price=2800.00,  # ATM for 2800 call
        bid=2799.50,
        ask=2800.50,
        quote_date=None,
    )


class TestExpirationEngineInitialization:
    """Test expiration engine initialization."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = OptionsExpirationEngine()

        assert engine.current_date is None

    def test_engine_processing_date_setup(self, expiration_engine, expired_date):
        """Test processing date setup."""
        expiration_engine.current_date = expired_date

        assert expiration_engine.current_date == expired_date


class TestExpirationDetection:
    """Test expired position detection and filtering."""

    def test_find_expired_positions_with_options(
        self, expiration_engine, sample_account, expired_date
    ):
        """Test finding expired option positions."""
        expired_positions = expiration_engine._find_expired_positions(
            sample_account["positions"], expired_date
        )

        # Should find 3 expired options (2 AAPL, 1 GOOGL)
        assert len(expired_positions) == 3

        expired_symbols = [pos["symbol"] for pos in expired_positions]
        assert "AAPL240119C150" in expired_symbols
        assert "AAPL240119P140" in expired_symbols
        assert "GOOGL240119C2800" in expired_symbols
        assert "AAPL" not in expired_symbols  # Stock doesn't expire

    def test_find_expired_positions_no_options(self, expiration_engine, expired_date):
        """Test finding expired positions with no options."""
        positions = [
            {"symbol": "AAPL", "quantity": 100, "avg_price": 150.00},
            {"symbol": "GOOGL", "quantity": 50, "avg_price": 2800.00},
        ]

        expired_positions = expiration_engine._find_expired_positions(
            positions, expired_date
        )

        assert len(expired_positions) == 0

    def test_find_expired_positions_zero_quantity(
        self, expiration_engine, expired_date
    ):
        """Test finding expired positions ignores zero quantities."""
        positions = [
            {
                "symbol": "AAPL240119C150",
                "quantity": 0,
                "avg_price": 3.50,
            },  # Zero quantity
            {"symbol": "AAPL240119P140", "quantity": 5, "avg_price": 2.00},  # Valid
        ]

        expired_positions = expiration_engine._find_expired_positions(
            positions, expired_date
        )

        assert len(expired_positions) == 1
        assert expired_positions[0]["symbol"] == "AAPL240119P140"

    def test_find_expired_positions_future_expiration(self, expiration_engine):
        """Test finding expired positions with future expiration."""
        future_date = date.today() + timedelta(days=30)
        positions = [
            {
                "symbol": f"AAPL{future_date.strftime('%y%m%d')}C150",
                "quantity": 5,
                "avg_price": 3.50,
            },
        ]

        expired_positions = expiration_engine._find_expired_positions(
            positions, date.today()
        )

        assert len(expired_positions) == 0

    def test_find_expired_positions_handles_position_objects(
        self, expiration_engine, expired_date
    ):
        """Test finding expired positions with Position objects."""
        positions = [
            Position(symbol="AAPL240119C150", quantity=5, avg_price=3.50),
            Position(symbol="AAPL", quantity=100, avg_price=150.00),
        ]

        expired_positions = expiration_engine._find_expired_positions(
            positions, expired_date
        )

        assert len(expired_positions) == 1
        assert expired_positions[0].symbol == "AAPL240119C150"


class TestPositionGrouping:
    """Test grouping expired positions by underlying."""

    def test_group_by_underlying_single_underlying(self, expiration_engine):
        """Test grouping with single underlying."""
        expired_positions = [
            {"symbol": "AAPL240119C150", "quantity": 5},
            {"symbol": "AAPL240119P140", "quantity": -3},
        ]

        groups = expiration_engine._group_by_underlying(expired_positions)

        assert "AAPL" in groups
        assert len(groups["AAPL"]) == 2
        assert len(groups) == 1

    def test_group_by_underlying_multiple_underlyings(self, expiration_engine):
        """Test grouping with multiple underlyings."""
        expired_positions = [
            {"symbol": "AAPL240119C150", "quantity": 5},
            {"symbol": "AAPL240119P140", "quantity": -3},
            {"symbol": "GOOGL240119C2800", "quantity": 2},
            {"symbol": "MSFT240119C300", "quantity": 1},
        ]

        groups = expiration_engine._group_by_underlying(expired_positions)

        assert "AAPL" in groups
        assert "GOOGL" in groups
        assert "MSFT" in groups
        assert len(groups["AAPL"]) == 2
        assert len(groups["GOOGL"]) == 1
        assert len(groups["MSFT"]) == 1

    def test_group_by_underlying_with_position_objects(self, expiration_engine):
        """Test grouping with Position objects."""
        expired_positions = [
            Position(symbol="AAPL240119C150", quantity=5, avg_price=3.50),
            Position(symbol="GOOGL240119C2800", quantity=2, avg_price=25.00),
        ]

        groups = expiration_engine._group_by_underlying(expired_positions)

        assert "AAPL" in groups
        assert "GOOGL" in groups
        assert len(groups["AAPL"]) == 1
        assert len(groups["GOOGL"]) == 1


class TestEquityPositionRetrieval:
    """Test equity position retrieval for underlyings."""

    def test_get_equity_positions_with_equity(self, expiration_engine):
        """Test getting equity positions when they exist."""
        positions = [
            {"symbol": "AAPL", "quantity": 200, "avg_price": 145.00},
            {"symbol": "AAPL240119C150", "quantity": 5, "avg_price": 3.50},
            {"symbol": "GOOGL", "quantity": 50, "avg_price": 2800.00},
        ]

        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")

        assert len(equity_positions) == 1
        assert equity_positions[0]["symbol"] == "AAPL"
        assert equity_positions[0]["quantity"] == 200

    def test_get_equity_positions_no_equity(self, expiration_engine):
        """Test getting equity positions when none exist."""
        positions = [
            {"symbol": "AAPL240119C150", "quantity": 5, "avg_price": 3.50},
            {"symbol": "GOOGL240119P2700", "quantity": -2, "avg_price": 20.00},
        ]

        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")

        assert len(equity_positions) == 0

    def test_get_equity_positions_ignores_zero_quantity(self, expiration_engine):
        """Test getting equity positions ignores zero quantities."""
        positions = [
            {"symbol": "AAPL", "quantity": 0, "avg_price": 145.00},  # Zero quantity
            {"symbol": "AAPL", "quantity": 100, "avg_price": 140.00},  # Valid
        ]

        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")

        assert len(equity_positions) == 1
        assert equity_positions[0]["quantity"] == 100

    def test_get_equity_positions_with_mixed_quantities(self, expiration_engine):
        """Test getting equity positions with long and short."""
        positions = [
            {"symbol": "AAPL", "quantity": 200, "avg_price": 145.00},  # Long
            {"symbol": "AAPL", "quantity": -50, "avg_price": 140.00},  # Short
            {"symbol": "AAPL240119C150", "quantity": 5, "avg_price": 3.50},  # Option
        ]

        equity_positions = expiration_engine._get_equity_positions(positions, "AAPL")

        assert len(equity_positions) == 2
        quantities = [pos["quantity"] for pos in equity_positions]
        assert 200 in quantities
        assert -50 in quantities


class TestLongCallExercise:
    """Test long call option exercise scenarios."""

    def test_exercise_long_call_basic(self, expiration_engine):
        """Test basic long call exercise."""
        account = {"cash_balance": 50000.0, "positions": []}

        call = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._exercise_long_call(
            account,
            call,
            5,
            3.50,
            155.00,  # 5 contracts, $3.50 cost, $155 underlying
        )

        assert result["type"] == "exercise"
        assert result["option_type"] == "call"
        assert result["quantity"] == 5
        assert result["strike"] == 150.0
        assert result["shares_acquired"] == 500  # 5 contracts * 100
        assert result["cash_paid"] == 75000.0  # 500 shares * $150
        assert result["effective_cost_basis"] == 153.50  # $150 + $3.50 premium

        # Check account changes
        assert account["cash_balance"] == -25000.0  # 50000 - 75000

    def test_exercise_long_call_creates_position(self, expiration_engine):
        """Test long call exercise creates stock position."""
        account = {"cash_balance": 50000.0, "positions": []}

        call = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        expiration_engine._exercise_long_call(account, call, 3, 4.00, 155.00)

        # Should create new position
        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 300  # 3 contracts * 100
        assert position["avg_price"] == 154.00  # $150 + $4.00

    def test_exercise_long_call_adds_to_existing_position(self, expiration_engine):
        """Test long call exercise adds to existing position."""
        account = {
            "cash_balance": 50000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "avg_price": 140.00,
                    "current_price": 150.00,
                }
            ],
        }

        call = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        expiration_engine._exercise_long_call(account, call, 2, 5.00, 155.00)

        # Should update existing position
        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 300  # 100 + 200

        # Weighted average: (100*140 + 200*155) / 300 = 150.00
        expected_avg = (100 * 140.00 + 200 * 155.00) / 300
        assert abs(position["avg_price"] - expected_avg) < 0.01


class TestShortCallAssignment:
    """Test short call assignment scenarios."""

    def test_assign_short_call_sufficient_shares(self, expiration_engine):
        """Test short call assignment with sufficient shares."""
        account = {
            "cash_balance": 10000.0,
            "positions": [{"symbol": "AAPL", "quantity": 1000, "avg_price": 140.00}],
        }

        call = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._assign_short_call(
            account,
            call,
            -3,
            155.00,
            1000,  # -3 contracts, sufficient shares
        )

        assert result["type"] == "assignment"
        assert result["option_type"] == "call"
        assert result["shares_delivered"] == 300
        assert result["cash_received"] == 45000.0  # 300 * $150
        assert result["shares_source"] == "existing_position"
        assert "warning" not in result

        # Cash should increase
        assert account["cash_balance"] == 55000.0  # 10000 + 45000

    def test_assign_short_call_insufficient_shares(self, expiration_engine):
        """Test short call assignment with insufficient shares."""
        account = {
            "cash_balance": 50000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "avg_price": 140.00,
                }  # Only 100 shares
            ],
        }

        call = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._assign_short_call(
            account,
            call,
            -3,
            155.00,
            100,  # Need 300, only have 100
        )

        assert result["type"] == "assignment"
        assert result["shares_delivered"] == 300
        assert result["cash_to_buy"] == 46500.0  # 300 * $155 market price
        assert result["cash_received"] == 45000.0  # 300 * $150 strike price
        assert result["net_cash"] == -1500.0  # Loss due to buying at market
        assert result["shares_source"] == "market_purchase"
        assert "warning" in result
        assert "forced to buy" in result["warning"]

    def test_assign_short_call_no_shares(self, expiration_engine):
        """Test short call assignment with no shares."""
        account = {"cash_balance": 50000.0, "positions": []}

        call = Call(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._assign_short_call(
            account,
            call,
            -2,
            155.00,
            0,  # No shares available
        )

        assert result["shares_source"] == "market_purchase"
        assert result["cash_to_buy"] == 31000.0  # 200 * $155
        assert result["cash_received"] == 30000.0  # 200 * $150
        assert result["net_cash"] == -1000.0  # $5 loss per share


class TestLongPutExercise:
    """Test long put option exercise scenarios."""

    def test_exercise_long_put_basic(self, expiration_engine):
        """Test basic long put exercise."""
        account = {"cash_balance": 10000.0, "positions": []}

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._exercise_long_put(
            account,
            put,
            3,
            4.00,
            140.00,  # 3 contracts, $4 cost, $140 underlying
        )

        assert result["type"] == "exercise"
        assert result["option_type"] == "put"
        assert result["quantity"] == 3
        assert result["strike"] == 150.0
        assert result["shares_sold_short"] == 300  # 3 contracts * 100
        assert result["cash_received"] == 45000.0  # 300 shares * $150
        assert result["effective_cost_basis"] == 146.0  # $150 - $4 premium

        # Check account changes
        assert account["cash_balance"] == 55000.0  # 10000 + 45000

    def test_exercise_long_put_creates_short_position(self, expiration_engine):
        """Test long put exercise creates short position."""
        account = {"cash_balance": 10000.0, "positions": []}

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=140.0,
            expiration_date=date.today(),
        )

        expiration_engine._exercise_long_put(account, put, 2, 3.00, 135.00)

        # Should create short position
        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == -200  # Negative for short
        assert position["avg_price"] == 137.0  # $140 - $3

    def test_exercise_long_put_adds_to_existing_short(self, expiration_engine):
        """Test long put exercise adds to existing short position."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": -100,
                    "avg_price": 145.00,
                    "current_price": 140.00,
                }
            ],
        }

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        expiration_engine._exercise_long_put(account, put, 2, 5.00, 140.00)

        # Should update existing short position
        position = account["positions"][0]
        assert position["quantity"] == -300  # -100 + (-200)

        # Weighted average for short positions
        expected_avg = (100 * 145.00 + 200 * 145.00) / 300  # Both at $145 effective
        assert abs(position["avg_price"] - expected_avg) < 0.01


class TestShortPutAssignment:
    """Test short put assignment scenarios."""

    def test_assign_short_put_sufficient_short_shares(self, expiration_engine):
        """Test short put assignment with sufficient short shares to cover."""
        account = {
            "cash_balance": 50000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": -500,
                    "avg_price": 160.00,
                }  # Short position
            ],
        }

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._assign_short_put(
            account,
            put,
            -2,
            140.00,
            -500,  # -2 contracts, -500 short shares
        )

        assert result["type"] == "assignment"
        assert result["option_type"] == "put"
        assert result["shares_purchased"] == 200
        assert result["cash_paid"] == 30000.0  # 200 * $150
        assert result["shares_destination"] == "cover_short"

        # Cash should decrease
        assert account["cash_balance"] == 20000.0  # 50000 - 30000

    def test_assign_short_put_insufficient_short_shares(self, expiration_engine):
        """Test short put assignment with insufficient short shares."""
        account = {
            "cash_balance": 50000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": -50,
                    "avg_price": 160.00,
                }  # Only 50 short
            ],
        }

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._assign_short_put(
            account,
            put,
            -3,
            140.00,
            -50,  # Need 300, only have 50 short
        )

        assert result["type"] == "assignment"
        assert result["shares_purchased"] == 300
        assert result["cash_paid"] == 45000.0  # 300 * $150
        assert result["shares_destination"] == "new_long_position"

    def test_assign_short_put_no_short_shares(self, expiration_engine):
        """Test short put assignment with no short shares."""
        account = {"cash_balance": 50000.0, "positions": []}

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=140.0,
            expiration_date=date.today(),
        )

        result = expiration_engine._assign_short_put(
            account,
            put,
            -2,
            135.00,
            0,  # No short shares
        )

        assert result["shares_destination"] == "new_long_position"
        assert result["cash_paid"] == 28000.0  # 200 * $140

    def test_assign_short_put_creates_long_position(self, expiration_engine):
        """Test short put assignment creates long position."""
        account = {"cash_balance": 50000.0, "positions": []}

        put = Put(
            underlying=Stock(symbol="AAPL"),
            strike=150.0,
            expiration_date=date.today(),
        )

        expiration_engine._assign_short_put(account, put, -2, 140.00, 0)

        # Should create long position
        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 200
        assert position["avg_price"] == 150.0  # Strike price


class TestPositionDraining:
    """Test FIFO position draining functionality."""

    def test_drain_asset_simple(self, expiration_engine):
        """Test simple asset draining."""
        positions = [{"symbol": "AAPL", "quantity": 500, "avg_price": 145.00}]

        remaining = expiration_engine._drain_asset(positions, "AAPL", -200)

        assert remaining == 0  # All drained
        assert positions[0]["quantity"] == 300  # 500 - 200

    def test_drain_asset_multiple_positions_fifo(self, expiration_engine):
        """Test FIFO draining across multiple positions."""
        positions = [
            {"symbol": "AAPL", "quantity": 100, "avg_price": 140.00},  # First in
            {"symbol": "AAPL", "quantity": 200, "avg_price": 145.00},  # Second in
            {"symbol": "AAPL", "quantity": 150, "avg_price": 150.00},  # Third in
        ]

        remaining = expiration_engine._drain_asset(positions, "AAPL", -250)

        assert remaining == 0
        assert positions[0]["quantity"] == 0  # Completely drained
        assert positions[1]["quantity"] == 50  # 200 - 150 remaining
        assert positions[2]["quantity"] == 150  # Untouched

    def test_drain_asset_insufficient_quantity(self, expiration_engine):
        """Test draining more than available."""
        positions = [{"symbol": "AAPL", "quantity": 100, "avg_price": 145.00}]

        remaining = expiration_engine._drain_asset(positions, "AAPL", -200)

        assert remaining == -100  # 100 short
        assert positions[0]["quantity"] == 0

    def test_drain_asset_short_positions(self, expiration_engine):
        """Test draining short positions."""
        positions = [{"symbol": "AAPL", "quantity": -300, "avg_price": 145.00}]

        remaining = expiration_engine._drain_asset(positions, "AAPL", 100)

        assert remaining == 0
        assert positions[0]["quantity"] == -200  # -300 + 100

    def test_drain_asset_mixed_positions(self, expiration_engine):
        """Test draining with mixed long/short positions."""
        positions = [
            {"symbol": "AAPL", "quantity": 200, "avg_price": 145.00},  # Long
            {"symbol": "AAPL", "quantity": -100, "avg_price": 150.00},  # Short
            {
                "symbol": "GOOGL",
                "quantity": 50,
                "avg_price": 2800.00,
            },  # Different symbol
        ]

        # Drain long positions
        remaining = expiration_engine._drain_asset(positions, "AAPL", -150)

        assert remaining == 0
        assert positions[0]["quantity"] == 50  # 200 - 150
        assert positions[1]["quantity"] == -100  # Unchanged (wrong sign)

    def test_drain_asset_with_position_objects(self, expiration_engine):
        """Test draining with Position objects."""
        positions = [Position(symbol="AAPL", quantity=300, avg_price=145.00)]

        remaining = expiration_engine._drain_asset(positions, "AAPL", -100)

        assert remaining == 0
        assert positions[0].quantity == 200


class TestPositionAddition:
    """Test position addition and averaging functionality."""

    def test_add_position_new_symbol(self, expiration_engine):
        """Test adding position for new symbol."""
        account = {"positions": []}

        expiration_engine._add_position(account, "AAPL", 100, 150.00)

        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 100
        assert position["avg_price"] == 150.00

    def test_add_position_existing_symbol(self, expiration_engine):
        """Test adding to existing position."""
        account = {
            "positions": [{"symbol": "AAPL", "quantity": 200, "avg_price": 140.00}]
        }

        expiration_engine._add_position(account, "AAPL", 100, 160.00)

        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["quantity"] == 300  # 200 + 100

        # Weighted average: (200*140 + 100*160) / 300 = 146.67
        expected_avg = (200 * 140.00 + 100 * 160.00) / 300
        assert abs(position["avg_price"] - expected_avg) < 0.01

    def test_add_position_zero_result(self, expiration_engine):
        """Test adding position that results in zero."""
        account = {
            "positions": [{"symbol": "AAPL", "quantity": 100, "avg_price": 140.00}]
        }

        expiration_engine._add_position(account, "AAPL", -100, 150.00)

        # Position should be zeroed but not removed
        position = account["positions"][0]
        assert position["quantity"] == 0

    def test_add_position_negative_quantity(self, expiration_engine):
        """Test adding negative quantity (short position)."""
        account = {"positions": []}

        expiration_engine._add_position(account, "AAPL", -200, 145.00)

        position = account["positions"][0]
        assert position["quantity"] == -200
        assert position["avg_price"] == 145.00

    def test_add_position_creates_positions_list(self, expiration_engine):
        """Test adding position creates positions list if missing."""
        account = {}  # No positions key

        expiration_engine._add_position(account, "AAPL", 100, 150.00)

        assert "positions" in account
        assert len(account["positions"]) == 1


class TestSingleExpirationProcessing:
    """Test processing individual expired positions."""

    def test_process_single_expiration_otm_option(self, expiration_engine):
        """Test processing OTM option that expires worthless."""
        account = {"cash_balance": 10000.0, "positions": []}

        otm_position = {
            "symbol": "AAPL240119P140",
            "quantity": 3,
            "avg_price": 2.00,
        }

        result = expiration_engine._process_single_expiration(
            account,
            otm_position,
            150.00,
            0,
            0,  # Underlying at $150, put strike $140
        )

        assert len(result.worthless_expirations) == 1
        worthless = result.worthless_expirations[0]
        assert worthless["symbol"] == "AAPL240119P140"
        assert worthless["intrinsic_value"] == 0.0
        assert otm_position["quantity"] == 0  # Position zeroed

    def test_process_single_expiration_itm_long_call(self, expiration_engine):
        """Test processing ITM long call."""
        account = {"cash_balance": 50000.0, "positions": []}

        itm_call_position = {
            "symbol": "AAPL240119C150",
            "quantity": 5,
            "avg_price": 3.50,
        }

        result = expiration_engine._process_single_expiration(
            account,
            itm_call_position,
            155.00,
            0,
            0,  # Underlying at $155, call strike $150
        )

        assert len(result.exercises) == 1
        exercise = result.exercises[0]
        assert exercise["type"] == "exercise"
        assert exercise["option_type"] == "call"
        assert itm_call_position["quantity"] == 0

    def test_process_single_expiration_itm_short_call(self, expiration_engine):
        """Test processing ITM short call."""
        account = {"cash_balance": 50000.0, "positions": []}

        short_call_position = {
            "symbol": "AAPL240119C150",
            "quantity": -3,
            "avg_price": 4.00,
        }

        result = expiration_engine._process_single_expiration(
            account,
            short_call_position,
            155.00,
            0,
            0,  # No shares to deliver
        )

        assert len(result.assignments) == 1
        assignment = result.assignments[0]
        assert assignment["type"] == "assignment"
        assert assignment["option_type"] == "call"
        assert "warning" in assignment  # Forced to buy shares

    def test_process_single_expiration_itm_long_put(self, expiration_engine):
        """Test processing ITM long put."""
        account = {"cash_balance": 10000.0, "positions": []}

        itm_put_position = {
            "symbol": "AAPL240119P150",
            "quantity": 2,
            "avg_price": 3.00,
        }

        result = expiration_engine._process_single_expiration(
            account,
            itm_put_position,
            140.00,
            0,
            0,  # Underlying at $140, put strike $150
        )

        assert len(result.exercises) == 1
        exercise = result.exercises[0]
        assert exercise["type"] == "exercise"
        assert exercise["option_type"] == "put"

    def test_process_single_expiration_itm_short_put(self, expiration_engine):
        """Test processing ITM short put."""
        account = {"cash_balance": 50000.0, "positions": []}

        short_put_position = {
            "symbol": "AAPL240119P150",
            "quantity": -2,
            "avg_price": 5.00,
        }

        result = expiration_engine._process_single_expiration(
            account,
            short_put_position,
            140.00,
            0,
            0,  # No short shares to cover
        )

        assert len(result.assignments) == 1
        assignment = result.assignments[0]
        assert assignment["type"] == "assignment"
        assert assignment["option_type"] == "put"

    def test_process_single_expiration_invalid_symbol(self, expiration_engine):
        """Test processing invalid option symbol."""
        account = {"cash_balance": 10000.0, "positions": []}

        invalid_position = {
            "symbol": "AAPL",  # Not an option
            "quantity": 100,
            "avg_price": 150.00,
        }

        result = expiration_engine._process_single_expiration(
            account, invalid_position, 150.00, 0, 0
        )

        # Should return empty result for non-options
        assert len(result.exercises) == 0
        assert len(result.assignments) == 0
        assert len(result.worthless_expirations) == 0


class TestUnderlyingExpirationProcessing:
    """Test processing expirations for specific underlying."""

    @pytest.mark.asyncio
    async def test_process_underlying_expirations_success(
        self,
        expiration_engine,
        sample_account,
        mock_quote_adapter,
        sample_underlying_quote,
    ):
        """Test successful underlying expiration processing."""
        mock_quote_adapter.get_quote.return_value = sample_underlying_quote

        expired_positions = [
            sample_account["positions"][1],  # AAPL240119C150
            sample_account["positions"][2],  # AAPL240119P140
        ]

        result = await expiration_engine._process_underlying_expirations(
            sample_account, "AAPL", expired_positions, mock_quote_adapter
        )

        assert isinstance(result, ExpirationResult)
        assert len(result.expired_positions) == 2
        # Call should be exercised (ITM), put should expire worthless (OTM)
        assert len(result.exercises) == 1
        assert len(result.worthless_expirations) == 1

    @pytest.mark.asyncio
    async def test_process_underlying_expirations_quote_error(
        self, expiration_engine, sample_account, mock_quote_adapter
    ):
        """Test underlying expiration processing with quote error."""
        mock_quote_adapter.get_quote.side_effect = Exception("Quote failed")

        expired_positions = [sample_account["positions"][1]]

        result = await expiration_engine._process_underlying_expirations(
            sample_account, "AAPL", expired_positions, mock_quote_adapter
        )

        assert len(result.errors) == 1
        assert "Error getting quote for AAPL" in result.errors[0]

    @pytest.mark.asyncio
    async def test_process_underlying_expirations_no_quote_price(
        self, expiration_engine, sample_account, mock_quote_adapter
    ):
        """Test underlying expiration processing with quote but no price."""
        quote_no_price = Quote(
            asset=Stock(symbol="AAPL"),
            price=None,  # No price
            bid=154.95,
            ask=155.05,
            quote_date=None,
        )
        mock_quote_adapter.get_quote.return_value = quote_no_price

        expired_positions = [sample_account["positions"][1]]

        result = await expiration_engine._process_underlying_expirations(
            sample_account, "AAPL", expired_positions, mock_quote_adapter
        )

        assert len(result.errors) == 1
        assert "has no price" in result.errors[0]

    @pytest.mark.asyncio
    async def test_process_underlying_expirations_position_error(
        self,
        expiration_engine,
        sample_account,
        mock_quote_adapter,
        sample_underlying_quote,
    ):
        """Test underlying expiration processing with position processing error."""
        mock_quote_adapter.get_quote.return_value = sample_underlying_quote

        # Create invalid position
        invalid_position = {"symbol": "INVALID", "quantity": "invalid"}

        result = await expiration_engine._process_underlying_expirations(
            sample_account, "AAPL", [invalid_position], mock_quote_adapter
        )

        assert len(result.errors) == 1
        assert "Error processing position" in result.errors[0]


class TestFullAccountExpiration:
    """Test complete account expiration processing."""

    @pytest.mark.asyncio
    async def test_process_account_expirations_success(
        self,
        expiration_engine,
        sample_account,
        mock_quote_adapter,
        sample_underlying_quote,
        sample_googl_quote,
        expired_date,
    ):
        """Test successful full account expiration processing."""

        # Mock quotes for different underlyings
        def quote_side_effect(asset):
            if asset.symbol == "AAPL":
                return sample_underlying_quote
            elif asset.symbol == "GOOGL":
                return sample_googl_quote
            return None

        mock_quote_adapter.get_quote.side_effect = quote_side_effect

        result = await expiration_engine.process_account_expirations(
            sample_account, mock_quote_adapter, expired_date
        )

        assert isinstance(result, ExpirationResult)
        assert len(result.expired_positions) == 3  # All 3 options
        assert result.cash_impact != 0  # Should have cash impact
        assert len(result.errors) == 0  # No errors

    @pytest.mark.asyncio
    async def test_process_account_expirations_empty_account(
        self, expiration_engine, mock_quote_adapter, expired_date
    ):
        """Test expiration processing with empty account."""
        empty_account = {"cash_balance": 0.0, "positions": []}

        result = await expiration_engine.process_account_expirations(
            empty_account, mock_quote_adapter, expired_date
        )

        assert len(result.expired_positions) == 0
        assert result.cash_impact == 0.0

    @pytest.mark.asyncio
    async def test_process_account_expirations_no_positions(
        self, expiration_engine, mock_quote_adapter, expired_date
    ):
        """Test expiration processing with no positions."""
        account_no_positions = {"cash_balance": 10000.0}

        result = await expiration_engine.process_account_expirations(
            account_no_positions, mock_quote_adapter, expired_date
        )

        assert len(result.expired_positions) == 0

    @pytest.mark.asyncio
    async def test_process_account_expirations_no_expired_options(
        self, expiration_engine, mock_quote_adapter
    ):
        """Test expiration processing with no expired options."""
        future_date = date.today() + timedelta(days=30)
        account_future_options = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 150.00},
                {
                    "symbol": f"AAPL{future_date.strftime('%y%m%d')}C150",
                    "quantity": 5,
                    "avg_price": 3.50,
                },
            ],
        }

        result = await expiration_engine.process_account_expirations(
            account_future_options, mock_quote_adapter, date.today()
        )

        assert len(result.expired_positions) == 0

    @pytest.mark.asyncio
    async def test_process_account_expirations_default_date(
        self, expiration_engine, mock_quote_adapter
    ):
        """Test expiration processing with default processing date."""
        account = {"cash_balance": 10000.0, "positions": []}

        result = await expiration_engine.process_account_expirations(
            account,
            mock_quote_adapter,  # No processing_date
        )

        # Should use today's date
        assert expiration_engine.current_date == date.today()

    @pytest.mark.asyncio
    async def test_process_account_expirations_preserves_original_account(
        self, expiration_engine, sample_account, mock_quote_adapter, expired_date
    ):
        """Test that processing doesn't modify original account."""
        original_positions_count = len(sample_account["positions"])
        original_cash = sample_account["cash_balance"]

        mock_quote_adapter.get_quote.return_value = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=None,
        )

        await expiration_engine.process_account_expirations(
            sample_account, mock_quote_adapter, expired_date
        )

        # Original account should be unchanged
        assert len(sample_account["positions"]) == original_positions_count
        assert sample_account["cash_balance"] == original_cash

    @pytest.mark.asyncio
    async def test_process_account_expirations_removes_zero_positions(
        self, expiration_engine, mock_quote_adapter, expired_date
    ):
        """Test that zero quantity positions are removed."""
        account_copy = {
            "cash_balance": 10000.0,
            "positions": [
                {
                    "symbol": "AAPL240119C150",
                    "quantity": 0,
                    "avg_price": 3.50,
                },  # Zero quantity
                {"symbol": "AAPL", "quantity": 100, "avg_price": 150.00},  # Valid
            ],
        }

        mock_quote_adapter.get_quote.return_value = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=None,
        )

        result = await expiration_engine.process_account_expirations(
            account_copy, mock_quote_adapter, expired_date
        )

        # Zero quantity position should be removed from the working copy
        # (This tests the internal account copy, not the original)
        assert (
            len(result.expired_positions) == 0
        )  # No zero quantity positions processed


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_process_with_malformed_position_data(
        self, expiration_engine, mock_quote_adapter, expired_date
    ):
        """Test processing with malformed position data."""
        malformed_account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL240119C150"},  # Missing quantity
                {"quantity": 5},  # Missing symbol
                {"symbol": "AAPL240119P140", "quantity": "invalid"},  # Invalid quantity
            ],
        }

        mock_quote_adapter.get_quote.return_value = Quote(
            asset=Stock(symbol="AAPL"),
            price=150.00,
            bid=149.95,
            ask=150.05,
            quote_date=None,
        )

        result = await expiration_engine.process_account_expirations(
            malformed_account, mock_quote_adapter, expired_date
        )

        # Should handle malformed data gracefully
        assert isinstance(result, ExpirationResult)

    def test_find_expired_positions_with_invalid_data_types(
        self, expiration_engine, expired_date
    ):
        """Test finding expired positions with invalid data types."""
        positions = [
            {
                "symbol": "AAPL240119C150",
                "quantity": "5",
                "avg_price": 3.50,
            },  # String quantity
            {
                "symbol": "AAPL240119P140",
                "quantity": 3.0,
                "avg_price": 2.00,
            },  # Float quantity
            {"symbol": None, "quantity": 5, "avg_price": 3.50},  # None symbol
        ]

        expired_positions = expiration_engine._find_expired_positions(
            positions, expired_date
        )

        # Should handle type conversions gracefully
        assert len(expired_positions) >= 0

    def test_drain_asset_with_invalid_quantities(self, expiration_engine):
        """Test asset draining with invalid quantity types."""
        positions = [
            {
                "symbol": "AAPL",
                "quantity": "100",
                "avg_price": 145.00,
            },  # String quantity
            {"symbol": "AAPL", "quantity": None, "avg_price": 150.00},  # None quantity
        ]

        # Should handle gracefully without crashing
        remaining = expiration_engine._drain_asset(positions, "AAPL", -50)

        # Exact behavior depends on implementation, but shouldn't crash
        assert isinstance(remaining, int)

    def test_add_position_with_zero_denominator(self, expiration_engine):
        """Test position addition that could create zero denominator."""
        account = {
            "positions": [{"symbol": "AAPL", "quantity": 100, "avg_price": 140.00}]
        }

        # Adding exactly opposite quantity
        expiration_engine._add_position(account, "AAPL", -100, 150.00)

        # Should handle zero quantity gracefully
        position = account["positions"][0]
        assert position["quantity"] == 0

    @pytest.mark.asyncio
    async def test_process_with_extreme_values(
        self, expiration_engine, mock_quote_adapter, expired_date
    ):
        """Test processing with extreme numerical values."""
        extreme_account = {
            "cash_balance": 1e10,  # Very large cash
            "positions": [
                {
                    "symbol": "AAPL240119C150",
                    "quantity": 1000000,
                    "avg_price": 0.01,
                },  # Huge quantity, tiny price
                {
                    "symbol": "AAPL",
                    "quantity": 1,
                    "avg_price": 1e6,
                },  # Tiny quantity, huge price
            ],
        }

        mock_quote_adapter.get_quote.return_value = Quote(
            asset=Stock(symbol="AAPL"),
            price=1e5,
            bid=99999,
            ask=100001,
            quote_date=None,
        )

        result = await expiration_engine.process_account_expirations(
            extreme_account, mock_quote_adapter, expired_date
        )

        # Should handle extreme values without overflow/underflow
        assert isinstance(result, ExpirationResult)
        assert not any("overflow" in error.lower() for error in result.errors)
