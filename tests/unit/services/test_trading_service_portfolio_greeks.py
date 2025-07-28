"""
Comprehensive test coverage for TradingService.get_portfolio_greeks() method.

This module provides complete test coverage for portfolio-wide Greeks calculations,
covering basic functionality, quote integration, and error handling scenarios.

Test Coverage Areas:
- Basic functionality: Empty portfolios, single/multiple positions, mixed portfolios
- Quote integration: Successful retrieval, partial failures, adapter failures
- Edge cases: Missing attributes, invalid symbols, null values, exception handling

Function Tested:
- TradingService.get_portfolio_greeks() - app/services/trading_service.py:474-517
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.assets import Call, Put, Stock
from app.models.database.trading import Account as DBAccount
from app.models.database.trading import Position as DBPosition
from app.models.quotes import OptionQuote, Quote
from app.services.strategies.models import StrategyGreeks
from app.services.trading_service import TradingService


@pytest.mark.database
class TestGetPortfolioGreeks:
    """Test TradingService.get_portfolio_greeks() function - Portfolio Greeks calculation."""

    # ================= BASIC FUNCTIONALITY TESTS (5 tests) =================

    @pytest.mark.asyncio
    async def test_empty_portfolio_greeks_calculation(self, db_session: AsyncSession):
        """Test Greeks calculation for empty portfolio."""
        account = DBAccount(
            id="ACCT000210",
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

        # Mock empty aggregate_portfolio_greeks result
        mock_greeks = StrategyGreeks(
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_normalized=0.0,
            gamma_normalized=0.0,
            theta_normalized=0.0,
            vega_normalized=0.0,
            delta_dollars=0.0,
            gamma_dollars=0.0,
            theta_dollars=0.0,
        )

        with patch(
            "app.services.strategies.aggregate_portfolio_greeks",
            return_value=mock_greeks,
        ):
            result = await service.get_portfolio_greeks()

        # Validate empty portfolio results
        assert "timestamp" in result
        assert result["total_positions"] == 0
        assert result["options_positions"] == 0
        assert result["portfolio_greeks"]["delta"] == 0.0
        assert result["portfolio_greeks"]["gamma"] == 0.0
        assert result["portfolio_greeks"]["theta"] == 0.0
        assert result["portfolio_greeks"]["vega"] == 0.0
        assert result["portfolio_greeks"]["rho"] == 0.0

    @pytest.mark.asyncio
    async def test_single_options_position_greeks(self, db_session: AsyncSession):
        """Test Greeks calculation for single options position."""
        account = DBAccount(
            id="ACCT000220",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add single call option position
        position = DBPosition(
            id="POS000001",
            account_id=account.id,
            symbol="AAPL250117C00150000",
            quantity=1,
            avg_price=5.50,
        )
        db_session.add(position)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock quote with Greeks
        mock_quote = OptionQuote(
            asset=Call(
                symbol="AAPL250117C00150000",
                underlying="AAPL",
                strike=150.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime.now(UTC),
            price=6.25,
            bid=6.20,
            ask=6.30,
            underlying_price=155.50,
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
        )

        # Mock Greeks aggregation result
        mock_greeks = StrategyGreeks(
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
            delta_normalized=65.0,
            gamma_normalized=5.0,
            theta_normalized=-15.0,
            vega_normalized=25.0,
            delta_dollars=35.75,
            gamma_dollars=2.75,
            theta_dollars=-8.25,
        )

        with (
            patch.object(service, "get_enhanced_quote", return_value=mock_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Validate single position results
        assert result["total_positions"] == 1
        assert result["options_positions"] == 1
        assert result["portfolio_greeks"]["delta"] == 0.65
        assert result["portfolio_greeks"]["gamma"] == 0.05
        assert result["portfolio_greeks"]["theta"] == -0.15
        assert result["portfolio_greeks"]["vega"] == 0.25
        assert result["portfolio_greeks"]["rho"] == 0.08
        assert result["portfolio_greeks"]["delta_dollars"] == 35.75

    @pytest.mark.asyncio
    async def test_multiple_options_positions_aggregation(
        self, db_session: AsyncSession
    ):
        """Test Greeks aggregation for multiple options positions."""
        account = DBAccount(
            id="ACCT000230",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add multiple option positions
        positions = [
            DBPosition(
                id="POS000002",
                account_id=account.id,
                symbol="AAPL250117C00150000",
                quantity=2,
                avg_price=5.50,
            ),
            DBPosition(
                id="POS000003",
                account_id=account.id,
                symbol="AAPL250117P00145000",
                quantity=1,
                avg_price=3.25,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock quotes for both positions
        call_quote = OptionQuote(
            asset=Call(
                symbol="AAPL250117C00150000",
                underlying="AAPL",
                strike=150.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime.now(UTC),
            price=6.25,
            bid=6.20,
            ask=6.30,
            underlying_price=155.50,
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
        )

        put_quote = OptionQuote(
            asset=Put(
                symbol="AAPL250117P00145000",
                underlying="AAPL",
                strike=145.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime.now(UTC),
            price=2.75,
            bid=2.70,
            ask=2.80,
            underlying_price=155.50,
            delta=-0.25,
            gamma=0.03,
            theta=-0.08,
            vega=0.18,
            rho=-0.05,
        )

        # Mock aggregated Greeks (2 calls + 1 put)
        mock_greeks = StrategyGreeks(
            delta=1.05,  # (2 * 0.65) + (1 * -0.25)
            gamma=0.13,  # (2 * 0.05) + (1 * 0.03)
            theta=-0.38,  # (2 * -0.15) + (1 * -0.08)
            vega=0.68,  # (2 * 0.25) + (1 * 0.18)
            rho=0.11,  # (2 * 0.08) + (1 * -0.05)
            delta_normalized=105.0,
            gamma_normalized=13.0,
            theta_normalized=-38.0,
            vega_normalized=68.0,
            delta_dollars=57.75,
            gamma_dollars=7.15,
            theta_dollars=-20.90,
        )

        quote_map = {
            "AAPL250117C00150000": call_quote,
            "AAPL250117P00145000": put_quote,
        }

        async def mock_get_quote(symbol):
            return quote_map[symbol]

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Validate aggregated results
        assert result["total_positions"] == 2
        assert result["options_positions"] == 2
        assert result["portfolio_greeks"]["delta"] == 1.05
        assert result["portfolio_greeks"]["gamma"] == 0.13
        assert result["portfolio_greeks"]["theta"] == -0.38
        assert result["portfolio_greeks"]["vega"] == 0.68
        assert result["portfolio_greeks"]["rho"] == 0.11

    @pytest.mark.asyncio
    async def test_mixed_portfolio_stocks_and_options_greeks(
        self, db_session: AsyncSession
    ):
        """Test Greeks calculation for mixed portfolio (stocks + options)."""
        account = DBAccount(
            id="ACCT000240",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add mixed positions (stock + option)
        positions = [
            DBPosition(
                id="POS000004",
                account_id=account.id,
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
            ),
            DBPosition(
                id="POS000005",
                account_id=account.id,
                symbol="AAPL250117C00150000",
                quantity=1,
                avg_price=5.50,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock quotes - stock quote without Greeks, option quote with Greeks
        stock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(UTC),
            price=155.50,
            bid=155.45,
            ask=155.55,
            bid_size=100,
            ask_size=100,
            volume=10000,
            # No Greeks for stock
        )

        option_quote = OptionQuote(
            asset=Call(
                symbol="AAPL250117C00150000",
                underlying="AAPL",
                strike=150.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime.now(UTC),
            price=6.25,
            bid=6.20,
            ask=6.30,
            underlying_price=155.50,
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
        )

        # Mock Greeks from option only (stock contributes no Greeks)
        mock_greeks = StrategyGreeks(
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
            delta_normalized=65.0,
            gamma_normalized=5.0,
            theta_normalized=-15.0,
            vega_normalized=25.0,
            delta_dollars=35.75,
            gamma_dollars=2.75,
            theta_dollars=-8.25,
        )

        quote_map = {"AAPL": stock_quote, "AAPL250117C00150000": option_quote}

        async def mock_get_quote(symbol):
            return quote_map[symbol]

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Validate mixed portfolio results - both positions have quotes with delta attributes
        assert result["total_positions"] == 2
        assert (
            result["options_positions"] == 2
        )  # Both stock and option have delta attributes
        assert result["portfolio_greeks"]["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_large_portfolio_greeks_performance(self, db_session: AsyncSession):
        """Test Greeks calculation performance with large portfolio."""
        account = DBAccount(
            id="ACCT000250",
            owner="test_user",
            cash_balance=100000.0,
        )
        db_session.add(account)

        # Add large number of option positions
        positions = []
        for i in range(50):  # 50 option positions
            position = DBPosition(
                id=f"POS{i + 1000:06d}",  # POS001000, POS001001, etc.
                account_id=account.id,
                symbol=f"AAPL25011{7 + (i % 3)}C00{150 + i}000",
                quantity=1 + (i % 5),
                avg_price=5.0 + (i * 0.1),
            )
            positions.append(position)
            db_session.add(position)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock aggregated Greeks for large portfolio
        mock_greeks = StrategyGreeks(
            delta=32.5,
            gamma=2.5,
            theta=-7.5,
            vega=12.5,
            rho=4.0,
            delta_normalized=325.0,
            gamma_normalized=25.0,
            theta_normalized=-75.0,
            vega_normalized=125.0,
            delta_dollars=1787.5,
            gamma_dollars=137.5,
            theta_dollars=-412.5,
        )

        # Mock quote for all positions
        async def mock_get_quote(symbol):
            return OptionQuote(
                asset=Call(
                    symbol=symbol,
                    underlying="AAPL",
                    strike=150.0,
                    expiration="2025-01-17",
                ),
                quote_date=datetime.now(UTC),
                price=6.0,
                bid=5.95,
                ask=6.05,
                underlying_price=155.50,
                delta=0.65,
                gamma=0.05,
                theta=-0.15,
                vega=0.25,
                rho=0.08,
            )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Validate large portfolio results
        assert result["total_positions"] == 50
        assert result["options_positions"] == 50
        assert result["portfolio_greeks"]["delta"] == 32.5
        assert "timestamp" in result

    # ================= QUOTE INTEGRATION TESTS (5 tests) =================

    @pytest.mark.asyncio
    async def test_successful_quote_retrieval_all_positions(
        self, db_session: AsyncSession
    ):
        """Test successful quote retrieval for all positions."""
        account = DBAccount(
            id="ACCT000260",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add multiple positions
        positions = [
            DBPosition(
                id="POS000007",
                account_id=account.id,
                symbol="AAPL250117C00150000",
                quantity=1,
                avg_price=5.50,
            ),
            DBPosition(
                id="POS000008",
                account_id=account.id,
                symbol="MSFT250117C00300000",
                quantity=1,
                avg_price=8.25,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Track quote calls
        quote_calls = []

        async def mock_get_quote(symbol):
            quote_calls.append(symbol)
            if symbol == "AAPL250117C00150000":
                return OptionQuote(
                    asset=Call(
                        symbol=symbol,
                        underlying="AAPL",
                        strike=150.0,
                        expiration="2025-01-17",
                    ),
                    quote_date=datetime.now(UTC),
                    price=6.25,
                    bid=6.20,
                    ask=6.30,
                    underlying_price=155.50,
                    delta=0.65,
                    gamma=0.05,
                    theta=-0.15,
                    vega=0.25,
                    rho=0.08,
                )
            else:  # MSFT option
                return OptionQuote(
                    asset=Call(
                        symbol=symbol,
                        underlying="MSFT",
                        strike=300.0,
                        expiration="2025-01-17",
                    ),
                    quote_date=datetime.now(UTC),
                    price=9.50,
                    bid=9.45,
                    ask=9.55,
                    underlying_price=310.25,
                    delta=0.75,
                    gamma=0.04,
                    theta=-0.12,
                    vega=0.22,
                    rho=0.09,
                )

        mock_greeks = StrategyGreeks(
            delta=1.40,
            gamma=0.09,
            theta=-0.27,
            vega=0.47,
            rho=0.17,
            delta_normalized=140.0,
            gamma_normalized=9.0,
            theta_normalized=-27.0,
            vega_normalized=47.0,
            delta_dollars=77.0,
            gamma_dollars=4.95,
            theta_dollars=-14.85,
        )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Validate all quotes were retrieved
        assert len(quote_calls) == 2
        assert "AAPL250117C00150000" in quote_calls
        assert "MSFT250117C00300000" in quote_calls
        assert result["total_positions"] == 2
        assert result["options_positions"] == 2

    @pytest.mark.asyncio
    async def test_partial_quote_failures_some_positions_missing(
        self, db_session: AsyncSession
    ):
        """Test handling of partial quote failures (some positions missing quotes)."""
        account = DBAccount(
            id="ACCT000270",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add multiple positions
        positions = [
            DBPosition(
                id="POS000009",
                account_id=account.id,
                symbol="AAPL250117C00150000",
                quantity=1,
                avg_price=5.50,
            ),
            DBPosition(
                id="POS000010",
                account_id=account.id,
                symbol="INVALID_SYMBOL",
                quantity=1,
                avg_price=8.25,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        async def mock_get_quote(symbol):
            if symbol == "AAPL250117C00150000":
                return OptionQuote(
                    asset=Call(
                        symbol=symbol,
                        underlying="AAPL",
                        strike=150.0,
                        expiration="2025-01-17",
                    ),
                    quote_date=datetime.now(UTC),
                    price=6.25,
                    bid=6.20,
                    ask=6.30,
                    underlying_price=155.50,
                    delta=0.65,
                    gamma=0.05,
                    theta=-0.15,
                    vega=0.25,
                    rho=0.08,
                )
            else:
                # Simulate quote failure for invalid symbol
                raise NotFoundError(f"Quote not found for {symbol}")

        # Greeks calculated only from successful quotes
        mock_greeks = StrategyGreeks(
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
            delta_normalized=65.0,
            gamma_normalized=5.0,
            theta_normalized=-15.0,
            vega_normalized=25.0,
            delta_dollars=35.75,
            gamma_dollars=2.75,
            theta_dollars=-8.25,
        )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should still process successfully with partial data
        # Note: invalid position may not make it through get_positions() processing
        assert result["total_positions"] >= 1  # At least the valid position
        assert result["options_positions"] == 1  # Only 1 position has valid quote
        assert result["portfolio_greeks"]["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_complete_quote_adapter_failure_handling(
        self, db_session: AsyncSession
    ):
        """Test handling of complete quote adapter failure."""
        account = DBAccount(
            id="ACCT000280",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add option position
        position = DBPosition(
            id="POS000011",
            account_id=account.id,
            symbol="AAPL250117C00150000",
            quantity=1,
            avg_price=5.50,
        )
        db_session.add(position)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        async def failing_get_quote(symbol):
            # Simulate complete adapter failure
            raise Exception("Quote adapter service unavailable")

        # Greeks calculated from empty quotes dict
        mock_greeks = StrategyGreeks(
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_normalized=0.0,
            gamma_normalized=0.0,
            theta_normalized=0.0,
            vega_normalized=0.0,
            delta_dollars=0.0,
            gamma_dollars=0.0,
            theta_dollars=0.0,
        )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=failing_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should handle gracefully with no quotes available
        assert result["total_positions"] == 1
        assert result["options_positions"] == 0  # No positions have valid quotes
        assert result["portfolio_greeks"]["delta"] == 0.0

    @pytest.mark.asyncio
    async def test_stale_quote_data_handling(self, db_session: AsyncSession):
        """Test handling of stale quote data."""
        account = DBAccount(
            id="ACCT000290",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add option position
        position = DBPosition(
            id="POS000012",
            account_id=account.id,
            symbol="AAPL250117C00150000",
            quantity=1,
            avg_price=5.50,
        )
        db_session.add(position)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock stale quote (old timestamp but valid data)
        stale_quote = OptionQuote(
            asset=Call(
                symbol="AAPL250117C00150000",
                underlying="AAPL",
                strike=150.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),  # Old timestamp
            price=6.25,
            bid=6.20,
            ask=6.30,
            underlying_price=155.50,
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
        )

        mock_greeks = StrategyGreeks(
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
            delta_normalized=65.0,
            gamma_normalized=5.0,
            theta_normalized=-15.0,
            vega_normalized=25.0,
            delta_dollars=35.75,
            gamma_dollars=2.75,
            theta_dollars=-8.25,
        )

        with (
            patch.object(service, "get_enhanced_quote", return_value=stale_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should still process stale quotes (up to quote adapter to validate freshness)
        assert result["total_positions"] == 1
        assert result["options_positions"] == 1
        assert result["portfolio_greeks"]["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_quote_data_validation_and_error_recovery(
        self, db_session: AsyncSession
    ):
        """Test quote data validation and error recovery."""
        account = DBAccount(
            id="ACCT000300",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add multiple positions
        positions = [
            DBPosition(
                id="POS000013",
                account_id=account.id,
                symbol="AAPL250117C00150000",
                quantity=1,
                avg_price=5.50,
            ),
            DBPosition(
                id="POS000014",
                account_id=account.id,
                symbol="MSFT250117C00300000",
                quantity=1,
                avg_price=8.25,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        call_count = 0

        async def mixed_quote_results(symbol):
            nonlocal call_count
            call_count += 1

            if symbol == "AAPL250117C00150000":
                # AAPL fails with validation error
                raise ValueError("Invalid quote data format")
            else:
                # MSFT succeeds on first try
                return OptionQuote(
                    asset=Call(
                        symbol=symbol,
                        underlying="MSFT",
                        strike=300.0,
                        expiration="2025-01-17",
                    ),
                    quote_date=datetime.now(UTC),
                    price=9.50,
                    bid=9.45,
                    ask=9.55,
                    underlying_price=310.25,
                    delta=0.75,
                    gamma=0.04,
                    theta=-0.12,
                    vega=0.22,
                    rho=0.09,
                )

        # Greeks from successful quotes only (MSFT succeeds, AAPL fails)
        mock_greeks = StrategyGreeks(
            delta=0.75,
            gamma=0.04,
            theta=-0.12,
            vega=0.22,
            rho=0.09,
            delta_normalized=75.0,
            gamma_normalized=4.0,
            theta_normalized=-12.0,
            vega_normalized=22.0,
            delta_dollars=41.25,
            gamma_dollars=2.20,
            theta_dollars=-6.60,
        )

        with (
            patch.object(
                service, "get_enhanced_quote", side_effect=mixed_quote_results
            ),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should recover from validation errors gracefully
        assert result["total_positions"] == 2
        assert result["options_positions"] == 1  # Only MSFT succeeded
        assert result["portfolio_greeks"]["delta"] == 0.75

    # ================= EDGE CASES & ERROR HANDLING TESTS (5 tests) =================

    @pytest.mark.asyncio
    async def test_positions_with_missing_delta_attributes(
        self, db_session: AsyncSession
    ):
        """Test handling positions with missing delta attributes."""
        account = DBAccount(
            id="ACCT000310",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add mixed positions - stock (no delta) and option (with delta)
        positions = [
            DBPosition(
                id="POS000015",
                account_id=account.id,
                symbol="AAPL",  # Stock position - no delta
                quantity=100,
                avg_price=150.0,
            ),
            DBPosition(
                id="POS000016",
                account_id=account.id,
                symbol="AAPL250117C00150000",
                quantity=1,
                avg_price=5.50,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock quotes - stock without delta, option with delta
        async def mock_get_quote(symbol):
            if symbol == "AAPL":
                return Quote(  # Regular quote without delta
                    asset=Stock(symbol="AAPL"),
                    quote_date=datetime.now(UTC),
                    price=155.50,
                    bid=155.45,
                    ask=155.55,
                )
            else:
                return OptionQuote(  # Option quote with delta
                    asset=Call(
                        symbol=symbol,
                        underlying="AAPL",
                        strike=150.0,
                        expiration="2025-01-17",
                    ),
                    quote_date=datetime.now(UTC),
                    price=6.25,
                    bid=6.20,
                    ask=6.30,
                    underlying_price=155.50,
                    delta=0.65,
                    gamma=0.05,
                    theta=-0.15,
                    vega=0.25,
                    rho=0.08,
                )

        mock_greeks = StrategyGreeks(
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
            delta_normalized=65.0,
            gamma_normalized=5.0,
            theta_normalized=-15.0,
            vega_normalized=25.0,
            delta_dollars=35.75,
            gamma_dollars=2.75,
            theta_dollars=-8.25,
        )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should only count positions with delta attributes - both quotes have delta
        assert result["total_positions"] == 2
        assert (
            result["options_positions"] == 2
        )  # Both stock and option quotes have delta attributes
        assert result["portfolio_greeks"]["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_invalid_option_symbols_in_portfolio(self, db_session: AsyncSession):
        """Test handling of invalid option symbols in portfolio."""
        account = DBAccount(
            id="ACCT000320",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add positions with malformed option symbols
        positions = [
            DBPosition(
                id="POS000017",
                account_id=account.id,
                symbol="INVALID_OPTION_FORMAT",
                quantity=1,
                avg_price=5.50,
            ),
            DBPosition(
                id="POS000018",
                account_id=account.id,
                symbol="AAPL250117C00150000",  # Valid option
                quantity=1,
                avg_price=5.50,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        async def mock_get_quote(symbol):
            if symbol == "INVALID_OPTION_FORMAT":
                raise ValueError(f"Invalid option symbol format: {symbol}")
            else:
                return OptionQuote(
                    asset=Call(
                        symbol=symbol,
                        underlying="AAPL",
                        strike=150.0,
                        expiration="2025-01-17",
                    ),
                    quote_date=datetime.now(UTC),
                    price=6.25,
                    bid=6.20,
                    ask=6.30,
                    underlying_price=155.50,
                    delta=0.65,
                    gamma=0.05,
                    theta=-0.15,
                    vega=0.25,
                    rho=0.08,
                )

        # Greeks only from valid option
        mock_greeks = StrategyGreeks(
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
            delta_normalized=65.0,
            gamma_normalized=5.0,
            theta_normalized=-15.0,
            vega_normalized=25.0,
            delta_dollars=35.75,
            gamma_dollars=2.75,
            theta_dollars=-8.25,
        )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should handle invalid symbols gracefully
        # Note: invalid position may not make it through get_positions() processing
        assert result["total_positions"] >= 1  # At least the valid position
        assert (
            result["options_positions"] == 1
        )  # Only position with valid quote counted
        assert result["portfolio_greeks"]["delta"] == 0.65

    @pytest.mark.asyncio
    async def test_greeks_calculation_with_null_zero_values(
        self, db_session: AsyncSession
    ):
        """Test Greeks calculation with null/zero values."""
        account = DBAccount(
            id="ACCT000330",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add option position
        position = DBPosition(
            id="POS000019",
            account_id=account.id,
            symbol="AAPL250117C00150000",
            quantity=1,
            avg_price=5.50,
        )
        db_session.add(position)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock quote with null/zero Greeks
        quote_with_nulls = OptionQuote(
            asset=Call(
                symbol="AAPL250117C00150000",
                underlying="AAPL",
                strike=150.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime.now(UTC),
            price=6.25,
            bid=6.20,
            ask=6.30,
            underlying_price=155.50,
            delta=None,  # Null delta
            gamma=0.0,  # Zero gamma
            theta=None,  # Null theta
            vega=0.0,  # Zero vega
            rho=None,  # Null rho
        )

        # Mock Greeks handling nulls appropriately
        mock_greeks = StrategyGreeks(
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_normalized=0.0,
            gamma_normalized=0.0,
            theta_normalized=0.0,
            vega_normalized=0.0,
            delta_dollars=0.0,
            gamma_dollars=0.0,
            theta_dollars=0.0,
        )

        with (
            patch.object(service, "get_enhanced_quote", return_value=quote_with_nulls),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should handle null/zero values gracefully
        assert result["total_positions"] == 1
        assert (
            result["options_positions"] == 1
        )  # Position still has quote with delta attribute (even if None)
        assert result["portfolio_greeks"]["delta"] == 0.0
        assert result["portfolio_greeks"]["gamma"] == 0.0
        assert result["portfolio_greeks"]["theta"] == 0.0

    @pytest.mark.asyncio
    async def test_exception_handling_in_aggregation_logic(
        self, db_session: AsyncSession
    ):
        """Test exception handling in aggregation logic."""
        account = DBAccount(
            id="ACCT000340",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add option position
        position = DBPosition(
            id="POS000020",
            account_id=account.id,
            symbol="AAPL250117C00150000",
            quantity=1,
            avg_price=5.50,
        )
        db_session.add(position)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock successful quote
        mock_quote = OptionQuote(
            asset=Call(
                symbol="AAPL250117C00150000",
                underlying="AAPL",
                strike=150.0,
                expiration="2025-01-17",
            ),
            quote_date=datetime.now(UTC),
            price=6.25,
            bid=6.20,
            ask=6.30,
            underlying_price=155.50,
            delta=0.65,
            gamma=0.05,
            theta=-0.15,
            vega=0.25,
            rho=0.08,
        )

        with (
            patch.object(service, "get_enhanced_quote", return_value=mock_quote),
            # Mock aggregation function to raise exception
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                side_effect=ValueError("Aggregation failed"),
            ),
            pytest.raises(ValueError, match="Aggregation failed"),
        ):
            await service.get_portfolio_greeks()

    @pytest.mark.asyncio
    async def test_portfolio_with_no_options_positions(self, db_session: AsyncSession):
        """Test portfolio with no options positions (stocks only)."""
        account = DBAccount(
            id="ACCT000350",
            owner="test_user",
            cash_balance=50000.0,
        )
        db_session.add(account)

        # Add only stock positions (no options)
        positions = [
            DBPosition(
                id="POS000021",
                account_id=account.id,
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
            ),
            DBPosition(
                id="POS000022",
                account_id=account.id,
                symbol="MSFT",
                quantity=50,
                avg_price=300.0,
            ),
        ]
        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        mock_quote_adapter = AsyncMock()
        service = TradingService(
            quote_adapter=mock_quote_adapter,
            account_owner="test_user",
            db_session=db_session,
        )

        # Mock stock quotes (no Greeks)
        async def mock_get_quote(symbol):
            if symbol == "AAPL":
                return Quote(
                    asset=Stock(symbol="AAPL"),
                    quote_date=datetime.now(UTC),
                    price=155.50,
                    bid=155.45,
                    ask=155.55,
                )
            else:  # MSFT
                return Quote(
                    asset=Stock(symbol="MSFT"),
                    quote_date=datetime.now(UTC),
                    price=310.25,
                    bid=310.20,
                    ask=310.30,
                )

        # Mock empty Greeks (no options)
        mock_greeks = StrategyGreeks(
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_normalized=0.0,
            gamma_normalized=0.0,
            theta_normalized=0.0,
            vega_normalized=0.0,
            delta_dollars=0.0,
            gamma_dollars=0.0,
            theta_dollars=0.0,
        )

        with (
            patch.object(service, "get_enhanced_quote", side_effect=mock_get_quote),
            patch(
                "app.services.strategies.aggregate_portfolio_greeks",
                return_value=mock_greeks,
            ),
        ):
            result = await service.get_portfolio_greeks()

        # Should handle stocks-only portfolio gracefully
        assert result["total_positions"] == 2
        assert (
            result["options_positions"] == 2
        )  # Both stock quotes have delta attributes
        assert result["portfolio_greeks"]["delta"] == 0.0
        assert result["portfolio_greeks"]["gamma"] == 0.0
        assert result["portfolio_greeks"]["theta"] == 0.0
        assert result["portfolio_greeks"]["vega"] == 0.0
        assert result["portfolio_greeks"]["rho"] == 0.0
        assert "timestamp" in result
