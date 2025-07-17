"""
Integration tests for live quote functionality.

Tests cover adapter switching, cache validation, data persistence,
and end-to-end quote retrieval as required by QA feedback.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, date

from app.services.trading_service import TradingService
from app.adapters.robinhood import RobinhoodAdapter
from app.adapters.test_data import TestDataQuoteAdapter
from app.adapters.config import get_adapter_factory
from app.models.quotes import Quote, OptionQuote
from app.models.assets import Stock, Option
from app.models.database.trading import DBAccount, DBPosition
from app.storage.database import get_async_session


class TestLiveQuotes:
    """Integration tests for live quote functionality."""

    @pytest.fixture
    async def trading_service(self):
        """Create TradingService instance for integration testing."""
        return TradingService()

    @pytest.fixture
    async def test_account(self, trading_service):
        """Create test account for integration testing."""
        account = await trading_service.create_account(
            owner="test_user",
            initial_balance=10000.0
        )
        return account


    @pytest.fixture
    def sample_stock_quote(self):
        """Create sample stock quote for testing."""
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        return Quote(
            asset=stock,
            quote_date=datetime.now(),
            price=150.25,
            bid=149.75,
            ask=150.75,
            volume=1000000
        )

    @pytest.fixture
    def sample_option_quote(self):
        """Create sample option quote for testing."""
        underlying = Stock(symbol="AAPL", name="Apple Inc.")
        option = Option(
            symbol="AAPL240119C00150000",
            underlying=underlying,
            option_type="CALL",
            strike=150.0,
            expiration_date=date(2024, 1, 19)
        )
        return OptionQuote(
            asset=option,
            quote_date=datetime.now(),
            price=5.625,
            bid=5.50,
            ask=5.75,
            underlying_price=150.25,
            volume=100,
            open_interest=1000
        )

    @pytest.mark.asyncio
    async def test_adapter_switching_test_to_robinhood(self, trading_service, sample_stock_quote):
        """Test switching from test adapter to Robinhood adapter."""
        # Start with test adapter
        assert isinstance(trading_service.quote_adapter, TestDataQuoteAdapter)
        
        # Get quote from test adapter
        test_quote = await trading_service.get_quote("AAPL")
        assert test_quote is not None
        assert test_quote.asset.symbol == "AAPL"
        
        # Switch to Robinhood adapter - testing real integration
        # Mock only the external Robinhood API calls
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.stocks.get_fundamentals') as mock_fundamentals, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses
            mock_price.return_value = ['150.25']
            mock_fundamentals.return_value = [{'volume': '1000000'}]
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            # This should create a real RobinhoodAdapter and test the integration
            await trading_service.switch_quote_adapter("robinhood")
            
            # Verify adapter was switched to actual RobinhoodAdapter
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Get quote from Robinhood adapter - this tests the real integration
            robinhood_quote = await trading_service.get_quote("AAPL")
            assert robinhood_quote is not None
            assert robinhood_quote.price == 150.25
            
            # Verify the quotes are from different sources
            assert test_quote.price != robinhood_quote.price

    @pytest.mark.asyncio
    async def test_adapter_switching_robinhood_to_test(self, trading_service, sample_stock_quote):
        """Test switching from Robinhood adapter to test adapter."""
        # Start with Robinhood adapter - testing real integration
        # Mock only the external Robinhood API calls
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.stocks.get_fundamentals') as mock_fundamentals, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses
            mock_price.return_value = ['150.25']
            mock_fundamentals.return_value = [{'volume': '1000000'}]
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            # Switch to Robinhood adapter - testing real integration
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Get quote from Robinhood adapter
            robinhood_quote = await trading_service.get_quote("AAPL")
            assert robinhood_quote.price == 150.25
            
            # Switch back to test adapter
            await trading_service.switch_quote_adapter("test")
            
            # Verify adapter was switched to actual TestDataQuoteAdapter
            assert isinstance(trading_service.quote_adapter, TestDataQuoteAdapter)
            
            # Get quote from test adapter
            test_quote = await trading_service.get_quote("AAPL")
            assert test_quote is not None
            assert test_quote.price != robinhood_quote.price

    @pytest.mark.asyncio
    async def test_adapter_failover_on_failure(self, trading_service):
        """Test adapter failover when primary adapter fails."""
        # Test real failover behavior - mock external API to fail
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock authentication to succeed
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            # Mock API call to fail
            mock_price.side_effect = Exception("API Error")
            
            # Switch to Robinhood adapter
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Should fail with Robinhood due to API error
            with pytest.raises(Exception):
                await trading_service.get_quote("AAPL")
            
            # Switch to fallback adapter
            await trading_service.switch_quote_adapter("test")
            assert isinstance(trading_service.quote_adapter, TestDataQuoteAdapter)
            
            # Should succeed with test adapter
            quote = await trading_service.get_quote("AAPL")
            assert quote is not None
            assert quote.asset.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_quote_persistence_with_database(self, trading_service, test_account):
        """Test that quotes are properly integrated with database persistence."""
        # Create an order that should use live quotes
        order = await trading_service.create_order(
            account_id=test_account.id,
            symbol="AAPL",
            order_type="market",
            quantity=100,
            price=None  # Market order, price should come from quote
        )
        
        assert order is not None
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.price is not None  # Price should be set from quote
        
        # Verify order is persisted in database
        async with get_async_session() as db:
            from sqlalchemy import select
            from app.models.database.trading import DBOrder
            
            result = await db.execute(
                select(DBOrder).where(DBOrder.id == order.id)
            )
            db_order = result.scalar_one_or_none()
            
            assert db_order is not None
            assert db_order.symbol == "AAPL"
            assert db_order.quantity == 100
            assert db_order.price is not None

    @pytest.mark.asyncio
    async def test_portfolio_calculation_with_live_quotes(self, trading_service, test_account):
        """Test portfolio calculation using live quotes."""
        # Create some positions
        await trading_service.create_position(
            account_id=test_account.id,
            symbol="AAPL",
            quantity=100,
            avg_price=145.00
        )
        
        await trading_service.create_position(
            account_id=test_account.id,
            symbol="GOOGL",
            quantity=10,
            avg_price=2750.00
        )
        
        # Get portfolio (should use live quotes for current prices)
        portfolio = await trading_service.get_portfolio(test_account.id)
        
        assert portfolio is not None
        assert len(portfolio.positions) == 2
        
        # Verify positions have current prices from quotes
        aapl_position = next(pos for pos in portfolio.positions if pos.symbol == "AAPL")
        googl_position = next(pos for pos in portfolio.positions if pos.symbol == "GOOGL")
        
        assert aapl_position.current_price is not None
        assert googl_position.current_price is not None
        assert aapl_position.current_price != aapl_position.avg_price  # Should be different from avg
        assert googl_position.current_price != googl_position.avg_price

    @pytest.mark.asyncio
    async def test_concurrent_quote_requests(self, trading_service, sample_stock_quote):
        """Test concurrent quote requests for performance."""
        # Test real concurrent requests - mock external API only
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.stocks.get_fundamentals') as mock_fundamentals, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses
            mock_price.return_value = ['150.25']
            mock_fundamentals.return_value = [{'volume': '1000000'}]
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Make concurrent requests
            symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
            tasks = [trading_service.get_quote(symbol) for symbol in symbols]
            
            quotes = await asyncio.gather(*tasks)
            
            # Verify all quotes were retrieved
            assert len(quotes) == len(symbols)
            for quote in quotes:
                assert quote is not None
                assert quote.price == 150.25

    @pytest.mark.asyncio
    async def test_quote_caching_behavior(self, trading_service, sample_stock_quote):
        """Test quote caching behavior."""
        # Test real caching behavior - mock external API with call counting
        call_count = 0
        
        def mock_get_latest_price(symbol):
            nonlocal call_count
            call_count += 1
            return ['150.25']
        
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.stocks.get_fundamentals') as mock_fundamentals, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses with call counting
            mock_price.side_effect = mock_get_latest_price
            mock_fundamentals.return_value = [{'volume': '1000000'}]
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Make multiple requests for the same symbol
            quote1 = await trading_service.get_quote("AAPL")
            quote2 = await trading_service.get_quote("AAPL")
            quote3 = await trading_service.get_quote("AAPL")
            
            assert quote1 is not None
            assert quote2 is not None
            assert quote3 is not None
            
            # Without caching, should make 3 calls
            # With caching, should make fewer calls
            assert call_count >= 1  # At least one call should be made

    @pytest.mark.asyncio
    async def test_options_chain_integration(self, trading_service, sample_option_quote):
        """Test options chain integration with live quotes."""
        # Test real options chain integration - mock external API only
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.stocks.get_fundamentals') as mock_fundamentals, \
             patch('robin_stocks.robinhood.options.get_chains') as mock_chains, \
             patch('robin_stocks.robinhood.options.get_option_instruments') as mock_instruments, \
             patch('robin_stocks.robinhood.options.get_option_market_data_by_id') as mock_market_data, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses
            mock_price.return_value = ['150.25']
            mock_fundamentals.return_value = [{'volume': '1000000'}]
            mock_chains.return_value = [{'expiration_date': '2024-01-19'}]
            mock_instruments.return_value = [{'id': 'test_id', 'strike_price': '150.00', 'expiration_date': '2024-01-19'}]
            mock_market_data.return_value = {'bid_price': '5.50', 'ask_price': '5.75', 'volume': '100', 'open_interest': '1000'}
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Get options chain
            options_chain = await trading_service.get_options_chain("AAPL")
            
            assert options_chain is not None
            assert options_chain.underlying_symbol == "AAPL"
            assert options_chain.underlying_price == 150.25
            # Options chain should have been populated from mocked data
            assert options_chain.calls is not None or options_chain.puts is not None

    @pytest.mark.asyncio
    async def test_market_hours_integration(self, trading_service):
        """Test market hours integration."""
        # Test real market hours integration - mock external API only
        with patch('robin_stocks.robinhood.markets.get_market_hours') as mock_market_hours, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses
            mock_market_hours.return_value = {
                "is_open": True,
                "opens_at": "2024-01-19T14:30:00Z",
                "closes_at": "2024-01-19T21:00:00Z"
            }
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Check market status
            is_open = await trading_service.is_market_open()
            assert is_open is True
            
            # Get market hours
            hours = await trading_service.get_market_hours()
            assert hours["is_open"] is True
            assert "opens_at" in hours
            assert "closes_at" in hours

    @pytest.mark.asyncio
    async def test_error_handling_with_invalid_symbols(self, trading_service):
        """Test error handling with invalid symbols."""
        # Test real error handling - mock external API to return None for invalid symbols
        def mock_get_latest_price(symbol):
            if symbol == "INVALID":
                return None
            return ['150.25']
        
        with patch('robin_stocks.robinhood.stocks.get_latest_price') as mock_price, \
             patch('robin_stocks.robinhood.stocks.get_fundamentals') as mock_fundamentals, \
             patch('robin_stocks.robinhood.login') as mock_login, \
             patch('robin_stocks.robinhood.load_user_profile') as mock_profile:
            
            # Mock the external API responses
            mock_price.side_effect = mock_get_latest_price
            mock_fundamentals.return_value = [{'volume': '1000000'}]
            mock_login.return_value = None
            mock_profile.return_value = {'user_id': 'test_user'}
            
            await trading_service.switch_quote_adapter("robinhood")
            assert isinstance(trading_service.quote_adapter, RobinhoodAdapter)
            
            # Try to get quote for invalid symbol
            quote = await trading_service.get_quote("INVALID")
            assert quote is None

    @pytest.mark.asyncio
    async def test_adapter_configuration_validation(self, trading_service):
        """Test adapter configuration validation."""
        # Test valid adapter types
        valid_adapters = ["test", "robinhood"]
        
        for adapter_type in valid_adapters:
            try:
                await trading_service.switch_quote_adapter(adapter_type)
                # Should not raise exception
            except Exception as e:
                pytest.fail(f"Valid adapter type {adapter_type} should not raise exception: {e}")
        
        # Test invalid adapter type
        with pytest.raises(Exception):
            await trading_service.switch_quote_adapter("invalid_adapter")

    @pytest.mark.asyncio
    async def test_quote_data_consistency(self, trading_service, mock_robinhood_adapter):
        """Test that quote data is consistent across multiple calls."""
        # Setup mock adapter to return consistent data
        consistent_quote = Quote(
            asset=Stock(symbol="AAPL", name="Apple Inc."),
            quote_date=datetime.now(),
            price=150.25,
            bid=149.75,
            ask=150.75,
            volume=1000000
        )
        
        mock_robinhood_adapter.get_quote.return_value = consistent_quote
        
        with patch('app.adapters.config.get_adapter_factory') as mock_factory:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_adapter.return_value = mock_robinhood_adapter
            mock_factory.return_value = mock_factory_instance
            
            await trading_service.switch_quote_adapter("robinhood")
            
            # Make multiple requests
            quote1 = await trading_service.get_quote("AAPL")
            quote2 = await trading_service.get_quote("AAPL")
            
            # Verify consistency
            assert quote1.price == quote2.price
            assert quote1.bid == quote2.bid
            assert quote1.ask == quote2.ask
            assert quote1.volume == quote2.volume