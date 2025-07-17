import pytest
from unittest.mock import MagicMock, patch
from app.services.trading_service import TradingService
from app.models.trading import Portfolio, Position, PortfolioSummary, StockQuote
from app.models.quotes import OptionsChain, OptionQuote, Quote
from app.models.assets import Option, Stock
from app.schemas.orders import OrderType, OrderCondition, Order, OrderCreate, OrderStatus
from app.core.exceptions import NotFoundError
from app.models.database.trading import Account as DBAccount, Position as DBPosition
from datetime import date, datetime


@pytest.fixture
def trading_service(db_session):
    """Provides a TradingService instance with real database session."""
    service = TradingService(account_owner="test_user")
    service.quote_adapter = MagicMock()
    # Override the database session getter to use test database
    service._get_db_session = lambda: db_session
    return service

@pytest.fixture
def sample_account(db_session):
    """Create a sample account for testing."""
    account = DBAccount(
        id="test-account-id",
        owner="test_user",
        cash_balance=100000.0
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account

@pytest.fixture
def sample_positions(db_session, sample_account):
    """Create sample positions for testing."""
    positions = [
        DBPosition(
            id="pos-1",
            account_id=sample_account.id,
            symbol="AAPL",
            quantity=10,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=50.0
        ),
        DBPosition(
            id="pos-2", 
            account_id=sample_account.id,
            symbol="GOOGL",
            quantity=5,
            avg_price=2800.0,
            current_price=2750.0,
            unrealized_pnl=-250.0
        )
    ]
    for pos in positions:
        db_session.add(pos)
    db_session.commit()
    return positions


@patch("app.services.trading_service.aggregate_portfolio_greeks")
@patch("app.services.trading_service.analyze_advanced_strategy_pnl")
@patch("app.services.trading_service.detect_complex_strategies")
@patch("app.services.trading_service.get_portfolio_optimization_recommendations")
@pytest.mark.asyncio
async def test_analyze_portfolio_strategies(
    mock_get_recs,
    mock_detect_complex,
    mock_analyze_pnl,
    mock_agg_greeks,
    trading_service,
    sample_account,
    sample_positions,
):
    """Test the comprehensive strategy analysis method."""
    # Arrange - Use real database data instead of mocks
    trading_service.get_enhanced_quote = MagicMock(return_value=MagicMock())

    mock_agg_greeks.return_value = MagicMock(
        delta=1,
        gamma=2,
        theta=3,
        vega=4,
        rho=5,
        delta_normalized=0.1,
        delta_dollars=100,
        theta_dollars=300,
    )
    mock_analyze_pnl.return_value = [
        MagicMock(
            strategy_type="test",
            strategy_name="Test Strategy",
            unrealized_pnl=100,
            realized_pnl=0,
            total_pnl=100,
            pnl_percent=10,
            cost_basis=1000,
            market_value=1100,
            days_held=10,
            annualized_return=365,
        )
    ]
    mock_detect_complex.return_value = [
        MagicMock(
            complex_type="iron_condor",
            underlying_symbol="AAPL",
            legs=[],
            net_credit=1.0,
            max_profit=100,
            max_loss=-100,
            breakeven_points=[1, 2],
        )
    ]
    mock_get_recs.return_value = ["recommendation1"]

    # Act
    result = await trading_service.analyze_portfolio_strategies(
        include_greeks=True,
        include_pnl=True,
        include_complex_strategies=True,
        include_recommendations=True,
    )

    # Assert
    assert result is not None
    assert "portfolio_greeks" in result
    assert result["portfolio_greeks"]["delta"] == 1
    assert "strategy_pnl" in result
    assert result["strategy_pnl"][0]["total_pnl"] == 100
    assert "complex_strategies" in result
    assert result["complex_strategies"][0]["complex_type"] == "iron_condor"
    assert "recommendations" in result
    assert result["recommendations"][0] == "recommendation1"

    # Verify the database data was used (positions from sample_positions fixture)
    trading_service.get_enhanced_quote.assert_called_with("AAPL")
    mock_agg_greeks.assert_called_once()
    mock_analyze_pnl.assert_called_once()
    mock_detect_complex.assert_called_once()
    mock_get_recs.assert_called_once()


def test_get_formatted_options_chain(trading_service):
    """Test the options chain formatting and filtering method."""
    # Arrange
    mock_option_asset_1 = Option(symbol="AAPL240119C00150000")
    mock_option_asset_2 = Option(symbol="AAPL240119P00150000")
    mock_chain = OptionsChain(
        underlying_symbol="AAPL",
        expiration_date=date(2024, 1, 19),
        underlying_price=150.0,
        calls=[
            OptionQuote(
                asset=mock_option_asset_1,
                quote_date=datetime.now(),
                price=1.0,
                strike=150.0,
            ),
        ],
        puts=[
            OptionQuote(
                asset=mock_option_asset_2,
                quote_date=datetime.now(),
                price=2.0,
                strike=150.0,
            ),
        ],
    )
    trading_service.get_options_chain = MagicMock(return_value=mock_chain)

    # Act
    result = trading_service.get_formatted_options_chain(
        "AAPL",
        expiration_date=date(2024, 1, 19),
        min_strike=140,
        max_strike=160,
        include_greeks=True,
    )

    # Assert
    assert result is not None
    assert result["underlying_symbol"] == "AAPL"
    assert len(result["calls"]) == 1
    assert len(result["puts"]) == 1
    assert result["calls"][0]["strike"] == 150.0
    assert "delta" in result["calls"][0]
    trading_service.get_options_chain.assert_called_once_with("AAPL", date(2024, 1, 19))


def test_create_multi_leg_order_from_request(trading_service):
    """Test creating a multi-leg order from a raw request."""
    # Arrange
    raw_legs = [
        {"symbol": "AAPL240119C00150000", "quantity": 1, "side": "buy"},
        {"symbol": "AAPL240119C00155000", "quantity": 1, "side": "sell"},
    ]
    trading_service.create_multi_leg_order = MagicMock(
        return_value=Order(
            id="123",
            symbol="AAPL_SPREAD",
            order_type=OrderType.BUY,
            quantity=1,
            price=1.0,
            condition=OrderCondition.LIMIT,
            status="pending",
        )
    )

    # Act
    order = trading_service.create_multi_leg_order_from_request(raw_legs, "limit", 2.50)

    # Assert
    assert order is not None
    assert order.id == "123"
    trading_service.create_multi_leg_order.assert_called_once()


# ============================================================================
# CORE TRADING METHODS TESTS
# ============================================================================

class TestOrderManagement:
    """Tests for order management functionality."""
    
    @pytest.mark.asyncio
    async def test_create_order_success(self, trading_service, sample_account):
        """Test successful order creation with database persistence."""
        # Arrange
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.00
        )
        
        # Mock quote lookup
        trading_service.get_quote = MagicMock(return_value=StockQuote(
            symbol="AAPL", price=150.00, change=0, change_percent=0, volume=1000, last_updated=datetime.now()
        ))
        
        # Act
        result = await trading_service.create_order(order_data)
        
        # Assert
        assert result is not None
        assert isinstance(result, Order)
        assert result.symbol == "AAPL"
        assert result.order_type == OrderType.BUY
        assert result.quantity == 10
        assert result.price == 150.00
        trading_service.get_quote.assert_called_once_with("AAPL")
        
    def test_create_order_symbol_not_found(self, trading_service):
        """Test order creation fails when symbol not found."""
        # Arrange
        order_data = OrderCreate(
            symbol="INVALID",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.00
        )
        
        trading_service.get_quote = MagicMock(side_effect=NotFoundError("Symbol not found"))
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.create_order(order_data)
            
    def test_create_order_account_not_found(self, trading_service):
        """Test order creation fails when account not found."""
        # Arrange
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=10,
            price=150.00
        )
        
        mock_db_session = MagicMock()
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.return_value = None
        
        trading_service.get_quote = MagicMock(return_value=StockQuote(
            symbol="AAPL", price=150.00, change=0, change_percent=0, volume=1000, last_updated=datetime.now()
        ))
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.create_order(order_data)
    
    def test_get_orders_success(self, trading_service):
        """Test successful retrieval of orders."""
        # Arrange
        mock_db_session = MagicMock()
        mock_account = MagicMock(id=1)
        mock_orders = [MagicMock(id="order_1", symbol="AAPL"), MagicMock(id="order_2", symbol="GOOGL")]
        
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.return_value = mock_account
        mock_db_session.query().filter().all.return_value = mock_orders
        
        # Act
        result = trading_service.get_orders()
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        
    def test_get_orders_no_account(self, trading_service):
        """Test get_orders returns empty list when account not found."""
        # Arrange
        mock_db_session = MagicMock()
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.return_value = None
        
        # Act
        result = trading_service.get_orders()
        
        # Assert
        assert result == []
    
    def test_get_order_success(self, trading_service):
        """Test successful retrieval of specific order."""
        # Arrange
        order_id = "order_123"
        mock_db_session = MagicMock()
        mock_account = MagicMock(id=1)
        mock_order = MagicMock(id=order_id, symbol="AAPL")
        
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.side_effect = [mock_account, mock_order]
        
        # Act
        result = trading_service.get_order(order_id)
        
        # Assert
        assert result is not None
        assert isinstance(result, Order)
        
    def test_get_order_not_found(self, trading_service):
        """Test get_order raises NotFoundError when order doesn't exist."""
        # Arrange
        order_id = "nonexistent"
        mock_db_session = MagicMock()
        mock_account = MagicMock(id=1)
        
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.side_effect = [mock_account, None]
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.get_order(order_id)
    
    def test_cancel_order_success(self, trading_service):
        """Test successful order cancellation."""
        # Arrange
        order_id = "order_123"
        mock_db_session = MagicMock()
        mock_account = MagicMock(id=1)
        mock_order = MagicMock(id=order_id, status=OrderStatus.PENDING)
        
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.side_effect = [mock_account, mock_order]
        
        # Act
        result = trading_service.cancel_order(order_id)
        
        # Assert
        assert result["message"] == "Order cancelled successfully"
        assert mock_order.status == OrderStatus.CANCELLED
        mock_db_session.commit.assert_called_once()
        
    def test_cancel_order_not_found(self, trading_service):
        """Test cancel_order raises NotFoundError when order doesn't exist."""
        # Arrange
        order_id = "nonexistent"
        mock_db_session = MagicMock()
        mock_account = MagicMock(id=1)
        
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.side_effect = [mock_account, None]
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.cancel_order(order_id)
    
    def test_create_multi_leg_order_success(self, trading_service):
        """Test successful creation of multi-leg order."""
        # Arrange
        mock_order_data = MagicMock()
        mock_order_data.legs = [MagicMock(order_type=OrderType.BUY, quantity=1, price=1.0)]
        mock_order_data.condition = OrderCondition.LIMIT
        
        # Act
        result = trading_service.create_multi_leg_order(mock_order_data)
        
        # Assert
        assert result is not None
        assert isinstance(result, Order)
        assert "MULTI_LEG" in result.symbol
        assert result.status == OrderStatus.FILLED


class TestPortfolioManagement:
    """Tests for portfolio management functionality."""
    
    @pytest.mark.asyncio
    async def test_get_portfolio_success(self, trading_service, sample_account, sample_positions):
        """Test successful portfolio retrieval with database persistence."""
        # Arrange
        # Mock quote lookup
        trading_service.get_quote = MagicMock(return_value=StockQuote(
            symbol="AAPL", price=155.0, change=5.0, change_percent=3.33, volume=1000, last_updated=datetime.now()
        ))
        
        # Act
        result = await trading_service.get_portfolio()
        
        # Assert
        assert result is not None
        assert isinstance(result, Portfolio)
        assert result.cash_balance == 100000.0  # From sample_account fixture
        assert len(result.positions) == 2  # From sample_positions fixture (AAPL, GOOGL)
        
        # Verify positions were loaded from database
        portfolio_symbols = [pos.symbol for pos in result.positions]
        assert "AAPL" in portfolio_symbols
        assert "GOOGL" in portfolio_symbols
        
    def test_get_portfolio_account_not_found(self, trading_service):
        """Test get_portfolio raises NotFoundError when account doesn't exist."""
        # Arrange
        mock_db_session = MagicMock()
        trading_service._get_db_session = MagicMock(return_value=mock_db_session)
        mock_db_session.query().filter().first.return_value = None
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.get_portfolio()
    
    def test_get_portfolio_summary_success(self, trading_service):
        """Test successful portfolio summary retrieval."""
        # Arrange
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[Position(symbol="AAPL", quantity=10, avg_price=150.0, current_price=155.0, unrealized_pnl=50.0)],
            total_value=11550.0,
            daily_pnl=50.0,
            total_pnl=50.0
        )
        trading_service.get_portfolio = MagicMock(return_value=mock_portfolio)
        
        # Act
        result = trading_service.get_portfolio_summary()
        
        # Assert
        assert result is not None
        assert isinstance(result, PortfolioSummary)
        assert result.cash_balance == 10000.0
        assert result.total_value == 11550.0
        
    def test_get_positions_success(self, trading_service):
        """Test successful positions retrieval."""
        # Arrange
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[Position(symbol="AAPL", quantity=10, avg_price=150.0)],
            total_value=11500.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        trading_service.get_portfolio = MagicMock(return_value=mock_portfolio)
        
        # Act
        result = trading_service.get_positions()
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        
    def test_get_position_success(self, trading_service):
        """Test successful specific position retrieval."""
        # Arrange
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[Position(symbol="AAPL", quantity=10, avg_price=150.0)],
            total_value=11500.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        trading_service.get_portfolio = MagicMock(return_value=mock_portfolio)
        
        # Act
        result = trading_service.get_position("AAPL")
        
        # Assert
        assert result is not None
        assert isinstance(result, Position)
        assert result.symbol == "AAPL"
        
    def test_get_position_not_found(self, trading_service):
        """Test get_position raises NotFoundError when position doesn't exist."""
        # Arrange
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        trading_service.get_portfolio = MagicMock(return_value=mock_portfolio)
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.get_position("NONEXISTENT")


# ============================================================================
# OPTIONS TRADING METHODS TESTS
# ============================================================================

class TestOptionsGreeks:
    """Tests for options Greeks functionality."""
    
    @patch('app.services.trading_service.aggregate_portfolio_greeks')
    def test_get_portfolio_greeks_success(self, mock_aggregate_greeks, trading_service):
        """Test successful portfolio Greeks calculation."""
        # Arrange
        mock_positions = [Position(symbol="AAPL240119C00150000", quantity=1, avg_price=5.0)]
        trading_service.get_positions = MagicMock(return_value=mock_positions)
        
        mock_quote = MagicMock(delta=0.5, gamma=0.1, theta=-0.05, vega=0.2, rho=0.1)
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        mock_greeks = MagicMock(
            delta=50.0, gamma=10.0, theta=-5.0, vega=20.0, rho=10.0,
            delta_normalized=0.5, gamma_normalized=0.1, theta_normalized=-0.05, vega_normalized=0.2,
            delta_dollars=5000.0, gamma_dollars=1000.0, theta_dollars=-500.0
        )
        mock_aggregate_greeks.return_value = mock_greeks
        
        # Act
        result = trading_service.get_portfolio_greeks()
        
        # Assert
        assert result is not None
        assert "portfolio_greeks" in result
        assert result["portfolio_greeks"]["delta"] == 50.0
        assert result["total_positions"] == 1
        
    def test_get_position_greeks_success(self, trading_service):
        """Test successful position Greeks calculation."""
        # Arrange
        symbol = "AAPL240119C00150000"
        mock_position = Position(symbol=symbol, quantity=1, avg_price=5.0)
        trading_service.get_position = MagicMock(return_value=mock_position)
        
        mock_quote = MagicMock(delta=0.5, gamma=0.1, theta=-0.05, vega=0.2, rho=0.1)
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        # Act
        result = trading_service.get_position_greeks(symbol)
        
        # Assert
        assert result is not None
        assert result["symbol"] == symbol
        assert result["greeks"]["delta"] == 0.5
        assert result["position_greeks"]["delta"] == 50.0  # 0.5 * 1 * 100
        
    def test_get_position_greeks_not_option(self, trading_service):
        """Test get_position_greeks raises error for non-option position."""
        # Arrange
        symbol = "AAPL"
        mock_position = Position(symbol=symbol, quantity=10, avg_price=150.0)
        trading_service.get_position = MagicMock(return_value=mock_position)
        
        mock_quote = MagicMock(spec=Quote)  # No delta attribute
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        # Act & Assert
        with pytest.raises(ValueError, match="not an options position"):
            trading_service.get_position_greeks(symbol)
    
    @patch('app.services.trading_service.asset_factory')
    @patch('app.services.trading_service.calculate_option_greeks')
    def test_get_option_greeks_response_success(self, mock_calc_greeks, mock_asset_factory, trading_service):
        """Test successful option Greeks response."""
        # Arrange
        option_symbol = "AAPL240119C00150000"
        mock_option = MagicMock(spec=Option)
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_option.option_type = "CALL"
        mock_option.get_days_to_expiration.return_value = 30
        
        mock_asset_factory.return_value = mock_option
        
        mock_greeks = {
            "delta": 0.5, "gamma": 0.1, "theta": -0.05, "vega": 0.2, "rho": 0.1,
            "charm": 0.01, "vanna": 0.02, "speed": 0.001, "zomma": 0.005, "color": 0.003,
            "iv": 0.25
        }
        mock_calc_greeks.return_value = mock_greeks
        
        mock_quote = MagicMock(price=5.0)
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        # Act
        result = trading_service.get_option_greeks_response(option_symbol)
        
        # Assert
        assert result is not None
        assert result["option_symbol"] == option_symbol
        assert result["underlying_symbol"] == "AAPL"
        assert result["delta"] == 0.5
        assert result["option_price"] == 5.0
        
    @patch('app.services.trading_service.asset_factory')
    @patch('app.services.trading_service.calculate_option_greeks')
    def test_calculate_greeks_success(self, mock_calc_greeks, mock_asset_factory, trading_service):
        """Test successful Greeks calculation."""
        # Arrange
        option_symbol = "AAPL240119C00150000"
        mock_option = MagicMock(spec=Option)
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.option_type = "CALL"
        mock_option.get_days_to_expiration.return_value = 30
        
        mock_asset_factory.return_value = mock_option
        
        mock_greeks = {"delta": 0.5, "gamma": 0.1, "theta": -0.05, "vega": 0.2, "rho": 0.1}
        mock_calc_greeks.return_value = mock_greeks
        
        mock_option_quote = MagicMock(price=5.0)
        mock_underlying_quote = MagicMock(price=150.0)
        trading_service.get_enhanced_quote = MagicMock(side_effect=[mock_option_quote, mock_underlying_quote])
        
        # Act
        result = trading_service.calculate_greeks(option_symbol)
        
        # Assert
        assert result is not None
        assert result["delta"] == 0.5
        mock_calc_greeks.assert_called_once()
        
    @patch('app.services.trading_service.asset_factory')
    def test_calculate_greeks_not_option(self, mock_asset_factory, trading_service):
        """Test calculate_greeks raises error for non-option symbol."""
        # Arrange
        symbol = "AAPL"
        mock_asset_factory.return_value = MagicMock(spec=Stock)
        
        # Act & Assert
        with pytest.raises(ValueError, match="is not an option"):
            trading_service.calculate_greeks(symbol)


class TestOptionsData:
    """Tests for options data retrieval functionality."""
    
    def test_get_options_chain_success(self, trading_service):
        """Test successful options chain retrieval."""
        # Arrange
        underlying = "AAPL"
        expiration_date = date(2024, 1, 19)
        
        mock_chain = MagicMock(spec=OptionsChain)
        trading_service.quote_adapter.get_options_chain = MagicMock(return_value=mock_chain)
        
        # Act
        result = trading_service.get_options_chain(underlying, expiration_date)
        
        # Assert
        assert result is not None
        assert result == mock_chain
        
    def test_get_options_chain_not_found(self, trading_service):
        """Test get_options_chain raises NotFoundError when chain not found."""
        # Arrange
        underlying = "INVALID"
        trading_service.quote_adapter.get_options_chain = MagicMock(return_value=None)
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.get_options_chain(underlying)
    
    def test_find_tradable_options_success(self, trading_service):
        """Test successful tradable options search."""
        # Arrange
        symbol = "AAPL"
        mock_option = MagicMock(spec=Option)
        mock_option.symbol = "AAPL240119C00150000"
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_option.option_type = "CALL"
        
        mock_option_quote = MagicMock()
        mock_option_quote.asset = mock_option
        mock_option_quote.bid = 4.8
        mock_option_quote.ask = 5.2
        mock_option_quote.price = 5.0
        
        mock_chain = MagicMock()
        mock_chain.calls = [mock_option_quote]
        mock_chain.puts = []
        
        trading_service.get_options_chain = MagicMock(return_value=mock_chain)
        
        # Act
        result = trading_service.find_tradable_options(symbol)
        
        # Assert
        assert result is not None
        assert result["symbol"] == symbol
        assert result["total_found"] == 1
        assert len(result["options"]) == 1
        
    def test_find_tradable_options_error(self, trading_service):
        """Test find_tradable_options handles errors gracefully."""
        # Arrange
        symbol = "AAPL"
        trading_service.get_options_chain = MagicMock(side_effect=Exception("API Error"))
        
        # Act
        result = trading_service.find_tradable_options(symbol)
        
        # Assert
        assert "error" in result
        assert "API Error" in result["error"]
    
    @patch('app.services.trading_service.asset_factory')
    def test_get_option_market_data_success(self, mock_asset_factory, trading_service):
        """Test successful option market data retrieval."""
        # Arrange
        option_id = "AAPL240119C00150000"
        mock_option = MagicMock(spec=Option)
        mock_option.symbol = option_id
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_option.option_type = "CALL"
        
        mock_asset_factory.return_value = mock_option
        
        mock_quote = MagicMock(spec=OptionQuote)
        mock_quote.asset = mock_option
        mock_quote.bid = 4.8
        mock_quote.ask = 5.2
        mock_quote.price = 5.0
        mock_quote.underlying_price = 150.0
        mock_quote.quote_date = datetime.now()
        
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        # Act
        result = trading_service.get_option_market_data(option_id)
        
        # Assert
        assert result is not None
        assert result["option_id"] == option_id
        assert result["underlying_symbol"] == "AAPL"
        assert result["bid_price"] == 4.8
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_option_market_data_invalid_symbol(self, mock_asset_factory, trading_service):
        """Test get_option_market_data handles invalid option symbol."""
        # Arrange
        option_id = "INVALID"
        mock_asset_factory.return_value = MagicMock(spec=Stock)  # Not an option
        
        # Act
        result = trading_service.get_option_market_data(option_id)
        
        # Assert
        assert "error" in result
        assert "Invalid option symbol" in result["error"]
    
    def test_get_expiration_dates_success(self, trading_service):
        """Test successful expiration dates retrieval."""
        # Arrange
        underlying = "AAPL"
        expected_dates = [date(2024, 1, 19), date(2024, 2, 16)]
        trading_service.quote_adapter.get_expiration_dates = MagicMock(return_value=expected_dates)
        
        # Act
        result = trading_service.get_expiration_dates(underlying)
        
        # Assert
        assert result == expected_dates
        trading_service.quote_adapter.get_expiration_dates.assert_called_once_with(underlying)


class TestOptionsStrategy:
    """Tests for options strategy analysis functionality."""
    
    @patch('app.services.trading_service.analyze_strategy_portfolio')
    def test_get_portfolio_strategies_success(self, mock_analyze, trading_service):
        """Test successful portfolio strategy analysis."""
        # Arrange
        mock_positions = [Position(symbol="AAPL240119C00150000", quantity=1, avg_price=5.0)]
        trading_service.get_positions = MagicMock(return_value=mock_positions)
        
        mock_strategy = MagicMock()
        mock_strategy.strategy_type = "long_call"
        mock_strategy.quantity = 1
        mock_strategy.asset = {"symbol": "AAPL"}
        
        mock_analysis = {
            "total_positions": 1,
            "total_strategies": 1,
            "strategies": [mock_strategy],
            "summary": {"long_call": 1}
        }
        mock_analyze.return_value = mock_analysis
        
        # Act
        result = trading_service.get_portfolio_strategies()
        
        # Assert
        assert result is not None
        assert result["total_strategies"] == 1
        assert len(result["strategies"]) == 1
        
    def test_analyze_portfolio_strategies_comprehensive(self, trading_service):
        """Test comprehensive portfolio strategy analysis."""
        # Arrange
        mock_positions = [Position(symbol="AAPL240119C00150000", quantity=1, avg_price=5.0)]
        trading_service.get_positions = MagicMock(return_value=mock_positions)
        
        mock_strategies = [MagicMock(dict=MagicMock(return_value={"type": "long_call"}))]
        mock_summary = {"long_call": 1}
        
        trading_service.strategy_recognition.group_positions_by_strategy = MagicMock(return_value=mock_strategies)
        trading_service.strategy_recognition.get_strategy_summary = MagicMock(return_value=mock_summary)
        
        # Act
        result = trading_service.analyze_portfolio_strategies()
        
        # Assert
        assert result is not None
        assert "strategies" in result
        assert "summary" in result
        assert result["total_strategies"] == 1
    
    @patch('app.services.trading_service.asset_factory')
    def test_simulate_expiration_success(self, mock_asset_factory, trading_service):
        """Test successful expiration simulation."""
        # Arrange
        processing_date = "2024-01-19"
        
        mock_option = MagicMock(spec=Option)
        mock_option.underlying.symbol = "AAPL"
        mock_option.strike = 150.0
        mock_option.expiration_date = date(2024, 1, 19)
        mock_option.option_type = "CALL"
        
        mock_asset_factory.return_value = mock_option
        
        mock_position = Position(symbol="AAPL240119C00150000", quantity=1, avg_price=5.0)
        mock_portfolio = Portfolio(
            cash_balance=10000.0,
            positions=[mock_position],
            total_value=10500.0,
            daily_pnl=0.0,
            total_pnl=0.0
        )
        trading_service.get_portfolio = MagicMock(return_value=mock_portfolio)
        
        mock_option_quote = MagicMock(price=5.0)
        mock_underlying_quote = MagicMock(price=155.0)
        trading_service.get_enhanced_quote = MagicMock(side_effect=[mock_option_quote, mock_underlying_quote])
        
        # Act
        result = trading_service.simulate_expiration(processing_date)
        
        # Assert
        assert result is not None
        assert result["processing_date"] == processing_date
        assert result["expiring_positions"] == 1
        assert result["total_impact"] == 500.0  # (155-150) * 1 * 100
        
    def test_simulate_expiration_error_handling(self, trading_service):
        """Test expiration simulation error handling."""
        # Arrange
        trading_service.get_portfolio = MagicMock(side_effect=Exception("Portfolio error"))
        
        # Act
        result = trading_service.simulate_expiration()
        
        # Assert
        assert "error" in result
        assert "Portfolio error" in result["error"]


# ============================================================================
# MARKET DATA METHODS TESTS
# ============================================================================

class TestMarketData:
    """Tests for market data functionality."""
    
    def test_get_quote_success(self, trading_service):
        """Test successful quote retrieval."""
        # Arrange
        symbol = "AAPL"
        
        # Act
        result = trading_service.get_quote(symbol)
        
        # Assert
        assert result is not None
        assert isinstance(result, StockQuote)
        assert result.symbol == symbol
        
    def test_get_quote_not_found(self, trading_service):
        """Test get_quote raises NotFoundError for unknown symbol."""
        # Arrange
        symbol = "UNKNOWN"
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.get_quote(symbol)
    
    @patch('app.services.trading_service.asset_factory')
    def test_get_enhanced_quote_success(self, mock_asset_factory, trading_service):
        """Test successful enhanced quote retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        mock_quote = MagicMock(spec=Quote)
        trading_service.quote_adapter.get_quote = MagicMock(return_value=mock_quote)
        
        # Act
        result = trading_service.get_enhanced_quote(symbol)
        
        # Assert
        assert result is not None
        assert result == mock_quote
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_enhanced_quote_no_quote_available(self, mock_asset_factory, trading_service):
        """Test enhanced quote raises error when no quote available."""
        # Arrange
        symbol = "AAPL"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        trading_service.quote_adapter.get_quote = MagicMock(return_value=None)
        
        # Act & Assert
        with pytest.raises(NotFoundError, match="No quote available for AAPL"):
            trading_service.get_enhanced_quote(symbol)
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_enhanced_quote_not_found(self, mock_asset_factory, trading_service):
        """Test get_enhanced_quote raises NotFoundError when no data available."""
        # Arrange
        symbol = "UNKNOWN"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        trading_service.quote_adapter.get_quote = MagicMock(return_value=None)
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service.get_enhanced_quote(symbol)
    
    @patch('app.services.trading_service.asset_factory')
    def test_get_stock_price_success(self, mock_asset_factory, trading_service):
        """Test successful stock price retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        mock_quote = MagicMock(price=150.0, bid=149.8, ask=150.2, quote_date=datetime.now())
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        # Act
        result = trading_service.get_stock_price(symbol)
        
        # Assert
        assert result is not None
        assert result["symbol"] == symbol.upper()
        assert result["price"] == 150.0
        assert "change" in result
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_stock_price_error(self, mock_asset_factory, trading_service):
        """Test get_stock_price error handling."""
        # Arrange
        symbol = "AAPL"
        mock_asset_factory.return_value = None
        
        # Act
        result = trading_service.get_stock_price(symbol)
        
        # Assert
        assert "error" in result
        assert "Invalid symbol" in result["error"]
    
    @patch('app.services.trading_service.asset_factory')
    def test_get_stock_info_success(self, mock_asset_factory, trading_service):
        """Test successful stock info retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        mock_info = {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": "2.5T"
        }
        trading_service.quote_adapter.get_stock_info = MagicMock(return_value=mock_info)
        
        # Act
        result = trading_service.get_stock_info(symbol)
        
        # Assert
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["company_name"] == "Apple Inc."
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_stock_info_fallback(self, mock_asset_factory, trading_service):
        """Test stock info fallback when adapter doesn't have extended functionality."""
        # Arrange
        symbol = "AAPL"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        mock_quote = MagicMock(quote_date=datetime.now())
        trading_service.get_enhanced_quote = MagicMock(return_value=mock_quote)
        
        # Act
        result = trading_service.get_stock_info(symbol)
        
        # Assert
        assert result is not None
        assert result["symbol"] == symbol.upper()
        assert result["company_name"] == f"{symbol.upper()} Company"
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_price_history_success(self, mock_asset_factory, trading_service):
        """Test successful price history retrieval."""
        # Arrange
        symbol = "AAPL"
        period = "week"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        mock_history = {
            "symbol": "AAPL",
            "period": "week",
            "data_points": [{"date": "2024-01-01", "close": 150.0}]
        }
        trading_service.quote_adapter.get_price_history = MagicMock(return_value=mock_history)
        
        # Act
        result = trading_service.get_price_history(symbol, period)
        
        # Assert
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["period"] == "week"
        
    @patch('app.services.trading_service.asset_factory')
    def test_get_stock_news_success(self, mock_asset_factory, trading_service):
        """Test successful stock news retrieval."""
        # Arrange
        symbol = "AAPL"
        mock_asset = MagicMock(spec=Stock)
        mock_asset_factory.return_value = mock_asset
        
        mock_news = {
            "symbol": "AAPL",
            "news": [{"title": "Apple reports earnings", "url": "http://example.com"}]
        }
        trading_service.quote_adapter.get_stock_news = MagicMock(return_value=mock_news)
        
        # Act
        result = trading_service.get_stock_news(symbol)
        
        # Assert
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert len(result["news"]) == 1
        
    def test_get_top_movers_success(self, trading_service):
        """Test successful top movers retrieval."""
        # Arrange
        mock_movers = {
            "movers": [{"symbol": "AAPL", "change_percent": 5.0}]
        }
        trading_service.quote_adapter.get_top_movers = MagicMock(return_value=mock_movers)
        
        # Act
        result = trading_service.get_top_movers()
        
        # Assert
        assert result is not None
        assert "movers" in result
        
    def test_get_top_movers_fallback(self, trading_service):
        """Test top movers fallback when adapter doesn't have extended functionality."""
        # Arrange
        trading_service.get_available_symbols = MagicMock(return_value=["AAPL", "GOOGL"])
        trading_service.get_stock_price = MagicMock(return_value={"price": 150.0, "change_percent": 2.0})
        
        # Act
        result = trading_service.get_top_movers()
        
        # Assert
        assert result is not None
        assert "movers" in result
        assert "message" in result
        
    def test_search_stocks_success(self, trading_service):
        """Test successful stock search."""
        # Arrange
        query = "AAPL"
        mock_results = {
            "query": "AAPL",
            "results": [{"symbol": "AAPL", "name": "Apple Inc."}]
        }
        trading_service.quote_adapter.search_stocks = MagicMock(return_value=mock_results)
        
        # Act
        result = trading_service.search_stocks(query)
        
        # Assert
        assert result is not None
        assert result["query"] == "AAPL"
        assert len(result["results"]) == 1
        
    def test_search_stocks_fallback(self, trading_service):
        """Test stock search fallback when adapter doesn't have extended functionality."""
        # Arrange
        query = "AAPL"
        trading_service.get_available_symbols = MagicMock(return_value=["AAPL", "GOOGL"])
        
        # Act
        result = trading_service.search_stocks(query)
        
        # Assert
        assert result is not None
        assert result["query"] == "AAPL"
        assert len(result["results"]) == 1
        assert result["results"][0]["symbol"] == "AAPL"


# ============================================================================
# DATABASE INTERACTION TESTS
# ============================================================================

class TestDatabaseInteraction:
    """Tests for database interaction functionality."""
    
    def test_get_db_session(self, trading_service):
        """Test database session retrieval."""
        # Act
        session = trading_service._get_db_session()
        
        # Assert
        assert session is not None
        # Note: In real tests, you might want to check session type
        
    @patch('app.services.trading_service.SessionLocal')
    def test_ensure_account_exists_creates_account(self, mock_session_local, trading_service):
        """Test account creation when account doesn't exist."""
        # Arrange
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query().filter().first.return_value = None
        
        # Act
        trading_service._ensure_account_exists()
        
        # Assert
        mock_session.add.assert_called()
        mock_session.commit.assert_called()
        
    @patch('app.services.trading_service.SessionLocal')
    def test_ensure_account_exists_account_exists(self, mock_session_local, trading_service):
        """Test account exists check when account already exists."""
        # Arrange
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_existing_account = MagicMock()
        mock_session.query().filter().first.return_value = mock_existing_account
        
        # Act
        trading_service._ensure_account_exists()
        
        # Assert
        mock_session.add.assert_not_called()
        
    def test_get_account_success(self, trading_service):
        """Test successful account retrieval."""
        # Arrange
        mock_session = MagicMock()
        mock_account = MagicMock()
        trading_service._get_db_session = MagicMock(return_value=mock_session)
        mock_session.query().filter().first.return_value = mock_account
        
        # Act
        result = trading_service._get_account()
        
        # Assert
        assert result == mock_account
        
    def test_get_account_not_found(self, trading_service):
        """Test get_account raises NotFoundError when account doesn't exist."""
        # Arrange
        mock_session = MagicMock()
        trading_service._get_db_session = MagicMock(return_value=mock_session)
        mock_session.query().filter().first.return_value = None
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            trading_service._get_account()


# ============================================================================
# UTILITY AND HELPER METHODS TESTS
# ============================================================================

class TestUtilityMethods:
    """Tests for utility and helper functionality."""
    
    def test_validate_account_state_success(self, trading_service):
        """Test successful account state validation."""
        # Arrange
        trading_service.account_validation.validate_account_state = MagicMock(return_value=True)
        
        # Act
        result = trading_service.validate_account_state()
        
        # Assert
        assert result is True
        trading_service.account_validation.validate_account_state.assert_called_once()
        
    def test_calculate_margin_requirement_success(self, trading_service):
        """Test successful margin requirement calculation."""
        # Arrange
        mock_margin_service = MagicMock()
        mock_margin_service.get_portfolio_margin_breakdown.return_value = {
            "total_margin": 5000.0,
            "maintenance_margin": 3000.0
        }
        trading_service.margin_service = mock_margin_service
        
        # Act
        result = trading_service.calculate_margin_requirement()
        
        # Assert
        assert result is not None
        assert "total_margin" in result
        
    def test_calculate_margin_requirement_no_service(self, trading_service):
        """Test margin requirement calculation when service not available."""
        # Arrange
        trading_service.margin_service = None
        
        # Act
        result = trading_service.calculate_margin_requirement()
        
        # Assert
        assert "error" in result
        assert "not available" in result["error"]
        
    def test_get_test_scenarios(self, trading_service):
        """Test test scenarios retrieval."""
        # Arrange
        mock_scenarios = {"scenario1": {"description": "Test scenario"}}
        trading_service.quote_adapter.get_test_scenarios = MagicMock(return_value=mock_scenarios)
        
        # Act
        result = trading_service.get_test_scenarios()
        
        # Assert
        assert result == mock_scenarios
        
    def test_set_test_date(self, trading_service):
        """Test test date setting."""
        # Arrange
        date_str = "2024-01-01"
        trading_service.quote_adapter.set_date = MagicMock()
        
        # Act
        trading_service.set_test_date(date_str)
        
        # Assert
        trading_service.quote_adapter.set_date.assert_called_once_with(date_str)
        
    def test_get_available_symbols(self, trading_service):
        """Test available symbols retrieval."""
        # Arrange
        mock_symbols = ["AAPL", "GOOGL", "MSFT"]
        trading_service.quote_adapter.get_available_symbols = MagicMock(return_value=mock_symbols)
        
        # Act
        result = trading_service.get_available_symbols()
        
        # Assert
        assert result == mock_symbols
        
    def test_get_sample_data_info(self, trading_service):
        """Test sample data info retrieval."""
        # Arrange
        mock_info = {"total_symbols": 100, "date_range": "2024-01-01 to 2024-12-31"}
        trading_service.quote_adapter.get_sample_data_info = MagicMock(return_value=mock_info)
        
        # Act
        result = trading_service.get_sample_data_info()
        
        # Assert
        assert result == mock_info
