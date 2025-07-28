"""
Test Position Greeks Calculation in TradingService.

Tests for get_position_greeks() method covering lines 519-560.
Target: 12 comprehensive tests for individual position Greeks calculation.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.schemas.positions import Position
from app.services.trading_service import TradingService


@pytest.mark.asyncio
class TestTradingServicePositionGreeks:
    """Test position Greeks calculation functionality."""

    async def test_get_position_greeks_success(self, async_db_session):
        """Test successful position Greeks calculation."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option position with proper asset
        position = Position(
            symbol="AAPL240315C00150000",
            quantity=2,
            avg_price=5.50,
            current_price=6.25,
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote with Greeks
        quote = Mock()
        quote.delta = 0.6
        quote.gamma = 0.05
        quote.theta = -0.15
        quote.vega = 0.25
        quote.rho = 0.10
        quote.quote_date = datetime.now()

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_position_greeks("AAPL240315C00150000")

        # Verify - Greeks scaled by quantity * multiplier (2 * 100 = 200)
        assert result["symbol"] == "AAPL240315C00150000"
        assert result["position_greeks"]["delta"] == 120.0  # 0.6 * 200
        assert result["position_greeks"]["gamma"] == 10.0  # 0.05 * 200
        assert result["position_greeks"]["theta"] == -30.0  # -0.15 * 200
        assert result["position_greeks"]["vega"] == 50.0  # 0.25 * 200
        assert result["position_greeks"]["rho"] == 20.0  # 0.10 * 200

    async def test_get_position_greeks_stock_position_error(self, async_db_session):
        """Test error when position is not an options position."""
        from app.models.assets import Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create stock position with stock asset (is_option = False)
        position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.00,
            current_price=155.00,
            asset=Stock(symbol="AAPL"),
        )

        # Mock quote without delta attribute (not an options quote)
        quote = Mock()
        del quote.delta  # Remove delta attribute entirely

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test - should raise error for non-options position
        with pytest.raises(ValueError, match="Position is not an options position"):
            await trading_service.get_position_greeks("AAPL")

    async def test_get_position_greeks_position_not_found(self, async_db_session):
        """Test error when position is not found."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Mock get_position to raise exception (simulating position not found)
        trading_service.get_position = AsyncMock(
            side_effect=ValueError("Position not found")
        )

        # Test - should raise error for missing position
        with pytest.raises(ValueError, match="Position not found"):
            await trading_service.get_position_greeks("NONEXISTENT")

    async def test_get_position_greeks_quote_not_found(self, async_db_session):
        """Test error when quote is not found."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option position
        position = Position(
            symbol="AAPL240315C00150000",
            quantity=1,
            avg_price=5.00,
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock dependencies - position exists but quote call fails
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(
            side_effect=Exception("Quote not found")
        )

        # Test - should raise error for missing quote
        with pytest.raises(Exception, match="Quote not found"):
            await trading_service.get_position_greeks("AAPL240315C00150000")

    async def test_get_position_greeks_quote_missing_delta(self, async_db_session):
        """Test error when quote doesn't have delta (not an options quote)."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option position
        position = Position(
            symbol="AAPL240315C00150000",
            quantity=1,
            avg_price=5.00,
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote without delta attribute (not an options quote)
        quote = Mock()
        del quote.delta  # Remove delta attribute entirely

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test - should raise error for quote without delta
        with pytest.raises(ValueError, match="Position is not an options position"):
            await trading_service.get_position_greeks("AAPL240315C00150000")

    async def test_get_position_greeks_put_option(self, async_db_session):
        """Test Greeks calculation for put option."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create put option position
        position = Position(
            symbol="TSLA240315P00200000",
            quantity=3,
            avg_price=8.75,
            current_price=12.50,
            asset=Option(
                symbol="TSLA240315P00200000",
                underlying=Stock(symbol="TSLA"),
                option_type="put",
                strike=200.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote with put option Greeks
        quote = Mock()
        quote.delta = -0.4  # Put options have negative delta
        quote.gamma = 0.03
        quote.theta = -0.20
        quote.vega = 0.35
        quote.rho = -0.08  # Put options have negative rho
        quote.quote_date = datetime.now()

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_position_greeks("TSLA240315P00200000")

        # Verify - Greeks scaled by quantity * multiplier (3 * 100 = 300)
        assert result["symbol"] == "TSLA240315P00200000"
        assert result["position_greeks"]["delta"] == pytest.approx(-120.0)  # -0.4 * 300
        assert result["position_greeks"]["gamma"] == pytest.approx(9.0)  # 0.03 * 300
        assert result["position_greeks"]["theta"] == pytest.approx(-60.0)  # -0.20 * 300
        assert result["position_greeks"]["vega"] == pytest.approx(105.0)  # 0.35 * 300
        assert result["position_greeks"]["rho"] == pytest.approx(-24.0)  # -0.08 * 300


    async def test_get_position_greeks_short_position(self, async_db_session):
        """Test Greeks calculation for short position (negative quantity)."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create short option position
        position = Position(
            symbol="QQQ240315C00380000",
            quantity=-5,  # Short position
            avg_price=2.80,
            current_price=1.95,
            asset=Option(
                symbol="QQQ240315C00380000",
                underlying=Stock(symbol="QQQ"),
                option_type="call",
                strike=380.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote with Greeks
        quote = Mock()
        quote.delta = 0.25
        quote.gamma = 0.04
        quote.theta = -0.12
        quote.vega = 0.22
        quote.rho = 0.06
        quote.quote_date = datetime.now()

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_position_greeks("QQQ240315C00380000")

        # Verify - Greeks scaled by quantity * multiplier (-5 * 100 = -500)
        assert result["symbol"] == "QQQ240315C00380000"
        assert result["position_greeks"]["delta"] == pytest.approx(
            -125.0
        )  # 0.25 * -500
        assert result["position_greeks"]["gamma"] == pytest.approx(-20.0)  # 0.04 * -500
        assert result["position_greeks"]["theta"] == pytest.approx(
            60.0
        )  # -0.12 * -500 (double negative)
        assert result["position_greeks"]["vega"] == pytest.approx(-110.0)  # 0.22 * -500
        assert result["position_greeks"]["rho"] == pytest.approx(-30.0)  # 0.06 * -500

    async def test_get_position_greeks_zero_greeks(self, async_db_session):
        """Test Greeks calculation with zero values."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option position
        position = Position(
            symbol="IWM240315C00190000",
            quantity=10,
            avg_price=1.50,
            current_price=0.75,
            asset=Option(
                symbol="IWM240315C00190000",
                underlying=Stock(symbol="IWM"),
                option_type="call",
                strike=190.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote with zero Greeks (deep OTM option near expiration)
        quote = Mock()
        quote.delta = 0.0
        quote.gamma = 0.0
        quote.theta = 0.0
        quote.vega = 0.0
        quote.rho = 0.0
        quote.quote_date = datetime.now()

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_position_greeks("IWM240315C00190000")

        # Verify - All Greeks should be zero
        assert result["symbol"] == "IWM240315C00190000"
        assert result["position_greeks"]["delta"] == 0.0
        assert result["position_greeks"]["gamma"] == 0.0
        assert result["position_greeks"]["theta"] == 0.0
        assert result["position_greeks"]["vega"] == 0.0
        assert result["position_greeks"]["rho"] == 0.0

    async def test_get_position_greeks_partial_greeks(self, async_db_session):
        """Test Greeks calculation with some None values."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option position
        position = Position(
            symbol="GLD240315C00180000",
            quantity=8,
            avg_price=4.20,
            current_price=5.85,
            asset=Option(
                symbol="GLD240315C00180000",
                underlying=Stock(symbol="GLD"),
                option_type="call",
                strike=180.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote with partial Greeks (some None)
        quote = Mock()
        quote.delta = 0.7
        quote.gamma = None  # Missing gamma
        quote.theta = -0.18
        quote.vega = None  # Missing vega
        quote.rho = 0.15
        quote.quote_date = datetime.now()

        # Mock dependencies
        trading_service.get_position = AsyncMock(return_value=position)
        trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

        # Test
        result = await trading_service.get_position_greeks("GLD240315C00180000")

        # Verify - Available Greeks calculated, missing ones as 0.0 (None or 0.0 * multiplier = 0.0)
        assert result["symbol"] == "GLD240315C00180000"
        assert result["position_greeks"]["delta"] == 560.0  # 0.7 * 800
        assert result["position_greeks"]["gamma"] == 0.0  # None or 0.0 * 800 = 0.0
        assert result["position_greeks"]["theta"] == -144.0  # -0.18 * 800
        assert result["position_greeks"]["vega"] == 0.0  # None or 0.0 * 800 = 0.0
        assert result["position_greeks"]["rho"] == 120.0  # 0.15 * 800

    async def test_get_position_greeks_integration_with_database(
        self, async_db_session
    ):
        """Test Greeks calculation with database integration."""
        from app.models.assets import Option, Stock

        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option position
        position = Position(
            symbol="AMD240315C00120000",
            quantity=15,
            avg_price=6.80,
            current_price=9.15,
            asset=Option(
                symbol="AMD240315C00120000",
                underlying=Stock(symbol="AMD"),
                option_type="call",
                strike=120.0,
                expiration_date=date(2024, 3, 15),
            ),
        )

        # Mock quote with Greeks
        quote = Mock()
        quote.delta = 0.82
        quote.gamma = 0.015
        quote.theta = -0.28
        quote.vega = 0.31
        quote.rho = 0.19
        quote.quote_date = datetime.now()

        # Use real database session via proper mocking
        with patch("app.storage.database.get_async_session") as mock_get_session:

            async def mock_session_generator():
                yield async_db_session

            mock_get_session.side_effect = lambda: mock_session_generator()

            # Mock service methods
            trading_service.get_position = AsyncMock(return_value=position)
            trading_service.get_enhanced_quote = AsyncMock(return_value=quote)

            # Test
            result = await trading_service.get_position_greeks("AMD240315C00120000")

            # Verify - Greeks scaled by quantity * multiplier (15 * 100 = 1500)
            assert result["symbol"] == "AMD240315C00120000"
            assert result["position_greeks"]["delta"] == pytest.approx(
                1230.0
            )  # 0.82 * 1500
            assert result["position_greeks"]["gamma"] == pytest.approx(
                22.5
            )  # 0.015 * 1500
            assert result["position_greeks"]["theta"] == pytest.approx(
                -420.0
            )  # -0.28 * 1500
            assert result["position_greeks"]["vega"] == pytest.approx(
                465.0
            )  # 0.31 * 1500
            assert result["position_greeks"]["rho"] == pytest.approx(
                285.0
            )  # 0.19 * 1500
            assert "quote_time" in result  # Verify quote_date is included
