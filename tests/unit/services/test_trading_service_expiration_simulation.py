"""
Tests for TradingService options expiration simulation functionality.

This module covers the simulate_expiration method (lines 1208-1373) which provides:
- Options expiration processing and simulation
- Intrinsic value calculations for calls and puts
- Portfolio impact analysis for expiring positions
- Dry run vs live processing modes
- Error handling for position parsing and quote retrieval

Coverage target: Lines 1208-1373 (simulate_expiration method + related logic)
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.assets import Option, Stock
from app.models.quotes import OptionQuote, Quote
from app.schemas.positions import Portfolio, Position


class TestTradingServiceExpirationSimulation:
    """Test options expiration simulation functionality."""

    @pytest.mark.asyncio
    async def test_simulate_expiration_basic_success_dry_run(
        self, trading_service_synthetic_data
    ):
        """Test basic successful expiration simulation in dry run mode."""
        # Mock portfolio with expiring option
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="AAPL240315C00150000",  # AAPL Call expiring 2024-03-15, strike 150
                    quantity=2,
                    avg_price=Decimal("5.50"),
                    current_price=Decimal("6.00"),
                    unrealized_pnl=Decimal("100.00"),
                )
            ],
        )

        # Mock option quote
        mock_option_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=6.00,
            bid=5.90,
            ask=6.10,
            underlying_price=155.00,
            volume=100,
            open_interest=500,
        )

        # Mock underlying stock quote
        mock_stock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=155.00,
            bid=154.95,
            ask=155.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):
            # Set up quote responses
            def quote_side_effect(symbol):
                if symbol == "AAPL240315C00150000":
                    return mock_option_quote
                elif symbol == "AAPL":
                    return mock_stock_quote
                return None

            mock_get_quote.side_effect = quote_side_effect

            # Test with expiration date (option expires)
            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15", dry_run=True
            )

            assert isinstance(result, dict)
            assert result["dry_run"] is True
            assert result["processing_date"] == "2024-03-15"
            assert result["total_positions"] == 1
            assert result["expiring_positions"] == 1
            assert result["non_expiring_positions"] == 0

            # Verify expiring option details
            expiring_option = result["expiring_options"][0]
            assert expiring_option["symbol"] == "AAPL240315C00150000"
            assert expiring_option["underlying_symbol"] == "AAPL"
            assert expiring_option["strike"] == 150.0
            assert expiring_option["option_type"] == "call"
            assert expiring_option["quantity"] == 2
            assert expiring_option["underlying_price"] == 155.00
            assert expiring_option["intrinsic_value"] == 5.0  # 155 - 150
            assert expiring_option["position_impact"] == 1000.0  # 5.0 * 2 * 100
            assert expiring_option["action"] == "exercise_or_assign"

            # Verify summary
            assert result["summary"]["positions_expiring"] == 1
            assert result["summary"]["estimated_cash_impact"] == 1000.0

    @pytest.mark.asyncio
    async def test_simulate_expiration_call_option_itm(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation for in-the-money call option."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="TSLA240315C00200000",  # TSLA Call, strike 200
                    quantity=1,
                    avg_price=Decimal("10.00"),
                    current_price=Decimal("15.00"),
                    unrealized_pnl=Decimal("500.00"),
                )
            ],
        )

        mock_option_quote = OptionQuote(
            asset=Option(
                symbol="TSLA240315C00200000",
                underlying=Stock(symbol="TSLA"),
                option_type="call",
                strike=200.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=15.00,
            bid=14.90,
            ask=15.10,
            underlying_price=220.00,  # ITM: underlying > strike
            volume=50,
            open_interest=200,
        )

        mock_stock_quote = Quote(
            asset=Stock(symbol="TSLA"),
            quote_date=datetime.now(),
            price=220.00,
            bid=219.95,
            ask=220.05,
            bid_size=100,
            ask_size=100,
            volume=500000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):

            def quote_side_effect(symbol):
                if symbol == "TSLA240315C00200000":
                    return mock_option_quote
                elif symbol == "TSLA":
                    return mock_stock_quote
                return None

            mock_get_quote.side_effect = quote_side_effect

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["expiring_positions"] == 1
            expiring_option = result["expiring_options"][0]
            assert expiring_option["intrinsic_value"] == 20.0  # 220 - 200
            assert expiring_option["position_impact"] == 2000.0  # 20.0 * 1 * 100
            assert expiring_option["action"] == "exercise_or_assign"

    @pytest.mark.asyncio
    async def test_simulate_expiration_put_option_itm(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation for in-the-money put option."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="SPY240315P00400000",  # SPY Put, strike 400
                    quantity=3,
                    avg_price=Decimal("8.00"),
                    current_price=Decimal("12.00"),
                    unrealized_pnl=Decimal("1200.00"),
                )
            ],
        )

        mock_option_quote = OptionQuote(
            asset=Option(
                symbol="SPY240315P00400000",
                underlying=Stock(symbol="SPY"),
                option_type="put",
                strike=400.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=12.00,
            bid=11.90,
            ask=12.10,
            underlying_price=380.00,  # ITM: underlying < strike for puts
            volume=200,
            open_interest=1000,
        )

        mock_stock_quote = Quote(
            asset=Stock(symbol="SPY"),
            quote_date=datetime.now(),
            price=380.00,
            bid=379.95,
            ask=380.05,
            bid_size=100,
            ask_size=100,
            volume=2000000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):

            def quote_side_effect(symbol):
                if symbol == "SPY240315P00400000":
                    return mock_option_quote
                elif symbol == "SPY":
                    return mock_stock_quote
                return None

            mock_get_quote.side_effect = quote_side_effect

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["expiring_positions"] == 1
            expiring_option = result["expiring_options"][0]
            assert expiring_option["intrinsic_value"] == 20.0  # 400 - 380
            assert expiring_option["position_impact"] == 6000.0  # 20.0 * 3 * 100
            assert expiring_option["action"] == "exercise_or_assign"

    @pytest.mark.asyncio
    async def test_simulate_expiration_otm_options_worthless(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation for out-of-the-money options (expire worthless)."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="AAPL240315C00200000",  # AAPL Call, strike 200 (OTM)
                    quantity=1,
                    avg_price=Decimal("2.00"),
                    current_price=Decimal("0.10"),
                    unrealized_pnl=Decimal("-190.00"),
                ),
                Position(
                    symbol="AAPL240315P00100000",  # AAPL Put, strike 100 (OTM)
                    quantity=2,
                    avg_price=Decimal("1.50"),
                    current_price=Decimal("0.05"),
                    unrealized_pnl=Decimal("-290.00"),
                ),
            ],
        )

        mock_call_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00200000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=200.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=0.10,
            bid=0.05,
            ask=0.15,
            underlying_price=180.00,  # OTM: underlying < strike for calls
            volume=10,
            open_interest=50,
        )

        mock_put_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240315P00100000",
                underlying=Stock(symbol="AAPL"),
                option_type="put",
                strike=100.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=0.05,
            bid=0.01,
            ask=0.10,
            underlying_price=180.00,  # OTM: underlying > strike for puts
            volume=5,
            open_interest=25,
        )

        mock_stock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=180.00,
            bid=179.95,
            ask=180.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):

            def quote_side_effect(symbol):
                quotes = {
                    "AAPL240315C00200000": mock_call_quote,
                    "AAPL240315P00100000": mock_put_quote,
                    "AAPL": mock_stock_quote,
                }
                return quotes.get(symbol)

            mock_get_quote.side_effect = quote_side_effect

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["expiring_positions"] == 2
            assert result["total_impact"] == 0.0  # Both options expire worthless

            # Verify both options expire worthless
            for expiring_option in result["expiring_options"]:
                assert expiring_option["intrinsic_value"] == 0.0
                assert expiring_option["position_impact"] == 0.0
                assert expiring_option["action"] == "expire_worthless"

    @pytest.mark.asyncio
    async def test_simulate_expiration_mixed_portfolio(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation with mixed portfolio (expiring and non-expiring positions)."""
        mock_portfolio = Portfolio(
            total_value=Decimal("20000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                # Expiring option (ITM)
                Position(
                    symbol="AAPL240315C00150000",
                    quantity=2,
                    avg_price=Decimal("5.00"),
                    current_price=Decimal("8.00"),
                    unrealized_pnl=Decimal("600.00"),
                ),
                # Non-expiring option (different date)
                Position(
                    symbol="AAPL240415C00160000",  # Expires April 15
                    quantity=1,
                    avg_price=Decimal("6.00"),
                    current_price=Decimal("7.00"),
                    unrealized_pnl=Decimal("100.00"),
                ),
                # Stock position
                Position(
                    symbol="AAPL",
                    quantity=100,
                    avg_price=Decimal("150.00"),
                    current_price=Decimal("160.00"),
                    unrealized_pnl=Decimal("1000.00"),
                ),
            ],
        )

        # Mock quotes for each position
        mock_expiring_option = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=8.00,
            bid=7.90,
            ask=8.10,
            underlying_price=160.00,
            volume=100,
            open_interest=500,
        )

        mock_stock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=160.00,
            bid=159.95,
            ask=160.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):

            def quote_side_effect(symbol):
                if symbol == "AAPL240315C00150000":
                    return mock_expiring_option
                elif symbol == "AAPL":
                    return mock_stock_quote
                return None

            mock_get_quote.side_effect = quote_side_effect

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["total_positions"] == 3
            assert result["expiring_positions"] == 1  # Only the March 15 option
            assert result["non_expiring_positions"] == 2  # April option + stock
            assert result["total_impact"] == 2000.0  # 10.0 * 2 * 100

            # Verify non-expiring positions
            non_expiring = result["non_expiring_positions_details"]
            assert len(non_expiring) == 2

            # Check the April option
            april_option = next(
                (pos for pos in non_expiring if "240415" in pos["symbol"]), None
            )
            assert april_option is not None
            assert april_option["days_to_expiration"] == 31  # March 15 to April 15

            # Check the stock position
            stock_position = next(
                (pos for pos in non_expiring if pos["symbol"] == "AAPL"), None
            )
            assert stock_position is not None
            assert stock_position["position_type"] == "stock"

    @pytest.mark.asyncio
    async def test_simulate_expiration_no_processing_date_uses_today(
        self, trading_service_synthetic_data
    ):
        """Test that simulate_expiration uses today's date when no processing_date provided."""
        today = datetime.now().date()

        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[],
        )

        with patch.object(
            trading_service_synthetic_data, "get_portfolio", return_value=mock_portfolio
        ):
            result = await trading_service_synthetic_data.simulate_expiration()

            assert result["processing_date"] == today.isoformat()
            assert result["dry_run"] is True  # Default to dry run

    @pytest.mark.asyncio
    async def test_simulate_expiration_live_processing_mode(
        self, trading_service_synthetic_data
    ):
        """Test simulate_expiration in live processing mode (dry_run=False)."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[],
        )

        with patch.object(
            trading_service_synthetic_data, "get_portfolio", return_value=mock_portfolio
        ):
            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15", dry_run=False
            )

            assert result["dry_run"] is False
            assert "processing_note" in result
            assert "not implemented" in result["processing_note"]

    @pytest.mark.asyncio
    async def test_simulate_expiration_quote_error_handling(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation handles quote retrieval errors gracefully."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="TEST240315C00150000",
                    quantity=1,
                    avg_price=Decimal("5.00"),
                    current_price=Decimal("6.00"),
                    unrealized_pnl=Decimal("100.00"),
                )
            ],
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):
            # Simulate quote retrieval failure
            mock_get_quote.side_effect = Exception("Quote not available")

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["expiring_positions"] == 1
            expiring_option = result["expiring_options"][0]
            assert "error" in expiring_option
            assert "Could not get quote" in expiring_option["error"]
            assert expiring_option["action"] == "manual_review_required"
            assert result["summary"]["positions_requiring_review"] == 1

    @pytest.mark.asyncio
    async def test_simulate_expiration_position_parsing_error(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation handles position parsing errors gracefully."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="INVALID_FORMAT",
                    quantity=1,
                    avg_price=Decimal("5.00"),
                    current_price=Decimal("6.00"),
                    unrealized_pnl=Decimal("100.00"),
                )
            ],
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch("app.models.assets.asset_factory") as mock_asset_factory,
        ):
            # Simulate asset parsing failure
            mock_asset_factory.side_effect = Exception("Invalid symbol format")

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["expiring_positions"] == 1
            expiring_option = result["expiring_options"][0]
            assert "error" in expiring_option
            assert "Could not parse position" in expiring_option["error"]
            assert expiring_option["action"] == "manual_review_required"

    @pytest.mark.asyncio
    async def test_simulate_expiration_portfolio_retrieval_error(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation handles portfolio retrieval errors gracefully."""
        with patch.object(
            trading_service_synthetic_data, "get_portfolio"
        ) as mock_get_portfolio:
            mock_get_portfolio.side_effect = Exception("Portfolio not available")

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert "error" in result
            assert "Simulation failed" in result["error"]
            assert "Portfolio not available" in result["error"]

    @pytest.mark.asyncio
    async def test_simulate_expiration_invalid_date_format(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation with invalid date format."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[],
        )

        with patch.object(
            trading_service_synthetic_data, "get_portfolio", return_value=mock_portfolio
        ):
            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="invalid-date-format"
            )

            assert "error" in result
            assert "Simulation failed" in result["error"]

    @pytest.mark.asyncio
    async def test_simulate_expiration_at_the_money_options(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation for at-the-money options (intrinsic value = 0)."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("5000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                Position(
                    symbol="AAPL240315C00150000",  # Strike = underlying price
                    quantity=1,
                    avg_price=Decimal("5.00"),
                    current_price=Decimal("2.00"),
                    unrealized_pnl=Decimal("-300.00"),
                )
            ],
        )

        mock_option_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00150000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=150.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=2.00,
            bid=1.90,
            ask=2.10,
            underlying_price=150.00,  # ATM: underlying = strike
            volume=50,
            open_interest=200,
        )

        mock_stock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=150.00,
            bid=149.95,
            ask=150.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):

            def quote_side_effect(symbol):
                if symbol == "AAPL240315C00150000":
                    return mock_option_quote
                elif symbol == "AAPL":
                    return mock_stock_quote
                return None

            mock_get_quote.side_effect = quote_side_effect

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["expiring_positions"] == 1
            expiring_option = result["expiring_options"][0]
            assert expiring_option["intrinsic_value"] == 0.0  # ATM = no intrinsic value
            assert expiring_option["position_impact"] == 0.0
            assert expiring_option["action"] == "expire_worthless"

    @pytest.mark.asyncio
    async def test_simulate_expiration_empty_portfolio(
        self, trading_service_synthetic_data
    ):
        """Test expiration simulation with empty portfolio."""
        mock_portfolio = Portfolio(
            total_value=Decimal("10000.00"),
            cash_balance=Decimal("10000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[],
        )

        with patch.object(
            trading_service_synthetic_data, "get_portfolio", return_value=mock_portfolio
        ):
            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            assert result["total_positions"] == 0
            assert result["expiring_positions"] == 0
            assert result["non_expiring_positions"] == 0
            assert result["total_impact"] == 0.0
            assert len(result["expiring_options"]) == 0
            assert len(result["non_expiring_positions_details"]) == 0
            assert result["summary"]["positions_expiring"] == 0
            assert result["summary"]["estimated_cash_impact"] == 0.0
            assert result["summary"]["positions_requiring_review"] == 0

    @pytest.mark.asyncio
    async def test_simulate_expiration_comprehensive_summary_validation(
        self, trading_service_synthetic_data
    ):
        """Test comprehensive validation of expiration simulation summary data."""
        mock_portfolio = Portfolio(
            total_value=Decimal("30000.00"),
            cash_balance=Decimal("10000.00"),
            daily_pnl=Decimal("0.00"),
            total_pnl=Decimal("0.00"),
            positions=[
                # ITM Call (will exercise)
                Position(
                    symbol="AAPL240315C00140000",
                    quantity=2,
                    avg_price=Decimal("8.00"),
                    current_price=Decimal("12.00"),
                    unrealized_pnl=Decimal("800.00"),
                ),
                # OTM Put (expire worthless)
                Position(
                    symbol="AAPL240315P00120000",
                    quantity=1,
                    avg_price=Decimal("3.00"),
                    current_price=Decimal("0.50"),
                    unrealized_pnl=Decimal("-250.00"),
                ),
                # Quote error position
                Position(
                    symbol="ERROR15C00150000",
                    quantity=1,
                    avg_price=Decimal("5.00"),
                    current_price=Decimal("6.00"),
                    unrealized_pnl=Decimal("100.00"),
                ),
            ],
        )

        mock_call_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240315C00140000",
                underlying=Stock(symbol="AAPL"),
                option_type="call",
                strike=140.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=12.00,
            bid=11.90,
            ask=12.10,
            underlying_price=155.00,
            volume=100,
            open_interest=500,
        )

        mock_put_quote = OptionQuote(
            asset=Option(
                symbol="AAPL240315P00120000",
                underlying=Stock(symbol="AAPL"),
                option_type="put",
                strike=120.0,
                expiration_date=date(2024, 3, 15),
            ),
            quote_date=datetime.now(),
            price=0.50,
            bid=0.45,
            ask=0.55,
            underlying_price=155.00,
            volume=10,
            open_interest=50,
        )

        mock_stock_quote = Quote(
            asset=Stock(symbol="AAPL"),
            quote_date=datetime.now(),
            price=155.00,
            bid=154.95,
            ask=155.05,
            bid_size=100,
            ask_size=100,
            volume=1000000,
        )

        with (
            patch.object(
                trading_service_synthetic_data,
                "get_portfolio",
                return_value=mock_portfolio,
            ),
            patch.object(
                trading_service_synthetic_data, "get_enhanced_quote"
            ) as mock_get_quote,
        ):

            def quote_side_effect(symbol):
                if symbol == "AAPL240315C00140000":
                    return mock_call_quote
                elif symbol == "AAPL240315P00120000":
                    return mock_put_quote
                elif symbol == "AAPL":
                    return mock_stock_quote
                elif symbol == "ERROR15C00150000":
                    raise Exception("Quote error")
                return None

            mock_get_quote.side_effect = quote_side_effect

            result = await trading_service_synthetic_data.simulate_expiration(
                processing_date="2024-03-15"
            )

            # Verify comprehensive summary
            assert result["total_positions"] == 3
            assert result["expiring_positions"] == 3
            assert result["total_impact"] == 3000.0  # Call: 15*2*100, Put: 0, Error: 0

            summary = result["summary"]
            assert summary["positions_expiring"] == 3
            assert summary["estimated_cash_impact"] == 3000.0
            assert summary["positions_requiring_review"] == 1  # The error position

            # Verify individual position details
            expiring_options = result["expiring_options"]
            assert len(expiring_options) == 3

            # Find each position type
            call_position = next(
                pos
                for pos in expiring_options
                if pos["symbol"] == "AAPL240315C00140000"
            )
            put_position = next(
                pos
                for pos in expiring_options
                if pos["symbol"] == "AAPL240315P00120000"
            )
            error_position = next(
                pos for pos in expiring_options if pos["symbol"] == "ERROR15C00150000"
            )

            # Verify call position
            assert call_position["intrinsic_value"] == 15.0  # 155 - 140
            assert call_position["action"] == "exercise_or_assign"

            # Verify put position
            assert put_position["intrinsic_value"] == 0.0  # max(0, 120 - 155)
            assert put_position["action"] == "expire_worthless"

            # Verify error position
            assert "error" in error_position
            assert error_position["action"] == "manual_review_required"
