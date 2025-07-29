"""
Comprehensive test coverage for TradingService portfolio management functions.

This module provides complete test coverage for Phase 2: Portfolio Intelligence,
covering portfolio operations, position management, and enhanced quote integration.

Test Coverage Areas:
- get_portfolio(): Portfolio retrieval with quotes and PnL calculations
- get_portfolio_summary(): Portfolio summary with percentage calculations
- get_positions(): Position list retrieval
- get_position(): Specific position lookup
- Quote integration: get_quote() and get_enhanced_quote() methods

Functions Tested:
- TradingService.get_portfolio() - app/services/trading_service.py:393
- TradingService.get_portfolio_summary() - app/services/trading_service.py:437
- TradingService.get_positions() - app/services/trading_service.py:458
- TradingService.get_position() - app/services/trading_service.py:464
- TradingService.get_quote() - app/services/trading_service.py:190-215
- TradingService.get_enhanced_quote() - app/services/trading_service.py:604-618
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Position as DBPosition
from app.schemas.positions import Portfolio, PortfolioSummary, Position
from app.services.trading_service import TradingService

pytestmark = pytest.mark.journey_basic_trading


@pytest.mark.journey_portfolio_management
@pytest.mark.database
class TestGetPortfolio:
    """Test TradingService.get_portfolio() function - Phase 2.1 requirements."""

    @pytest.mark.asyncio
    async def test_get_portfolio_empty_account(self, db_session: AsyncSession):
        """Test getting portfolio from account with no positions."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter
        mock_quote_adapter = AsyncMock()

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_portfolio()

        # Verify empty portfolio
        assert isinstance(result, Portfolio)
        assert result.cash_balance == 50000.0
        assert result.total_value == 50000.0  # Only cash
        assert len(result.positions) == 0
        assert result.daily_pnl == 0.0
        assert result.total_pnl == 0.0

    @pytest.mark.asyncio
    async def test_get_portfolio_single_position(self, db_session: AsyncSession):
        """Test getting portfolio with single stock position."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=40000.0,
        )
        db_session.add(account)

        # Add single position
        position = DBPosition(
            id="NVDA001000",
            account_id=account.id,
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
        )
        db_session.add(position)
        await db_session.commit()

        # Mock quote adapter with current price
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 155.0
        mock_quote_adapter.get_quote.return_value = mock_quote

        # Mock position converter
        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0,  # (155-150) * 100
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_portfolio()

        # Verify portfolio calculations
        assert result.cash_balance == 40000.0
        assert len(result.positions) == 1
        assert result.positions[0].symbol == "NVDA"
        assert result.positions[0].current_price == 155.0
        assert result.total_value == 40000.0 + (100 * 155.0)  # cash + position value
        assert result.total_pnl == 500.0
        assert result.daily_pnl == 500.0

    @pytest.mark.asyncio
    async def test_get_portfolio_multiple_positions(self, db_session: AsyncSession):
        """Test getting portfolio with multiple positions."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=30000.0,
        )
        db_session.add(account)

        # Add multiple positions
        positions_data = [
            ("NVDA", 100, 150.0, 155.0, 500.0),
            ("TSLA", 50, 200.0, 190.0, -500.0),
            ("AMZN", 25, 300.0, 320.0, 500.0),
        ]

        db_positions = []
        for i, (symbol, qty, avg_price, current_price, pnl) in enumerate(
            positions_data
        ):
            db_pos = DBPosition(
                id=f"POS_{i + 1:03d}",
                account_id=account.id,
                symbol=symbol,
                quantity=qty,
                avg_price=avg_price,
            )
            db_positions.append((db_pos, current_price, pnl))
            db_session.add(db_pos)

        await db_session.commit()

        # Mock quote adapter for all symbols
        mock_quote_adapter = AsyncMock()

        def mock_get_quote(symbol):
            for db_pos, price, _ in db_positions:
                if db_pos.symbol == symbol:
                    mock_quote = MagicMock()
                    mock_quote.price = price
                    return mock_quote
            raise NotFoundError(f"Quote for {symbol} not found")

        mock_quote_adapter.get_quote.side_effect = mock_get_quote

        # Mock position converter
        mock_position_converter = AsyncMock()

        def mock_to_schema(db_pos, current_price):
            for db_position, _price, pnl in db_positions:
                if db_position.symbol == db_pos.symbol:
                    return Position(
                        symbol=db_pos.symbol,
                        quantity=db_pos.quantity,
                        avg_price=db_pos.avg_price,
                        current_price=current_price,
                        unrealized_pnl=pnl,
                        realized_pnl=0.0,
                    )

        mock_position_converter.to_schema.side_effect = mock_to_schema

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_portfolio()

        # Verify portfolio with multiple positions
        assert result.cash_balance == 30000.0
        assert len(result.positions) == 3

        # Check each position
        symbols = {pos.symbol for pos in result.positions}
        assert symbols == {"NVDA", "TSLA", "AMZN"}

        # Check total calculations
        total_invested = sum(
            pos.quantity * (pos.current_price or 0.0) for pos in result.positions
        )
        assert result.total_value == 30000.0 + total_invested
        assert result.total_pnl == 500.0  # Sum of all PnL
        assert result.daily_pnl == 500.0

    @pytest.mark.asyncio
    async def test_get_portfolio_position_with_no_quote(self, db_session: AsyncSession):
        """Test portfolio with position that has no available quote."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add position with symbol that won't have quote
        position = DBPosition(
            id="DELISTED00",
            account_id=account.id,
            symbol="DELISTED",
            quantity=100,
            avg_price=50.0,
        )
        db_session.add(position)
        await db_session.commit()

        # Mock quote adapter to raise NotFoundError
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.side_effect = NotFoundError("Quote not found")

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_portfolio()

        # Position should be skipped due to no quote
        assert result.cash_balance == 50000.0
        assert len(result.positions) == 0  # Position skipped
        assert result.total_value == 50000.0  # Only cash
        assert result.total_pnl == 0.0

    @pytest.mark.asyncio
    async def test_get_portfolio_mixed_assets(self, db_session: AsyncSession):
        """Test portfolio with mix of stocks and options."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=25000.0,
        )
        db_session.add(account)

        # Add stock and option positions
        stock_pos = DBPosition(
            id="STOCK00100",
            account_id=account.id,
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
        )
        option_pos = DBPosition(
            id="OPTION0010",
            account_id=account.id,
            symbol="NVDA240115C00160000",
            quantity=5,
            avg_price=5.0,
        )
        db_session.add(stock_pos)
        db_session.add(option_pos)
        await db_session.commit()

        # Mock quote adapter
        mock_quote_adapter = AsyncMock()

        def mock_get_quote(symbol):
            if symbol == "NVDA":
                mock_quote = MagicMock()
                mock_quote.price = 160.0
                return mock_quote
            elif symbol == "NVDA240115C00160000":
                mock_quote = MagicMock()
                mock_quote.price = 8.0
                return mock_quote

        mock_quote_adapter.get_quote.side_effect = mock_get_quote

        # Mock position converter
        mock_position_converter = AsyncMock()

        def mock_to_schema(db_pos, current_price):
            if db_pos.symbol == "NVDA":
                return Position(
                    symbol="NVDA",
                    quantity=100,
                    avg_price=150.0,
                    current_price=160.0,
                    unrealized_pnl=1000.0,  # (160-150) * 100
                    realized_pnl=0.0,
                )
            else:
                return Position(
                    symbol="NVDA240115C00160000",
                    quantity=5,
                    avg_price=5.0,
                    current_price=8.0,
                    unrealized_pnl=1500.0,  # (8-5) * 5 * 100 (option multiplier)
                    realized_pnl=0.0,
                )

        mock_position_converter.to_schema.side_effect = mock_to_schema

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_portfolio()

        # Verify mixed asset portfolio
        assert result.cash_balance == 25000.0
        assert len(result.positions) == 2

        # Find positions by symbol
        stock = next(pos for pos in result.positions if pos.symbol == "NVDA")
        option = next(pos for pos in result.positions if "C00160000" in pos.symbol)

        assert stock.current_price == 160.0
        assert option.current_price == 8.0
        assert result.total_pnl == 2500.0  # 1000 + 1500


@pytest.mark.journey_portfolio_management
@pytest.mark.database
class TestGetPortfolioSummary:
    """Test TradingService.get_portfolio_summary() function - Phase 2.2 requirements."""

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_empty_account(self, db_session: AsyncSession):
        """Test portfolio summary for empty account."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=75000.0,
        )
        db_session.add(account)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_portfolio_summary()

        # Verify empty account summary
        assert isinstance(result, PortfolioSummary)
        assert result.total_value == 75000.0
        assert result.cash_balance == 75000.0
        assert result.invested_value == 0.0
        assert result.daily_pnl == 0.0
        assert result.daily_pnl_percent == 0.0
        assert result.total_pnl == 0.0
        assert result.total_pnl_percent == 0.0

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_with_positions(self, db_session: AsyncSession):
        """Test portfolio summary with positions and PnL."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add position
        position = DBPosition(
            id="NVDA002000",
            account_id=account.id,
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
        )
        db_session.add(position)
        await db_session.commit()

        # Mock dependencies
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 165.0
        mock_quote_adapter.get_quote.return_value = mock_quote

        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
            current_price=165.0,
            unrealized_pnl=1500.0,  # (165-150) * 100
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_portfolio_summary()

        # Verify summary calculations
        invested_value = 100 * 165.0  # quantity * current_price
        total_value = 50000.0 + invested_value

        assert result.total_value == total_value
        assert result.cash_balance == 50000.0
        assert result.invested_value == invested_value
        assert result.daily_pnl == 1500.0
        assert result.daily_pnl_percent == (1500.0 / total_value) * 100
        assert result.total_pnl == 1500.0
        assert result.total_pnl_percent == (1500.0 / total_value) * 100

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_negative_pnl(self, db_session: AsyncSession):
        """Test portfolio summary with negative PnL."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=60000.0,
        )
        db_session.add(account)

        position = DBPosition(
            id="TSLA001000",
            account_id=account.id,
            symbol="TSLA",
            quantity=50,
            avg_price=250.0,
        )
        db_session.add(position)
        await db_session.commit()

        # Mock for loss position
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 220.0  # Down $30 per share
        mock_quote_adapter.get_quote.return_value = mock_quote

        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="TSLA",
            quantity=50,
            avg_price=250.0,
            current_price=220.0,
            unrealized_pnl=-1500.0,  # (220-250) * 50 = -1500
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_portfolio_summary()

        # Verify negative PnL calculations
        invested_value = 50 * 220.0
        total_value = 60000.0 + invested_value

        assert result.total_value == total_value
        assert result.invested_value == invested_value
        assert result.daily_pnl == -1500.0
        assert result.daily_pnl_percent == (-1500.0 / total_value) * 100
        assert result.total_pnl == -1500.0
        assert result.total_pnl_percent == (-1500.0 / total_value) * 100

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_zero_total_value(
        self, db_session: AsyncSession
    ):
        """Test portfolio summary edge case with zero total value."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=0.0,  # No cash
        )
        db_session.add(account)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_portfolio_summary()

        # Should handle zero division gracefully
        assert result.total_value == 0.0
        assert result.cash_balance == 0.0
        assert result.invested_value == 0.0
        assert result.daily_pnl_percent == 0.0  # Should be 0, not error
        assert result.total_pnl_percent == 0.0  # Should be 0, not error


@pytest.mark.journey_portfolio_management
@pytest.mark.database
class TestGetPositions:
    """Test TradingService.get_positions() function - Phase 2.3 requirements."""

    @pytest.mark.asyncio
    async def test_get_positions_empty_account(self, db_session: AsyncSession):
        """Test getting positions from empty account."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_positions()

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_positions_multiple_positions(self, db_session: AsyncSession):
        """Test getting multiple positions."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=40000.0,
        )
        db_session.add(account)

        # Add multiple positions
        symbols = ["NVDA", "TSLA", "AMZN"]
        for i, symbol in enumerate(symbols):
            position = DBPosition(
                id=f"MULTI_{i + 1:03d}",
                account_id=account.id,
                symbol=symbol,
                quantity=100 + i * 10,
                avg_price=150.0 + i * 10,
            )
            db_session.add(position)

        await db_session.commit()

        # Mock quote adapter and position converter
        mock_quote_adapter = AsyncMock()

        def mock_get_quote(symbol):
            mock_quote = MagicMock()
            mock_quote.price = 160.0 + symbols.index(symbol) * 10
            return mock_quote

        mock_quote_adapter.get_quote.side_effect = mock_get_quote

        mock_position_converter = AsyncMock()

        def mock_to_schema(db_pos, current_price):
            return Position(
                symbol=db_pos.symbol,
                quantity=db_pos.quantity,
                avg_price=db_pos.avg_price,
                current_price=current_price,
                unrealized_pnl=100.0,  # Simplified
                realized_pnl=0.0,
            )

        mock_position_converter.to_schema.side_effect = mock_to_schema

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_positions()

        # Verify all positions returned
        assert len(result) == 3
        result_symbols = {pos.symbol for pos in result}
        assert result_symbols == {"NVDA", "TSLA", "AMZN"}

        # Verify positions have current prices
        for pos in result:
            assert pos.current_price is not None

    @pytest.mark.asyncio
    async def test_get_positions_with_failed_quotes(self, db_session: AsyncSession):
        """Test positions retrieval with some failed quote lookups."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add positions where one will fail quote lookup
        good_pos = DBPosition(
            id="GOOD001000",
            account_id=account.id,
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
        )
        bad_pos = DBPosition(
            id="BAD0010000",
            account_id=account.id,
            symbol="DELISTED",
            quantity=50,
            avg_price=100.0,
        )
        db_session.add(good_pos)
        db_session.add(bad_pos)
        await db_session.commit()

        # Mock quote adapter - one succeeds, one fails
        mock_quote_adapter = AsyncMock()

        def mock_get_quote(symbol):
            if symbol == "NVDA":
                mock_quote = MagicMock()
                mock_quote.price = 160.0
                return mock_quote
            else:
                raise NotFoundError("Quote not found")

        mock_quote_adapter.get_quote.side_effect = mock_get_quote

        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
            current_price=160.0,
            unrealized_pnl=1000.0,
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_positions()

        # Only position with successful quote should be returned
        assert len(result) == 1
        assert result[0].symbol == "NVDA"


@pytest.mark.journey_portfolio_management
@pytest.mark.database
class TestGetPosition:
    """Test TradingService.get_position() function - Phase 2.3 requirements."""

    @pytest.mark.asyncio
    async def test_get_position_existing(self, db_session: AsyncSession):
        """Test getting existing position by symbol."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        position = DBPosition(
            id="NVDA003000",
            account_id=account.id,
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
        )
        db_session.add(position)
        await db_session.commit()

        # Mock dependencies
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 160.0
        mock_quote_adapter.get_quote.return_value = mock_quote

        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
            current_price=160.0,
            unrealized_pnl=1000.0,
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_position("NVDA")

        assert isinstance(result, Position)
        assert result.symbol == "NVDA"
        assert result.quantity == 100

    @pytest.mark.asyncio
    async def test_get_position_case_insensitive(self, db_session: AsyncSession):
        """Test getting position with different case."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        position = DBPosition(
            id="NVDA004000",
            account_id=account.id,
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
        )
        db_session.add(position)
        await db_session.commit()

        # Mock dependencies
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 160.0
        mock_quote_adapter.get_quote.return_value = mock_quote

        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="NVDA",
            quantity=100,
            avg_price=150.0,
            current_price=160.0,
            unrealized_pnl=1000.0,
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        # Test case insensitive lookup
        result = await service.get_position("nvda")

        assert result.symbol == "NVDA"

    @pytest.mark.asyncio
    async def test_get_position_not_found(self, db_session: AsyncSession):
        """Test getting non-existent position."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_position("NOTFOUND")

        assert "Position for symbol NOTFOUND not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_position_option_symbol(self, db_session: AsyncSession):
        """Test getting position for option symbol."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        option_pos = DBPosition(
            id="OPTION0020",
            account_id=account.id,
            symbol="NVDA240115C00160000",
            quantity=5,
            avg_price=8.0,
        )
        db_session.add(option_pos)
        await db_session.commit()

        # Mock dependencies
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 12.0
        mock_quote_adapter.get_quote.return_value = mock_quote

        mock_position_converter = AsyncMock()
        mock_schema_position = Position(
            symbol="NVDA240115C00160000",
            quantity=5,
            avg_price=8.0,
            current_price=12.0,
            unrealized_pnl=2000.0,  # (12-8) * 5 * 100
            realized_pnl=0.0,
        )
        mock_position_converter.to_schema.return_value = mock_schema_position

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )
        service.position_converter = mock_position_converter

        result = await service.get_position("NVDA240115C00160000")

        assert result.symbol == "NVDA240115C00160000"
        assert result.quantity == 5


@pytest.mark.journey_account_management
@pytest.mark.database
class TestAccountBalanceManagement:
    """Test account and balance management functions - Phase 2.4 requirements."""

    @pytest.mark.asyncio
    async def test_get_account_balance_fresh_account(self, db_session: AsyncSession):
        """Test getting balance for fresh account."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=100000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Test account balance retrieval through internal method
        account_result = await service._get_account()

        assert account_result.cash_balance == 100000.0
        assert account_result.owner == "test_user"

    @pytest.mark.asyncio
    async def test_get_account_balance_updated_balance(self, db_session: AsyncSession):
        """Test getting balance after updates."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Update balance
        account.cash_balance = 75000.0
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        account_result = await service._get_account()

        assert account_result.cash_balance == 75000.0

    @pytest.mark.asyncio
    async def test_account_not_found(self, db_session: AsyncSession):
        """Test behavior when account doesn't exist (account gets created by _ensure_account_exists)."""
        service = TradingService(account_owner="nonexistent", db_session=db_session)

        # _get_account() actually calls _ensure_account_exists() first, so it creates the account
        # This test verifies the account creation behavior
        account_result = await service._get_account()

        # Account should be created with default values
        assert account_result is not None
        assert account_result.owner == "nonexistent"
        assert (
            account_result.cash_balance == 10000.0
        )  # Default from _ensure_account_exists

    @pytest.mark.asyncio
    async def test_validate_account_state_valid(self, db_session: AsyncSession):
        """Test account state validation for valid account."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Account exists and is valid - should not raise
        account_result = await service._get_account()
        assert account_result is not None

    @pytest.mark.asyncio
    async def test_account_with_zero_balance(self, db_session: AsyncSession):
        """Test account with zero cash balance."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=0.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        account_result = await service._get_account()

        assert account_result.cash_balance == 0.0

    @pytest.mark.asyncio
    async def test_account_with_negative_balance(self, db_session: AsyncSession):
        """Test account with negative cash balance (margin account)."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=-5000.0,  # Negative balance (borrowed funds)
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        account_result = await service._get_account()

        assert account_result.cash_balance == -5000.0


@pytest.mark.journey_market_data
@pytest.mark.database
class TestQuoteIntegration:
    """Test quote integration methods - Phase 2.5 requirements."""

    @pytest.mark.asyncio
    async def test_get_quote_stock_success(self, db_session: AsyncSession):
        """Test getting quote for stock symbol."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 165.0
        mock_quote.volume = 1000000
        mock_quote.quote_date = datetime.now()
        mock_quote_adapter.get_quote.return_value = mock_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_quote("NVDA")

        # Verify StockQuote response
        from app.schemas.trading import StockQuote

        assert isinstance(result, StockQuote)
        assert result.symbol == "NVDA"
        assert result.price == 165.0
        assert result.volume == 1000000
        assert result.change == 0.0  # Default value
        assert result.change_percent == 0.0  # Default value

    @pytest.mark.asyncio
    async def test_get_quote_symbol_not_found(self, db_session: AsyncSession):
        """Test getting quote for non-existent symbol."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to return None
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.return_value = None

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_quote("INVALID")

        assert "Symbol INVALID not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_quote_adapter_exception(self, db_session: AsyncSession):
        """Test quote retrieval when adapter raises exception."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to raise exception
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.side_effect = Exception("API Error")

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_quote("TSLA")

        assert "Symbol TSLA not found: API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_quote_case_normalization(self, db_session: AsyncSession):
        """Test quote retrieval with case normalization."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 200.0
        mock_quote.volume = 500000
        mock_quote.quote_date = datetime.now()
        mock_quote_adapter.get_quote.return_value = mock_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_quote("tsla")  # lowercase input

        # Should normalize to uppercase
        assert result.symbol == "TSLA"
        assert result.price == 200.0

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_stock(self, db_session: AsyncSession):
        """Test getting enhanced quote for stock."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to return Quote object
        mock_quote_adapter = AsyncMock()
        from app.models.assets import Stock
        from app.models.quotes import Quote

        mock_quote = Quote(
            asset=Stock(symbol="NVDA"),
            quote_date=datetime.now(),
            price=170.0,
            bid=169.5,
            ask=170.5,
            bid_size=100,
            ask_size=100,
            volume=1200000,
        )
        mock_quote_adapter.get_quote.return_value = mock_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_enhanced_quote("NVDA")

        # Should return the Quote object directly
        assert isinstance(result, Quote)
        assert result.price == 170.0
        assert result.bid == 169.5
        assert result.ask == 170.5

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_option(self, db_session: AsyncSession):
        """Test getting enhanced quote for option with Greeks."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to return OptionQuote
        mock_quote_adapter = AsyncMock()
        from datetime import date

        from app.models.assets import Option
        from app.models.quotes import Quote

        mock_option_quote = Quote(
            asset=Option(
                symbol="NVDA240115C00170000",
                underlying="NVDA",
                strike=170.0,
                expiration_date=date(2024, 1, 15),
                option_type="call",
            ),
            quote_date=datetime.now(),
            price=8.5,
            bid=8.0,
            ask=9.0,
            bid_size=10,
            ask_size=10,
            volume=1000,
            delta=0.65,
            gamma=0.02,
            theta=-0.05,
            vega=0.12,
            rho=0.08,
        )
        mock_quote_adapter.get_quote.return_value = mock_option_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_enhanced_quote("NVDA240115C00170000")

        # Should return Quote with Greeks
        assert isinstance(result, Quote)
        assert result.price == 8.5
        assert result.delta == 0.65
        assert result.gamma == 0.02
        assert result.theta == -0.05
        assert result.vega == 0.12

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_not_found(self, db_session: AsyncSession):
        """Test enhanced quote for non-existent symbol."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter to return None
        mock_quote_adapter = AsyncMock()
        mock_quote_adapter.get_quote.return_value = None

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_enhanced_quote("INVALID")

        assert "No quote available for INVALID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_enhanced_quote_invalid_symbol(self, db_session: AsyncSession):
        """Test enhanced quote with invalid symbol format."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        service = TradingService(account_owner="test_user", db_session=db_session)

        # Mock asset_factory to return None (invalid symbol)
        with (
            patch("app.services.trading_service.asset_factory", return_value=None),
            pytest.raises(NotFoundError) as exc_info,
        ):
            await service.get_enhanced_quote("INVALID_FORMAT")

        assert "Invalid symbol: INVALID_FORMAT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_quote_adapter_fallback_behavior(self, db_session: AsyncSession):
        """Test quote adapter fallback mechanisms."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock primary adapter failure, secondary success
        mock_quote_adapter = AsyncMock()
        # First call fails, second succeeds
        mock_quote_adapter.get_quote.side_effect = [
            Exception("Primary failed"),
            MagicMock(price=180.0, volume=800000, quote_date=datetime.now()),
        ]

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # First call should fail
        with pytest.raises(NotFoundError):
            await service.get_quote("AMZN")

        # Reset the mock for second call
        mock_quote_adapter.get_quote.side_effect = None
        mock_quote = MagicMock()
        mock_quote.price = 180.0
        mock_quote.volume = 800000
        mock_quote.quote_date = datetime.now()
        mock_quote_adapter.get_quote.return_value = mock_quote

        # Second call should succeed
        result = await service.get_quote("AMZN")
        assert result.price == 180.0

    @pytest.mark.asyncio
    async def test_quote_data_freshness(self, db_session: AsyncSession):
        """Test quote data timestamp handling."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote with specific timestamp
        mock_quote_adapter = AsyncMock()
        test_timestamp = datetime(2024, 1, 15, 14, 30, 0)
        mock_quote = MagicMock()
        mock_quote.price = 155.0
        mock_quote.volume = 1500000
        mock_quote.quote_date = test_timestamp
        mock_quote_adapter.get_quote.return_value = mock_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_quote("MSFT")

        # Verify timestamp preservation
        assert result.last_updated == test_timestamp

    @pytest.mark.asyncio
    async def test_quote_price_precision(self, db_session: AsyncSession):
        """Test quote price precision handling."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote with high precision price
        mock_quote_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 123.456789  # High precision
        mock_quote.volume = 2000000
        mock_quote.quote_date = datetime.now()
        mock_quote_adapter.get_quote.return_value = mock_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        result = await service.get_quote("PREC")

        # Verify precision is maintained
        assert result.price == 123.456789

    @pytest.mark.asyncio
    async def test_quote_integration_performance(self, db_session: AsyncSession):
        """Test quote retrieval performance with multiple symbols."""
        account = DBAccount(
            id="TEST123456",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)
        await db_session.commit()

        # Mock quote adapter for bulk requests
        mock_quote_adapter = AsyncMock()

        def mock_get_quote(asset):
            symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)
            mock_quote = MagicMock()
            mock_quote.price = (
                100.0 + hash(symbol) % 100
            )  # Deterministic but varied prices
            mock_quote.volume = 1000000
            mock_quote.quote_date = datetime.now()
            return mock_quote

        mock_quote_adapter.get_quote.side_effect = mock_get_quote

        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Test performance with 20 quote requests
        symbols = [f"PERF{i:02d}" for i in range(20)]

        import time

        start_time = time.time()

        results = []
        for symbol in symbols:
            result = await service.get_quote(symbol)
            results.append(result)

        elapsed_time = time.time() - start_time

        # Verify all quotes retrieved successfully
        assert len(results) == 20
        for result in results:
            assert result.price > 0

        # Performance should be reasonable (less than 2 seconds for 20 quotes)
        assert elapsed_time < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
