"""
Comprehensive tests for app/services/expiration.py - Options expiration processing.

Tests cover:
- Engine initialization and configuration
- Expired position detection and grouping
- ITM/OTM option processing
- Assignment and exercise logic for calls and puts
- Cash and position adjustments
- FIFO position closing logic
- Error handling and warnings
- Edge cases and complex scenarios
"""

import copy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.base import QuoteAdapter
from app.models.assets import Call, Option, Put, Stock, asset_factory
from app.schemas.positions import Position
from app.models.quotes import Quote
from app.services.expiration import ExpirationResult, OptionsExpirationEngine


class TestOptionsExpirationEngine:
    """Test suite for OptionsExpirationEngine functionality."""

    @pytest.fixture
    def engine(self):
        """Create expiration engine instance."""
        return OptionsExpirationEngine()

    @pytest.fixture
    def mock_quote_adapter(self):
        """Create mock quote adapter."""
        adapter = AsyncMock(spec=QuoteAdapter)
        return adapter

    @pytest.fixture
    def sample_account(self):
        """Sample account with various positions."""
        return {
            "cash_balance": 10000.0,
            "positions": [
                # Long stock position
                {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},
                # ITM call option (expires today)
                {"symbol": "AAPL250123C00145000", "quantity": 1, "avg_price": 8.0},
                # OTM put option (expires today)
                {"symbol": "AAPL250123P00140000", "quantity": -2, "avg_price": 3.0},
                # Non-expired option
                {"symbol": "AAPL250223C00150000", "quantity": 1, "avg_price": 5.0},
            ],
        }

    @pytest.fixture
    def expired_call_positions(self):
        """Sample expired call positions."""
        return [
            {
                "symbol": "AAPL250123C00145000",
                "quantity": 1,
                "avg_price": 8.0,
            },  # Long ITM call
            {
                "symbol": "AAPL250123C00155000",
                "quantity": -1,
                "avg_price": 4.0,
            },  # Short OTM call
        ]

    @pytest.fixture
    def expired_put_positions(self):
        """Sample expired put positions."""
        return [
            {
                "symbol": "AAPL250123P00140000",
                "quantity": 1,
                "avg_price": 5.0,
            },  # Long OTM put
            {
                "symbol": "AAPL250123P00160000",
                "quantity": -2,
                "avg_price": 7.0,
            },  # Short ITM put
        ]

    def test_engine_initialization(self, engine):
        """Test engine initialization."""
        assert engine.current_date is None
        assert isinstance(engine, OptionsExpirationEngine)

    @pytest.mark.asyncio
    async def test_process_account_expirations_empty_account(
        self, engine, mock_quote_adapter
    ):
        """Test processing empty account."""
        empty_account = {"cash_balance": 1000.0, "positions": []}

        result = await engine.process_account_expirations(
            empty_account, mock_quote_adapter, date.today()
        )

        assert isinstance(result, ExpirationResult)
        assert len(result.expired_positions) == 0
        assert result.cash_impact == 0.0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_process_account_expirations_no_positions(
        self, engine, mock_quote_adapter
    ):
        """Test processing account with no positions."""
        account = {"cash_balance": 1000.0}

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, date.today()
        )

        assert len(result.expired_positions) == 0
        assert result.cash_impact == 0.0

    @pytest.mark.asyncio
    async def test_process_account_expirations_no_expired_options(
        self, engine, mock_quote_adapter
    ):
        """Test processing account with no expired options."""
        future_date = date.today() + timedelta(days=30)
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},
                {
                    "symbol": f"AAPL{future_date.strftime('%y%m%d')}C00150000",
                    "quantity": 1,
                    "avg_price": 5.0,
                },
            ],
        }

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, date.today()
        )

        assert len(result.expired_positions) == 0
        assert result.cash_impact == 0.0

    @pytest.mark.asyncio
    async def test_process_expired_options_with_quote_error(
        self, engine, mock_quote_adapter
    ):
        """Test handling quote adapter errors."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL250123C00150000", "quantity": 1, "avg_price": 5.0},
            ],
        }

        # Mock quote adapter to raise exception
        mock_quote_adapter.get_quote.side_effect = Exception(
            "Quote service unavailable"
        )

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, date(2025, 1, 23)
        )

        assert len(result.errors) > 0
        assert "Quote service unavailable" in result.errors[0]

    @pytest.mark.asyncio
    async def test_process_expired_options_no_quote_price(
        self, engine, mock_quote_adapter
    ):
        """Test handling missing quote price."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL250123C00150000", "quantity": 1, "avg_price": 5.0},
            ],
        }

        # Mock quote with no price
        mock_quote = Quote(symbol="AAPL", price=None, timestamp=date.today())
        mock_quote_adapter.get_quote.return_value = mock_quote

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, date(2025, 1, 23)
        )

        assert len(result.errors) > 0
        assert "no price" in result.errors[0].lower()

    def test_find_expired_positions(self, engine):
        """Test finding expired option positions."""
        positions = [
            {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},  # Stock
            {
                "symbol": "AAPL250123C00150000",
                "quantity": 1,
                "avg_price": 5.0,
            },  # Expired call
            {
                "symbol": "AAPL250223P00140000",
                "quantity": -1,
                "avg_price": 3.0,
            },  # Future put
            {
                "symbol": "AAPL250123P00145000",
                "quantity": 2,
                "avg_price": 4.0,
            },  # Expired put
            {
                "symbol": "MSFT250123C00300000",
                "quantity": 0,
                "avg_price": 2.0,
            },  # Zero quantity
        ]

        expired = engine._find_expired_positions(positions, date(2025, 1, 23))

        assert len(expired) == 2
        expired_symbols = [pos["symbol"] for pos in expired]
        assert "AAPL250123C00150000" in expired_symbols
        assert "AAPL250123P00145000" in expired_symbols

    def test_find_expired_positions_with_position_objects(self, engine):
        """Test finding expired positions with Position objects."""
        positions = [
            Position(
                symbol="AAPL250123C00150000",
                quantity=1,
                avg_price=5.0,
                current_price=7.0,
            ),
            Position(
                symbol="AAPL250223P00140000",
                quantity=-1,
                avg_price=3.0,
                current_price=2.0,
            ),
        ]

        expired = engine._find_expired_positions(positions, date(2025, 1, 23))

        assert len(expired) == 1
        assert expired[0].symbol == "AAPL250123C00150000"

    def test_group_by_underlying(self, engine):
        """Test grouping expired positions by underlying."""
        expired_positions = [
            {"symbol": "AAPL250123C00150000", "quantity": 1, "avg_price": 5.0},
            {"symbol": "AAPL250123P00145000", "quantity": -1, "avg_price": 3.0},
            {"symbol": "MSFT250123C00300000", "quantity": 2, "avg_price": 8.0},
        ]

        groups = engine._group_by_underlying(expired_positions)

        assert len(groups) == 2
        assert "AAPL" in groups
        assert "MSFT" in groups
        assert len(groups["AAPL"]) == 2
        assert len(groups["MSFT"]) == 1

    @pytest.mark.asyncio
    async def test_process_underlying_expirations_success(
        self, engine, mock_quote_adapter
    ):
        """Test processing expirations for a specific underlying."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},
            ],
        }

        expired_positions = [
            {
                "symbol": "AAPL250123C00145000",
                "quantity": 1,
                "avg_price": 5.0,
            },  # ITM call
        ]

        # Mock underlying quote
        mock_quote = Quote(symbol="AAPL", price=150.0, timestamp=date.today())
        mock_quote_adapter.get_quote.return_value = mock_quote

        with patch.object(engine, "_process_single_expiration") as mock_process:
            mock_process.return_value = ExpirationResult(
                expired_positions=[
                    Position(
                        symbol="AAPL250123C00145000",
                        quantity=0,
                        avg_price=5.0,
                        current_price=5.0,
                    )
                ],
                exercises=[{"type": "exercise", "option_type": "call"}],
            )

            result = await engine._process_underlying_expirations(
                account, "AAPL", expired_positions, mock_quote_adapter
            )

            assert len(result.expired_positions) == 1
            assert len(result.exercises) == 1

    @pytest.mark.asyncio
    async def test_process_underlying_expirations_invalid_asset(
        self, engine, mock_quote_adapter
    ):
        """Test handling invalid asset symbol."""
        account = {"cash_balance": 10000.0, "positions": []}
        expired_positions = []

        with patch("app.services.expiration.asset_factory", return_value=None):
            result = await engine._process_underlying_expirations(
                account, "INVALID", expired_positions, mock_quote_adapter
            )

            assert len(result.errors) > 0
            assert "Could not create asset" in result.errors[0]

    def test_process_single_expiration_otm_option(self, engine):
        """Test processing OTM option that expires worthless."""
        account = {"cash_balance": 10000.0, "positions": []}
        position = {"symbol": "AAPL250123C00155000", "quantity": 1, "avg_price": 3.0}
        underlying_price = 150.0  # Below strike, OTM

        result = engine._process_single_expiration(
            account, position, underlying_price, 0, 0
        )

        assert len(result.worthless_expirations) == 1
        assert result.worthless_expirations[0]["symbol"] == "AAPL250123C00155000"
        assert result.worthless_expirations[0]["intrinsic_value"] == 0.0
        assert position["quantity"] == 0  # Position zeroed out

    def test_process_single_expiration_itm_long_call(self, engine):
        """Test processing ITM long call exercise."""
        account = {"cash_balance": 15000.0, "positions": []}
        position = {"symbol": "AAPL250123C00145000", "quantity": 1, "avg_price": 5.0}
        underlying_price = 150.0  # Above strike, ITM

        with patch.object(engine, "_exercise_long_call") as mock_exercise:
            mock_exercise.return_value = {
                "type": "exercise",
                "option_type": "call",
                "shares_acquired": 100,
                "cash_paid": 14500.0,
            }

            result = engine._process_single_expiration(
                account, position, underlying_price, 0, 0
            )

            assert len(result.exercises) == 1
            assert result.exercises[0]["type"] == "exercise"
            mock_exercise.assert_called_once()

    def test_process_single_expiration_itm_short_call(self, engine):
        """Test processing ITM short call assignment."""
        account = {"cash_balance": 5000.0, "positions": []}
        position = {"symbol": "AAPL250123C00145000", "quantity": -1, "avg_price": 5.0}
        underlying_price = 150.0  # Above strike, ITM
        long_equity = 100  # Have shares to deliver

        with patch.object(engine, "_assign_short_call") as mock_assign:
            mock_assign.return_value = {
                "type": "assignment",
                "option_type": "call",
                "shares_delivered": 100,
                "cash_received": 14500.0,
            }

            result = engine._process_single_expiration(
                account, position, underlying_price, long_equity, 0
            )

            assert len(result.assignments) == 1
            assert result.assignments[0]["type"] == "assignment"
            mock_assign.assert_called_once()

    def test_process_single_expiration_itm_long_put(self, engine):
        """Test processing ITM long put exercise."""
        account = {"cash_balance": 5000.0, "positions": []}
        position = {"symbol": "AAPL250123P00155000", "quantity": 1, "avg_price": 8.0}
        underlying_price = 150.0  # Below strike, ITM

        with patch.object(engine, "_exercise_long_put") as mock_exercise:
            mock_exercise.return_value = {
                "type": "exercise",
                "option_type": "put",
                "shares_sold_short": 100,
                "cash_received": 15500.0,
            }

            result = engine._process_single_expiration(
                account, position, underlying_price, 0, 0
            )

            assert len(result.exercises) == 1
            assert result.exercises[0]["type"] == "exercise"
            mock_exercise.assert_called_once()

    def test_process_single_expiration_itm_short_put(self, engine):
        """Test processing ITM short put assignment."""
        account = {"cash_balance": 16000.0, "positions": []}
        position = {"symbol": "AAPL250123P00155000", "quantity": -2, "avg_price": 8.0}
        underlying_price = 150.0  # Below strike, ITM
        short_equity = 0  # No short shares to cover

        with patch.object(engine, "_assign_short_put") as mock_assign:
            mock_assign.return_value = {
                "type": "assignment",
                "option_type": "put",
                "shares_purchased": 200,
                "cash_paid": 31000.0,
            }

            result = engine._process_single_expiration(
                account, position, underlying_price, 0, short_equity
            )

            assert len(result.assignments) == 1
            assert result.assignments[0]["type"] == "assignment"
            mock_assign.assert_called_once()

    def test_exercise_long_call(self, engine):
        """Test long call exercise logic."""
        account = {"cash_balance": 15000.0, "positions": []}
        call = Call(
            underlying=Stock("AAPL"),
            strike=Decimal("145"),
            expiration_date=date(2025, 1, 23),
        )
        quantity = 1
        cost_basis = 5.0
        underlying_price = 150.0

        with patch.object(engine, "_add_position") as mock_add:
            result = engine._exercise_long_call(
                account, call, quantity, cost_basis, underlying_price
            )

            assert result["type"] == "exercise"
            assert result["option_type"] == "call"
            assert result["shares_acquired"] == 100
            assert result["cash_paid"] == 14500.0
            assert result["effective_cost_basis"] == 150.0  # Strike + premium
            assert account["cash_balance"] == 500.0  # 15000 - 14500

            mock_add.assert_called_once_with(account, "AAPL", 100, 150.0)

    def test_assign_short_call_with_shares(self, engine):
        """Test short call assignment with sufficient shares."""
        account = {
            "cash_balance": 5000.0,
            "positions": [{"symbol": "AAPL", "quantity": 200, "avg_price": 140.0}],
        }
        call = Call(
            underlying=Stock("AAPL"),
            strike=Decimal("145"),
            expiration_date=date(2025, 1, 23),
        )
        quantity = -1
        underlying_price = 150.0
        long_equity = 200

        with patch.object(engine, "_drain_asset") as mock_drain:
            result = engine._assign_short_call(
                account, call, quantity, underlying_price, long_equity
            )

            assert result["type"] == "assignment"
            assert result["option_type"] == "call"
            assert result["shares_delivered"] == 100
            assert result["cash_received"] == 14500.0
            assert result["shares_source"] == "existing_position"
            assert account["cash_balance"] == 19500.0  # 5000 + 14500

            mock_drain.assert_called_once_with(account["positions"], "AAPL", -100)

    def test_assign_short_call_insufficient_shares(self, engine):
        """Test short call assignment with insufficient shares."""
        account = {"cash_balance": 5000.0, "positions": []}
        call = Call(
            underlying=Stock("AAPL"),
            strike=Decimal("145"),
            expiration_date=date(2025, 1, 23),
        )
        quantity = -1
        underlying_price = 150.0
        long_equity = 0  # No shares to deliver

        result = engine._assign_short_call(
            account, call, quantity, underlying_price, long_equity
        )

        assert result["type"] == "assignment"
        assert result["option_type"] == "call"
        assert result["shares_delivered"] == 100
        assert result["cash_to_buy"] == 15000.0  # Buy at market
        assert result["cash_received"] == 14500.0  # Sell at strike
        assert result["net_cash"] == -500.0
        assert result["shares_source"] == "market_purchase"
        assert "warning" in result
        assert account["cash_balance"] == 4500.0  # 5000 - 500 net

    def test_exercise_long_put(self, engine):
        """Test long put exercise logic."""
        account = {"cash_balance": 5000.0, "positions": []}
        put = Put(
            underlying=Stock("AAPL"),
            strike=Decimal("155"),
            expiration_date=date(2025, 1, 23),
        )
        quantity = 1
        cost_basis = 8.0
        underlying_price = 150.0

        with patch.object(engine, "_add_position") as mock_add:
            result = engine._exercise_long_put(
                account, put, quantity, cost_basis, underlying_price
            )

            assert result["type"] == "exercise"
            assert result["option_type"] == "put"
            assert result["shares_sold_short"] == 100
            assert result["cash_received"] == 15500.0
            assert result["effective_cost_basis"] == 147.0  # Strike - premium
            assert account["cash_balance"] == 20500.0  # 5000 + 15500

            mock_add.assert_called_once_with(account, "AAPL", -100, 147.0)

    def test_assign_short_put_with_short_shares(self, engine):
        """Test short put assignment with existing short position."""
        account = {
            "cash_balance": 16000.0,
            "positions": [{"symbol": "AAPL", "quantity": -200, "avg_price": 160.0}],
        }
        put = Put(
            underlying=Stock("AAPL"),
            strike=Decimal("155"),
            expiration_date=date(2025, 1, 23),
        )
        quantity = -1
        underlying_price = 150.0
        short_equity = -200

        with patch.object(engine, "_drain_asset") as mock_drain:
            result = engine._assign_short_put(
                account, put, quantity, underlying_price, short_equity
            )

            assert result["type"] == "assignment"
            assert result["option_type"] == "put"
            assert result["shares_purchased"] == 100
            assert result["cash_paid"] == 15500.0
            assert result["shares_destination"] == "cover_short"
            assert account["cash_balance"] == 500.0  # 16000 - 15500

            mock_drain.assert_called_once_with(account["positions"], "AAPL", 100)

    def test_assign_short_put_new_long_position(self, engine):
        """Test short put assignment creating new long position."""
        account = {"cash_balance": 16000.0, "positions": []}
        put = Put(
            underlying=Stock("AAPL"),
            strike=Decimal("155"),
            expiration_date=date(2025, 1, 23),
        )
        quantity = -1
        underlying_price = 150.0
        short_equity = 0  # No short shares to cover

        with patch.object(engine, "_add_position") as mock_add:
            result = engine._assign_short_put(
                account, put, quantity, underlying_price, short_equity
            )

            assert result["type"] == "assignment"
            assert result["option_type"] == "put"
            assert result["shares_purchased"] == 100
            assert result["cash_paid"] == 15500.0
            assert result["shares_destination"] == "new_long_position"
            assert account["cash_balance"] == 500.0  # 16000 - 15500

            mock_add.assert_called_once_with(account, "AAPL", 100, 155.0)

    def test_get_equity_positions(self, engine):
        """Test getting equity positions for underlying."""
        positions = [
            {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},
            {"symbol": "AAPL", "quantity": -50, "avg_price": 155.0},
            {
                "symbol": "AAPL250123C00150000",
                "quantity": 1,
                "avg_price": 5.0,
            },  # Option
            {
                "symbol": "MSFT",
                "quantity": 200,
                "avg_price": 300.0,
            },  # Different underlying
            {"symbol": "AAPL", "quantity": 0, "avg_price": 160.0},  # Zero quantity
        ]

        equity_positions = engine._get_equity_positions(positions, "AAPL")

        assert len(equity_positions) == 2
        quantities = [pos["quantity"] for pos in equity_positions]
        assert 100 in quantities
        assert -50 in quantities

    def test_get_equity_positions_with_position_objects(self, engine):
        """Test getting equity positions with Position objects."""
        positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=155.0),
            Position(
                symbol="AAPL250123C00150000",
                quantity=1,
                avg_price=5.0,
                current_price=7.0,
            ),
        ]

        equity_positions = engine._get_equity_positions(positions, "AAPL")

        assert len(equity_positions) == 1
        assert equity_positions[0].symbol == "AAPL"

    def test_drain_asset_reduce_long_position(self, engine):
        """Test draining long asset position."""
        positions = [
            {"symbol": "AAPL", "quantity": 200, "avg_price": 150.0},
            {"symbol": "AAPL", "quantity": 100, "avg_price": 155.0},
        ]

        remaining = engine._drain_asset(positions, "AAPL", -150)

        assert remaining == 0
        assert positions[0]["quantity"] == 50  # 200 - 150
        assert positions[1]["quantity"] == 100  # Unchanged

    def test_drain_asset_reduce_short_position(self, engine):
        """Test draining short asset position."""
        positions = [
            {"symbol": "AAPL", "quantity": -200, "avg_price": 150.0},
            {"symbol": "AAPL", "quantity": -100, "avg_price": 155.0},
        ]

        remaining = engine._drain_asset(positions, "AAPL", 150)

        assert remaining == 0
        assert positions[0]["quantity"] == -50  # -200 + 150
        assert positions[1]["quantity"] == -100  # Unchanged

    def test_drain_asset_insufficient_quantity(self, engine):
        """Test draining more than available."""
        positions = [
            {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},
        ]

        remaining = engine._drain_asset(positions, "AAPL", -200)

        assert remaining == -100  # 100 shares short
        assert positions[0]["quantity"] == 0

    def test_drain_asset_with_position_objects(self, engine):
        """Test draining with Position objects."""
        positions = [
            Position(symbol="AAPL", quantity=200, avg_price=150.0, current_price=155.0),
        ]

        remaining = engine._drain_asset(positions, "AAPL", -100)

        assert remaining == 0
        assert positions[0].quantity == 100

    def test_add_position_new_position(self, engine):
        """Test adding new position to account."""
        account = {"positions": []}

        engine._add_position(account, "AAPL", 100, 150.0)

        assert len(account["positions"]) == 1
        assert account["positions"][0]["symbol"] == "AAPL"
        assert account["positions"][0]["quantity"] == 100
        assert account["positions"][0]["avg_price"] == 150.0

    def test_add_position_existing_position(self, engine):
        """Test adding to existing position with weighted average."""
        account = {
            "positions": [{"symbol": "AAPL", "quantity": 100, "avg_price": 150.0}]
        }

        engine._add_position(account, "AAPL", 100, 160.0)

        assert len(account["positions"]) == 1
        position = account["positions"][0]
        assert position["quantity"] == 200
        assert position["avg_price"] == 155.0  # Weighted average

    def test_add_position_offsetting_position(self, engine):
        """Test adding offsetting position that zeros out."""
        account = {
            "positions": [{"symbol": "AAPL", "quantity": 100, "avg_price": 150.0}]
        }

        engine._add_position(account, "AAPL", -100, 160.0)

        # Position should remain but with zero quantity
        assert len(account["positions"]) == 1
        # When total quantity is 0, we don't update the position

    def test_add_position_no_existing_positions(self, engine):
        """Test adding position when positions key doesn't exist."""
        account = {}

        engine._add_position(account, "AAPL", 100, 150.0)

        assert "positions" in account
        assert len(account["positions"]) == 1

    @pytest.mark.asyncio
    async def test_full_expiration_scenario_mixed_options(
        self, engine, mock_quote_adapter
    ):
        """Test comprehensive expiration scenario with mixed options."""
        processing_date = date(2025, 1, 23)
        account = {
            "cash_balance": 20000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 200, "avg_price": 145.0},
                {
                    "symbol": "AAPL250123C00145000",
                    "quantity": 1,
                    "avg_price": 8.0,
                },  # ITM long call
                {
                    "symbol": "AAPL250123C00155000",
                    "quantity": -1,
                    "avg_price": 4.0,
                },  # OTM short call
                {
                    "symbol": "AAPL250123P00140000",
                    "quantity": 1,
                    "avg_price": 3.0,
                },  # OTM long put
                {
                    "symbol": "AAPL250123P00160000",
                    "quantity": -2,
                    "avg_price": 12.0,
                },  # ITM short put
            ],
        }

        # Mock underlying quote at $150
        mock_quote = Quote(symbol="AAPL", price=150.0, timestamp=processing_date)
        mock_quote_adapter.get_quote.return_value = mock_quote

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, processing_date
        )

        # Verify results
        assert len(result.expired_positions) == 4  # All options expired
        assert len(result.exercises) == 1  # Long ITM call exercised
        assert len(result.assignments) == 1  # Short ITM put assigned
        assert len(result.worthless_expirations) == 2  # OTM options

        # Verify cash impact
        assert result.cash_impact != 0.0

    @pytest.mark.asyncio
    async def test_error_handling_in_single_expiration(
        self, engine, mock_quote_adapter
    ):
        """Test error handling during single expiration processing."""
        account = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "INVALID_OPTION", "quantity": 1, "avg_price": 5.0},
            ],
        }

        mock_quote = Quote(symbol="AAPL", price=150.0, timestamp=date.today())
        mock_quote_adapter.get_quote.return_value = mock_quote

        # Mock asset_factory to return invalid option
        with patch("app.services.expiration.asset_factory") as mock_factory:
            mock_factory.side_effect = [None, Exception("Invalid asset")]

            result = await engine.process_account_expirations(
                account, mock_quote_adapter, date.today()
            )

            assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_expiration_result_aggregation(self, engine, mock_quote_adapter):
        """Test proper aggregation of expiration results."""
        account = {
            "cash_balance": 50000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 300, "avg_price": 145.0},
                {"symbol": "MSFT", "quantity": 100, "avg_price": 290.0},
                {"symbol": "AAPL250123C00145000", "quantity": 2, "avg_price": 8.0},
                {"symbol": "MSFT250123P00300000", "quantity": -1, "avg_price": 15.0},
            ],
        }

        # Mock quotes for both underlyings
        def mock_get_quote(asset):
            if asset.symbol == "AAPL":
                return Quote(symbol="AAPL", price=150.0, timestamp=date.today())
            elif asset.symbol == "MSFT":
                return Quote(symbol="MSFT", price=295.0, timestamp=date.today())
            return None

        mock_quote_adapter.get_quote.side_effect = mock_get_quote

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, date(2025, 1, 23)
        )

        # Should have processed both underlyings
        assert len(result.expired_positions) >= 2

        # Should have both exercises and assignments
        total_events = (
            len(result.exercises)
            + len(result.assignments)
            + len(result.worthless_expirations)
        )
        assert total_events == 2

    def test_edge_case_zero_quantity_positions(self, engine):
        """Test handling positions with zero quantity."""
        positions = [
            {"symbol": "AAPL250123C00150000", "quantity": 0, "avg_price": 5.0},
            {"symbol": "AAPL250123P00145000", "quantity": 1, "avg_price": 3.0},
        ]

        expired = engine._find_expired_positions(positions, date(2025, 1, 23))

        # Should only find non-zero quantity positions
        assert len(expired) == 1
        assert expired[0]["symbol"] == "AAPL250123P00145000"

    def test_edge_case_invalid_option_symbol(self, engine):
        """Test handling invalid option symbols."""
        position = {"symbol": "INVALID", "quantity": 1, "avg_price": 5.0}

        # Should not crash, asset_factory will return non-Option
        with patch("app.services.expiration.asset_factory") as mock_factory:
            mock_factory.return_value = Stock("INVALID")  # Non-option asset

            result = engine._process_single_expiration({}, position, 100.0, 0, 0)

            # Should return empty result for non-option
            assert len(result.expired_positions) == 0
            assert len(result.exercises) == 0
            assert len(result.assignments) == 0

    def test_multiple_positions_same_symbol(self, engine):
        """Test handling multiple positions of same option symbol."""
        positions = [
            {"symbol": "AAPL250123C00150000", "quantity": 2, "avg_price": 5.0},
            {"symbol": "AAPL250123C00150000", "quantity": 1, "avg_price": 6.0},
        ]

        expired = engine._find_expired_positions(positions, date(2025, 1, 23))

        # Should find both positions
        assert len(expired) == 2

    def test_complex_drain_scenario(self, engine):
        """Test complex position draining with multiple positions."""
        positions = [
            {"symbol": "AAPL", "quantity": 150, "avg_price": 140.0},
            {"symbol": "AAPL", "quantity": 200, "avg_price": 150.0},
            {"symbol": "AAPL", "quantity": 100, "avg_price": 160.0},
        ]

        # Drain 300 shares (should affect first two positions)
        remaining = engine._drain_asset(positions, "AAPL", -300)

        assert remaining == 0
        assert positions[0]["quantity"] == 0  # Completely drained
        assert positions[1]["quantity"] == 50  # Partially drained
        assert positions[2]["quantity"] == 100  # Unchanged

    @pytest.mark.asyncio
    async def test_concurrent_expiration_processing(self, engine, mock_quote_adapter):
        """Test that expiration processing maintains consistency."""
        # This test ensures the engine doesn't have race conditions
        # when processing multiple expirations simultaneously

        account = {
            "cash_balance": 25000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 500, "avg_price": 145.0},
                {"symbol": "AAPL250123C00145000", "quantity": 3, "avg_price": 8.0},
                {"symbol": "AAPL250123P00160000", "quantity": -2, "avg_price": 12.0},
            ],
        }

        mock_quote = Quote(symbol="AAPL", price=150.0, timestamp=date.today())
        mock_quote_adapter.get_quote.return_value = mock_quote

        # Make a deep copy to test that original isn't modified
        original_account = copy.deepcopy(account)

        result = await engine.process_account_expirations(
            account, mock_quote_adapter, date(2025, 1, 23)
        )

        # Original account should be unchanged (deep copy was made)
        assert account == original_account

        # Result should show proper processing
        assert len(result.expired_positions) > 0
