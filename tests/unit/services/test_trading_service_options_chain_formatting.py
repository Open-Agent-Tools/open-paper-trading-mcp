"""
Test Options Chain Formatting in TradingService.

Tests for get_formatted_options_chain() method covering lines 1030-1147.
Target: 10 comprehensive tests for options chain formatting with filtering.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.assets import Option, Stock
from app.models.quotes import OptionQuote, OptionsChain
from app.services.trading_service import TradingService


@pytest.mark.asyncio
class TestTradingServiceOptionsChainFormatting:
    """Test options chain formatting functionality."""

    async def test_get_formatted_options_chain_success(self, async_db_session):
        """Test successful options chain formatting with all data."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create call options
        call1 = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00145000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=145.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=8.50,
            bid=8.45,
            ask=8.55,
            volume=1250,
            delta=0.65,
            gamma=0.04,
            theta=-0.12,
            vega=0.28,
            rho=0.15,
            iv=0.35,
            quote_date=datetime.now(),
            open_interest=5420,
        )

        call2 = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=5.25,
            bid=5.20,
            ask=5.30,
            volume=2150,
            delta=0.45,
            gamma=0.06,
            theta=-0.18,
            vega=0.32,
            rho=0.12,
            iv=0.38,
            quote_date=datetime.now(),
            open_interest=8950,
        )

        # Create put options
        put1 = OptionQuote(
            asset=Option(
                symbol="AAPL240315P00145000",
                underlying=Stock(symbol="AAPL"),
                option_type="put",
                strike=145.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=3.75,
            bid=3.70,
            ask=3.80,
            volume=850,
            delta=-0.35,
            gamma=0.04,
            theta=-0.10,
            vega=0.28,
            rho=-0.08,
            iv=0.33,
            quote_date=datetime.now(),
            open_interest=3250,
        )

        put2 = OptionQuote(
            asset=Option(
                symbol="AAPL240315P00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="put",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=6.45,
            bid=6.40,
            ask=6.50,
            volume=1650,
            delta=-0.55,
            gamma=0.06,
            theta=-0.16,
            vega=0.32,
            rho=-0.12,
            iv=0.36,
            quote_date=datetime.now(),
            open_interest=7150,
        )

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="AAPL",
            underlying_price=147.50,
            expiration_date=date(2024, 3, 15),
            calls=[call1, call2],
            puts=[put1, put2],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test
        result = await trading_service.get_formatted_options_chain("AAPL")

        # Verify overall structure
        assert result["underlying_symbol"] == "AAPL"
        assert result["underlying_price"] == 147.50
        assert result["expiration_date"] == "2024-03-15"
        assert "quote_time" in result
        assert len(result["calls"]) == 2
        assert len(result["puts"]) == 2

        # Verify call formatting
        call_145 = next(c for c in result["calls"] if c["strike"] == 145.0)
        assert call_145["symbol"] == "AAPL240315C00145000"
        assert call_145["strike"] == 145.0
        assert call_145["bid"] == 8.45
        assert call_145["ask"] == 8.55
        assert call_145["mark"] == 8.50
        assert call_145["volume"] == 1250
        assert call_145["open_interest"] == 5420
        assert call_145["delta"] == 0.65
        assert call_145["gamma"] == 0.04
        assert call_145["theta"] == -0.12
        assert call_145["vega"] == 0.28
        assert call_145["rho"] == 0.15
        assert call_145["iv"] == 0.35

        # Verify put formatting
        put_150 = next(p for p in result["puts"] if p["strike"] == 150.0)
        assert put_150["symbol"] == "AAPL240315P00150000"
        assert put_150["strike"] == 150.0
        assert put_150["delta"] == -0.55  # Put delta is negative
        assert put_150["rho"] == -0.12  # Put rho is negative

    async def test_get_formatted_options_chain_no_greeks(self, async_db_session):
        """Test options chain formatting without Greeks."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create simple call option
        call = OptionQuote(
            asset=Option(
                symbol="TSLA240315C00200000",
                underlying=Stock(symbol="TSLA"),
                option_type="call",
                strike=200.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=12.50,
            bid=12.45,
            ask=12.55,
            volume=750,
            quote_date=datetime.now(),
            open_interest=2250,
        )

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="TSLA",
            underlying_price=205.75,
            expiration_date=date(2024, 3, 15),
            calls=[call],
            puts=[],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test with include_greeks=False
        result = await trading_service.get_formatted_options_chain(
            "TSLA", include_greeks=False
        )

        # Verify Greeks are not included
        call_data = result["calls"][0]
        assert call_data["symbol"] == "TSLA240315C00200000"
        assert call_data["strike"] == 200.0
        assert call_data["bid"] == 12.45
        assert call_data["ask"] == 12.55
        assert call_data["mark"] == 12.50
        assert call_data["volume"] == 750
        assert call_data["open_interest"] == 2250

        # Verify Greeks keys are not present
        assert "delta" not in call_data
        assert "gamma" not in call_data
        assert "theta" not in call_data
        assert "vega" not in call_data
        assert "rho" not in call_data
        assert "iv" not in call_data

    async def test_get_formatted_options_chain_strike_filtering(self, async_db_session):
        """Test options chain with strike price filtering."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create multiple strikes
        strikes = [140.0, 145.0, 150.0, 155.0, 160.0]
        calls = []
        puts = []

        for strike in strikes:
            call = OptionQuote(
                asset=Option(
                    symbol=f"SPY240315C{int(strike * 1000):08d}",
                    underlying=Stock(symbol="SPY"),
                    option_type="call",
                    strike=strike,
                    expiration_date=date(2024, 3, 15),
                ),
                price=strike * 0.05,  # Arbitrary pricing
                bid=strike * 0.049,
                ask=strike * 0.051,
                volume=100,
                quote_date=datetime.now(),
                open_interest=500,
            )
            calls.append(call)

            put = OptionQuote(
                asset=Option(
                    symbol=f"SPY240315P{int(strike * 1000):08d}",
                    underlying=Stock(symbol="SPY"),
                    option_type="put",
                    strike=strike,
                    expiration_date=date(2024, 3, 15),
                ),
                price=strike * 0.03,  # Arbitrary pricing
                bid=strike * 0.029,
                ask=strike * 0.031,
                volume=80,
                quote_date=datetime.now(),
                open_interest=300,
            )
            puts.append(put)

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="SPY",
            underlying_price=150.25,
            expiration_date=date(2024, 3, 15),
            calls=calls,
            puts=puts,
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test with strike filtering: min=145, max=155
        result = await trading_service.get_formatted_options_chain(
            "SPY", min_strike=145.0, max_strike=155.0, include_greeks=False
        )

        # Verify filtering worked
        assert len(result["calls"]) == 3  # 145, 150, 155
        assert len(result["puts"]) == 3  # 145, 150, 155

        # Verify strikes are within range
        call_strikes = [c["strike"] for c in result["calls"]]
        put_strikes = [p["strike"] for p in result["puts"]]

        assert sorted(call_strikes) == [145.0, 150.0, 155.0]
        assert sorted(put_strikes) == [145.0, 150.0, 155.0]

        # Verify 140 and 160 are filtered out
        assert 140.0 not in call_strikes
        assert 160.0 not in call_strikes

    async def test_get_formatted_options_chain_expiration_filtering(
        self, async_db_session
    ):
        """Test options chain with expiration date filtering."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option for specific expiration
        call = OptionQuote(
            asset=Option(
                symbol="QQQ240419C00380000",
                underlying=Stock(symbol="QQQ"),
                option_type="call",
                strike=380.0,
                expiration_date=date(2024, 4, 19),
            ),
            price=15.25,
            bid=15.20,
            ask=15.30,
            volume=1850,
            delta=0.72,
            quote_date=datetime.now(),
            open_interest=4250,
        )

        # Create options chain with specific expiration
        chain = OptionsChain(
            underlying_symbol="QQQ",
            underlying_price=385.50,
            expiration_date=date(2024, 4, 19),
            calls=[call],
            puts=[],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test with expiration date filtering
        result = await trading_service.get_formatted_options_chain(
            "QQQ", expiration_date=date(2024, 4, 19)
        )

        # Verify expiration date is properly formatted
        assert result["expiration_date"] == "2024-04-19"
        assert len(result["calls"]) == 1
        assert result["calls"][0]["symbol"] == "QQQ240419C00380000"

    async def test_get_formatted_options_chain_missing_attributes(
        self, async_db_session
    ):
        """Test options chain formatting with missing optional attributes."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create option with minimal data
        call = OptionQuote(
            asset=Option(
                symbol="IWM240315C00190000",
                underlying=Stock(symbol="IWM"),
                option_type="call",
                strike=190.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=4.50,
            bid=4.45,
            ask=4.55,
            quote_date=datetime.now(),
            # Missing: volume, open_interest, Greeks
        )

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="IWM",
            underlying_price=192.75,
            expiration_date=date(2024, 3, 15),
            calls=[call],
            puts=[],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test
        result = await trading_service.get_formatted_options_chain("IWM")

        # Verify missing attributes are handled gracefully
        call_data = result["calls"][0]
        assert call_data["symbol"] == "IWM240315C00190000"
        assert call_data["strike"] == 190.0
        assert call_data["mark"] == 4.50
        assert call_data["volume"] is None  # Missing attribute
        assert call_data["open_interest"] is None  # Missing attribute
        assert call_data["delta"] is None  # Missing Greeks
        assert call_data["gamma"] is None
        assert call_data["theta"] is None
        assert call_data["vega"] is None
        assert call_data["rho"] is None
        assert call_data["iv"] is None

    async def test_get_formatted_options_chain_empty_chain(self, async_db_session):
        """Test options chain formatting with empty chain."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create empty options chain
        chain = OptionsChain(
            underlying_symbol="GLD",
            underlying_price=185.25,
            expiration_date=date(2024, 3, 15),
            calls=[],
            puts=[],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test
        result = await trading_service.get_formatted_options_chain("GLD")

        # Verify empty chain handling
        assert result["underlying_symbol"] == "GLD"
        assert result["underlying_price"] == 185.25
        assert result["expiration_date"] == "2024-03-15"
        assert result["calls"] == []
        assert result["puts"] == []

    async def test_get_formatted_options_chain_complex_scenario(self, async_db_session):
        """Test options chain formatting with complex real-world scenario."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create multiple options with various characteristics
        call1 = OptionQuote(
            asset=Option(
                symbol="NVDA240315C00800000",
                underlying=Stock(symbol="NVDA"),
                option_type="call",
                strike=800.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=25.50,
            bid=25.45,
            ask=25.55,
            volume=3500,
            delta=0.68,
            gamma=0.005,
            theta=-0.45,
            vega=1.25,
            rho=0.85,
            iv=0.42,
            quote_date=datetime.now(),
            open_interest=12750,
        )

        call2 = OptionQuote(
            asset=Option(
                symbol="NVDA240315C00850000",
                underlying=Stock(symbol="NVDA"),
                option_type="call",
                strike=850.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=15.25,
            bid=15.20,
            ask=15.30,
            volume=2200,
            delta=0.42,
            gamma=0.008,
            theta=-0.52,
            vega=1.35,
            rho=0.58,
            iv=0.45,
            quote_date=datetime.now(),
            open_interest=8950,
        )

        put1 = OptionQuote(
            asset=Option(
                symbol="NVDA240315P00750000",
                underlying=Stock(symbol="NVDA"),
                option_type="put",
                strike=750.0,
                expiration_date=date(2024, 3, 15),
            ),
            price=18.75,
            bid=18.70,
            ask=18.80,
            volume=1850,
            delta=-0.38,
            gamma=0.006,
            theta=-0.38,
            vega=1.15,
            rho=-0.45,
            iv=0.40,
            quote_date=datetime.now(),
            open_interest=6750,
        )

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="NVDA",
            underlying_price=825.75,
            expiration_date=date(2024, 3, 15),
            calls=[call1, call2],
            puts=[put1],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test with strike filtering (only include strikes between 750-825)
        result = await trading_service.get_formatted_options_chain(
            "NVDA", min_strike=750.0, max_strike=825.0
        )

        # Verify filtering and formatting
        assert result["underlying_symbol"] == "NVDA"
        assert result["underlying_price"] == 825.75
        assert len(result["calls"]) == 1  # Only 800 strike (850 filtered out)
        assert len(result["puts"]) == 1  # 750 strike included

        # Verify detailed call data
        call_data = result["calls"][0]
        assert call_data["symbol"] == "NVDA240315C00800000"
        assert call_data["strike"] == 800.0
        assert call_data["mark"] == 25.50
        assert call_data["volume"] == 3500
        assert call_data["delta"] == 0.68
        assert call_data["iv"] == 0.42

        # Verify detailed put data
        put_data = result["puts"][0]
        assert put_data["symbol"] == "NVDA240315P00750000"
        assert put_data["strike"] == 750.0
        assert put_data["delta"] == -0.38  # Negative for puts
        assert put_data["rho"] == -0.45  # Negative for puts

    async def test_get_formatted_options_chain_min_strike_only(self, async_db_session):
        """Test options chain with only minimum strike filtering."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create options with different strikes
        strikes = [100.0, 110.0, 120.0, 130.0]
        calls = []

        for strike in strikes:
            call = OptionQuote(
                asset=Option(
                    symbol=f"TLT240315C{int(strike * 1000):08d}",
                    underlying=Stock(symbol="TLT"),
                    option_type="call",
                    strike=strike,
                    expiration_date=date(2024, 3, 15),
                ),
                price=strike * 0.04,
                bid=strike * 0.039,
                ask=strike * 0.041,
                quote_date=datetime.now(),
            )
            calls.append(call)

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="TLT",
            underlying_price=115.50,
            expiration_date=date(2024, 3, 15),
            calls=calls,
            puts=[],
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test with only min_strike=115
        result = await trading_service.get_formatted_options_chain(
            "TLT", min_strike=115.0, include_greeks=False
        )

        # Verify only strikes >= 115 are included
        call_strikes = [c["strike"] for c in result["calls"]]
        assert sorted(call_strikes) == [120.0, 130.0]
        assert 100.0 not in call_strikes
        assert 110.0 not in call_strikes

    async def test_get_formatted_options_chain_max_strike_only(self, async_db_session):
        """Test options chain with only maximum strike filtering."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Create puts with different strikes
        strikes = [40.0, 50.0, 60.0, 70.0]
        puts = []

        for strike in strikes:
            put = OptionQuote(
                asset=Option(
                    symbol=f"VXX240315P{int(strike * 1000):08d}",
                    underlying=Stock(symbol="VXX"),
                    option_type="put",
                    strike=strike,
                    expiration_date=date(2024, 3, 15),
                ),
                price=strike * 0.08,
                bid=strike * 0.079,
                ask=strike * 0.081,
                delta=-0.3,  # Put delta
                quote_date=datetime.now(),
            )
            puts.append(put)

        # Create options chain
        chain = OptionsChain(
            underlying_symbol="VXX",
            underlying_price=55.25,
            expiration_date=date(2024, 3, 15),
            calls=[],
            puts=puts,
        )

        # Mock dependencies
        trading_service.get_options_chain = AsyncMock(return_value=chain)

        # Test with only max_strike=55
        result = await trading_service.get_formatted_options_chain(
            "VXX", max_strike=55.0
        )

        # Verify only strikes <= 55 are included
        put_strikes = [p["strike"] for p in result["puts"]]
        assert sorted(put_strikes) == [40.0, 50.0]
        assert 60.0 not in put_strikes
        assert 70.0 not in put_strikes

    async def test_get_formatted_options_chain_exception_handling(
        self, async_db_session
    ):
        """Test error handling in options chain formatting."""
        # Create TradingService with mock adapter
        mock_quote_adapter = AsyncMock()
        trading_service = TradingService(quote_adapter=mock_quote_adapter)

        # Mock get_options_chain to raise exception
        trading_service.get_options_chain = AsyncMock(
            side_effect=Exception("Chain not available")
        )

        # Test
        result = await trading_service.get_formatted_options_chain("INVALID")

        # Verify error response
        assert "error" in result
        assert "Chain not available" in result["error"]
