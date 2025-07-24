"""
Comprehensive tests for order impact analysis service.

Tests all impact analysis functionality including:
- Account snapshot creation and management
- Order impact simulation and calculation
- Multi-leg order processing
- Position change analysis
- Greeks impact calculation for options
- Order validation and approval status
- Market data integration
- Error handling and edge cases
"""

from copy import deepcopy
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.models.assets import Option, OptionType, Stock
from app.schemas.orders import (
    MultiLegOrder,
    Order,
    OrderCondition,
    OrderLeg,
    OrderStatus,
    OrderType,
)
from app.schemas.positions import Position
from app.services.order_impact import (
    AccountSnapshot,
    OrderImpactAnalysis,
    OrderImpactService,
    analyze_order_impact,
    preview_order_impact,
)
from app.services.validation import ValidationError


class TestAccountSnapshot:
    """Test AccountSnapshot model."""

    def test_account_snapshot_creation(self):
        """Test creating account snapshot with all fields."""
        test_time = datetime.now()
        positions = [
            Position(
                symbol="AAPL",
                quantity=100,
                avg_price=150.0,
                current_price=155.0,
                unrealized_pnl=500.0,
            )
        ]

        snapshot = AccountSnapshot(
            cash_balance=50000.0,
            positions=positions,
            total_value=65500.0,
            buying_power=100000.0,
            timestamp=test_time,
        )

        assert snapshot.cash_balance == 50000.0
        assert len(snapshot.positions) == 1
        assert snapshot.total_value == 65500.0
        assert snapshot.buying_power == 100000.0
        assert snapshot.timestamp == test_time

    def test_account_snapshot_default_timestamp(self):
        """Test account snapshot with default timestamp."""
        snapshot = AccountSnapshot(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            buying_power=20000.0,
        )

        assert snapshot.timestamp is not None
        assert isinstance(snapshot.timestamp, datetime)

    def test_account_snapshot_empty_positions(self):
        """Test account snapshot with empty positions list."""
        snapshot = AccountSnapshot(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            buying_power=20000.0,
        )

        assert len(snapshot.positions) == 0


class TestOrderImpactAnalysis:
    """Test OrderImpactAnalysis model."""

    def test_order_impact_analysis_creation(self):
        """Test creating complete order impact analysis."""
        before_snapshot = AccountSnapshot(
            cash_balance=50000.0,
            positions=[],
            total_value=50000.0,
            buying_power=100000.0,
        )

        after_snapshot = AccountSnapshot(
            cash_balance=34500.0,
            positions=[
                Position(
                    symbol="AAPL", quantity=100, avg_price=155.0, current_price=155.0
                )
            ],
            total_value=50000.0,
            buying_power=84500.0,
        )

        analysis = OrderImpactAnalysis(
            order_id="test_order_123",
            order_type="Single leg buy",
            estimated_fill_price=155.0,
            commission=1.0,
            before=before_snapshot,
            after=after_snapshot,
            cash_impact=-15501.0,  # 100 * 155.0 + 1.0 commission
            buying_power_impact=-15500.0,
            position_impact={"new_positions": ["AAPL"]},
            validation_errors=[],
            approval_status="approved",
        )

        assert analysis.order_id == "test_order_123"
        assert analysis.cash_impact == -15501.0
        assert analysis.approval_status == "approved"
        assert len(analysis.validation_errors) == 0

    def test_order_impact_analysis_with_errors(self):
        """Test order impact analysis with validation errors."""
        before_snapshot = AccountSnapshot(
            cash_balance=1000.0, positions=[], total_value=1000.0, buying_power=1000.0
        )

        analysis = OrderImpactAnalysis(
            order_type="Single leg buy",
            before=before_snapshot,
            after=before_snapshot,  # No change due to rejection
            cash_impact=0.0,
            buying_power_impact=0.0,
            validation_errors=["Insufficient buying power"],
            approval_status="rejected",
        )

        assert analysis.approval_status == "rejected"
        assert len(analysis.validation_errors) == 1
        assert "Insufficient buying power" in analysis.validation_errors


class TestOrderImpactService:
    """Test OrderImpactService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = OrderImpactService()
        self.test_account_data = {
            "cash_balance": 50000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "avg_price": 150.0,
                    "current_price": 155.0,
                    "unrealized_pnl": 500.0,
                    "realized_pnl": 0.0,
                    "market_value": 15500.0,
                },
                {
                    "symbol": "GOOGL",
                    "quantity": 50,
                    "avg_price": 2800.0,
                    "current_price": 2750.0,
                    "unrealized_pnl": -2500.0,
                    "realized_pnl": 0.0,
                    "market_value": 137500.0,
                },
            ],
        }

    def create_test_order(
        self,
        symbol: str = "MSFT",
        quantity: int = 100,
        order_type: OrderType = OrderType.BUY,
        price: float | None = None,
        order_id: str = "test_order_123",
    ) -> Order:
        """Helper to create test orders."""
        return Order(
            id=order_id,
            symbol=symbol,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.MARKET if price is None else OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

    def create_mock_quote_adapter(self) -> MagicMock:
        """Create mock quote adapter."""
        adapter = MagicMock()
        adapter.get_quote = MagicMock()

        # Default quote responses
        quotes = {
            "AAPL": MagicMock(price=155.0),
            "GOOGL": MagicMock(price=2750.0),
            "MSFT": MagicMock(price=380.0),
            "TSLA": MagicMock(price=250.0),
        }

        def get_quote_side_effect(asset):
            symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)
            return quotes.get(symbol, MagicMock(price=100.0))

        adapter.get_quote.side_effect = get_quote_side_effect
        return adapter


class TestAnalyzeOrderImpact(TestOrderImpactService):
    """Test analyze_order_impact functionality."""

    def test_analyze_buy_order_impact(self):
        """Test impact analysis for a buy order."""
        order = self.create_test_order(
            symbol="MSFT", quantity=100, order_type=OrderType.BUY, price=380.0
        )

        mock_adapter = self.create_mock_quote_adapter()

        analysis = self.service.analyze_order_impact(
            self.test_account_data, order, mock_adapter
        )

        assert analysis.order_id == "test_order_123"
        assert analysis.order_type == "Single leg OrderType.BUY"
        assert analysis.estimated_fill_price == 380.0
        assert analysis.cash_impact == -38000.0  # 100 * 380.0
        assert analysis.buying_power_impact == -38000.0
        assert analysis.approval_status == "approved"
        assert len(analysis.validation_errors) == 0

        # Check before snapshot
        assert analysis.before.cash_balance == 50000.0
        assert len(analysis.before.positions) == 2

        # Check after snapshot
        assert analysis.after.cash_balance == 12000.0  # 50000 - 38000
        assert len(analysis.after.positions) == 3  # Added MSFT position

    def test_analyze_sell_order_impact(self):
        """Test impact analysis for a sell order of existing position."""
        order = self.create_test_order(
            symbol="AAPL", quantity=50, order_type=OrderType.SELL, price=155.0
        )

        mock_adapter = self.create_mock_quote_adapter()

        analysis = self.service.analyze_order_impact(
            self.test_account_data, order, mock_adapter
        )

        assert analysis.cash_impact == 7750.0  # 50 * 155.0
        assert analysis.buying_power_impact == 7750.0
        assert analysis.approval_status == "approved"

        # Check position changes
        aapl_position_after = None
        for pos in analysis.after.positions:
            if pos.symbol == "AAPL":
                aapl_position_after = pos
                break

        assert aapl_position_after is not None
        assert aapl_position_after.quantity == 50  # 100 - 50

    def test_analyze_order_with_estimated_fill_prices(self):
        """Test analysis with custom estimated fill prices."""
        order = self.create_test_order(
            symbol="TSLA", quantity=100, order_type=OrderType.BUY
        )

        estimated_fill_prices = {"TSLA": 260.0}  # Override default 250.0

        analysis = self.service.analyze_order_impact(
            self.test_account_data, order, estimated_fill_prices=estimated_fill_prices
        )

        assert analysis.estimated_fill_price == 260.0
        assert analysis.cash_impact == -26000.0  # 100 * 260.0

    def test_analyze_order_without_quote_adapter(self):
        """Test analysis without quote adapter."""
        order = self.create_test_order(
            symbol="NVDA", quantity=100, order_type=OrderType.BUY, price=500.0
        )

        analysis = self.service.analyze_order_impact(self.test_account_data, order)

        assert analysis.estimated_fill_price == 500.0  # Uses order price
        assert analysis.cash_impact == -50000.0

    def test_analyze_order_no_price_no_adapter(self):
        """Test analysis with no price and no quote adapter."""
        order = self.create_test_order(
            symbol="NVDA",
            quantity=100,
            order_type=OrderType.BUY,
            price=None,  # Market order, no price
        )

        analysis = self.service.analyze_order_impact(self.test_account_data, order)

        # Should use 0.0 as fill price when no data available
        assert analysis.cash_impact == 0.0

    def test_analyze_multi_leg_order(self):
        """Test analysis of multi-leg order."""
        legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"),
                quantity=50,
                order_type=OrderType.BUY,
                price=155.0,
            ),
            OrderLeg(
                asset=Stock(symbol="GOOGL"),
                quantity=-25,  # Sell
                order_type=OrderType.SELL,
                price=2750.0,
            ),
        ]

        multi_order = MultiLegOrder(
            id="multi_123",
            legs=legs,
            net_price=10.0,  # Net credit/debit
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        analysis = self.service.analyze_order_impact(
            self.test_account_data, multi_order
        )

        assert analysis.order_type == "Multi-leg order with 2 legs"
        assert analysis.estimated_fill_price == 10.0  # Net price

        # Net impact: -50*155 + 25*2750 = -7750 + 68750 = 61000
        assert analysis.cash_impact == 61000.0

    def test_analyze_order_list_of_legs(self):
        """Test analysis of list of order legs."""
        legs = [
            OrderLeg(
                asset=Stock(symbol="MSFT"),
                quantity=100,
                order_type=OrderType.BUY,
                price=380.0,
            )
        ]

        analysis = self.service.analyze_order_impact(self.test_account_data, legs)

        assert analysis.order_type == "Order with 1 legs"
        assert analysis.cash_impact == -38000.0


class TestPreviewOrder(TestOrderImpactService):
    """Test preview_order functionality."""

    def test_preview_order_basic(self):
        """Test basic order preview."""
        order = self.create_test_order(
            symbol="MSFT", quantity=100, order_type=OrderType.BUY, price=380.0
        )

        mock_adapter = self.create_mock_quote_adapter()

        preview = self.service.preview_order(
            self.test_account_data, order, mock_adapter
        )

        assert preview["estimated_cost"] == 38000.0  # abs(-38000.0)
        assert preview["approval_status"] == "approved"
        assert preview["buying_power_after"] == 12000.0  # 50000 - 38000
        assert len(preview["errors"]) == 0
        assert preview["estimated_fill"] == 380.0

    def test_preview_order_with_errors(self):
        """Test order preview with validation errors."""
        # Create expensive order that would cause validation errors
        order = self.create_test_order(
            symbol="BERKB",
            quantity=1000,
            order_type=OrderType.BUY,
            price=500000.0,  # Very expensive
        )

        # Mock validator to return errors
        mock_validator = MagicMock()
        mock_validator.validate_account_state.side_effect = ValidationError(
            "Insufficient funds"
        )

        service = OrderImpactService(validator=mock_validator)

        preview = service.preview_order(self.test_account_data, order)

        assert preview["approval_status"] == "rejected"
        assert len(preview["errors"]) > 0

    def test_preview_order_limits_errors(self):
        """Test that preview limits errors to top 3."""
        order = self.create_test_order(symbol="TEST", quantity=100)

        # Mock validator to return many errors
        mock_validator = MagicMock()
        mock_validator.validate_account_state.side_effect = ValidationError("Error")

        service = OrderImpactService(validator=mock_validator)

        # Mock the _validate_order method to return many errors
        with patch.object(service, "_validate_order") as mock_validate:
            mock_validate.return_value = [
                "Error 1",
                "Error 2",
                "Error 3",
                "Error 4",
                "Error 5",
            ]

            preview = service.preview_order(self.test_account_data, order)

        assert len(preview["errors"]) == 3  # Limited to top 3


class TestAccountSnapshotCreation(TestOrderImpactService):
    """Test _create_account_snapshot functionality."""

    def test_create_snapshot_with_position_objects(self):
        """Test creating snapshot with Position objects."""
        account_data = {
            "cash_balance": 25000.0,
            "positions": [
                Position(
                    symbol="AAPL",
                    quantity=100,
                    avg_price=150.0,
                    current_price=155.0,
                    market_value=15500.0,
                )
            ],
        }

        snapshot = self.service._create_account_snapshot(account_data)

        assert snapshot.cash_balance == 25000.0
        assert len(snapshot.positions) == 1
        assert snapshot.positions[0].symbol == "AAPL"
        assert snapshot.total_value == 40500.0  # 25000 + 15500
        assert snapshot.buying_power == 25000.0

    def test_create_snapshot_with_dict_positions(self):
        """Test creating snapshot with dictionary positions."""
        account_data = {
            "cash_balance": 30000.0,
            "positions": [
                {
                    "symbol": "GOOGL",
                    "quantity": 50,
                    "avg_price": 2800.0,
                    "current_price": 2750.0,
                    "market_value": 137500.0,
                    "unrealized_pnl": -2500.0,
                    "realized_pnl": 0.0,
                }
            ],
        }

        snapshot = self.service._create_account_snapshot(account_data)

        assert snapshot.cash_balance == 30000.0
        assert len(snapshot.positions) == 1
        assert isinstance(snapshot.positions[0], Position)
        assert snapshot.positions[0].symbol == "GOOGL"
        assert snapshot.total_value == 167500.0  # 30000 + 137500

    def test_create_snapshot_no_positions(self):
        """Test creating snapshot with no positions."""
        account_data = {"cash_balance": 50000.0, "positions": []}

        snapshot = self.service._create_account_snapshot(account_data)

        assert snapshot.cash_balance == 50000.0
        assert len(snapshot.positions) == 0
        assert snapshot.total_value == 50000.0
        assert snapshot.buying_power == 50000.0

    def test_create_snapshot_positions_with_none_market_value(self):
        """Test creating snapshot with positions having None market_value."""
        account_data = {
            "cash_balance": 40000.0,
            "positions": [
                Position(
                    symbol="TEST",
                    quantity=100,
                    avg_price=50.0,
                    market_value=None,  # None market value
                )
            ],
        }

        snapshot = self.service._create_account_snapshot(account_data)

        assert snapshot.total_value == 40000.0  # Only cash, no position value added


class TestOrderSimulation(TestOrderImpactService):
    """Test order execution simulation."""

    def test_simulate_order_execution_single_order(self):
        """Test simulating single order execution."""
        order = self.create_test_order(
            symbol="NVDA", quantity=50, order_type=OrderType.BUY, price=600.0
        )

        result = self.service._simulate_order_execution(self.test_account_data, order)

        # Should have new NVDA position
        nvda_position = None
        for pos in result["positions"]:
            if pos.get("symbol") if isinstance(pos, dict) else pos.symbol == "NVDA":
                nvda_position = pos
                break

        assert nvda_position is not None
        assert nvda_position["quantity"] == 50
        assert nvda_position["avg_price"] == 600.0
        assert result["cash_balance"] == 20000.0  # 50000 - 30000

    def test_simulate_order_execution_multi_leg(self):
        """Test simulating multi-leg order execution."""
        legs = [
            OrderLeg(
                asset=Stock(symbol="IBM"),
                quantity=100,
                order_type=OrderType.BUY,
                price=140.0,
            ),
            OrderLeg(
                asset=Stock(symbol="AAPL"),  # Existing position
                quantity=-50,  # Sell half
                order_type=OrderType.SELL,
                price=155.0,
            ),
        ]

        multi_order = MultiLegOrder(
            id="multi_test",
            legs=legs,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        result = self.service._simulate_order_execution(
            self.test_account_data, multi_order
        )

        # Check IBM position was added
        ibm_position = None
        aapl_position = None
        for pos in result["positions"]:
            symbol = pos.get("symbol") if isinstance(pos, dict) else pos.symbol
            if symbol == "IBM":
                ibm_position = pos
            elif symbol == "AAPL":
                aapl_position = pos

        assert ibm_position is not None
        assert ibm_position["quantity"] == 100

        assert aapl_position is not None
        aapl_qty = (
            aapl_position.get("quantity")
            if isinstance(aapl_position, dict)
            else aapl_position.quantity
        )
        assert aapl_qty == 50  # 100 - 50

        # Cash impact: -100*140 + 50*155 = -14000 + 7750 = -6250
        assert result["cash_balance"] == 43750.0  # 50000 - 6250

    def test_simulate_order_execution_list_of_legs(self):
        """Test simulating execution with list of legs."""
        legs = [
            OrderLeg(
                asset=Stock(symbol="META"),
                quantity=25,
                order_type=OrderType.BUY,
                price=320.0,
            )
        ]

        result = self.service._simulate_order_execution(self.test_account_data, legs)

        # Should create new META position
        meta_position = None
        for pos in result["positions"]:
            if pos.get("symbol") if isinstance(pos, dict) else pos.symbol == "META":
                meta_position = pos
                break

        assert meta_position is not None
        assert meta_position["quantity"] == 25
        assert result["cash_balance"] == 42000.0  # 50000 - 8000


class TestLegSimulation(TestOrderImpactService):
    """Test _simulate_leg_execution functionality."""

    def test_simulate_leg_with_estimated_fill_price(self):
        """Test leg simulation with estimated fill price."""
        account_data = deepcopy(self.test_account_data)

        leg = OrderLeg(
            asset=Stock(symbol="AMZN"),
            quantity=10,
            order_type=OrderType.BUY,
            price=3200.0,
        )

        estimated_fill_prices = {"AMZN": 3150.0}  # Different from order price

        self.service._simulate_leg_execution(
            account_data, leg, estimated_fill_prices=estimated_fill_prices
        )

        # Should use estimated fill price
        assert account_data["cash_balance"] == 18500.0  # 50000 - 31500

        # Check new position
        amzn_position = None
        for pos in account_data["positions"]:
            if pos.get("symbol") == "AMZN":
                amzn_position = pos
                break

        assert amzn_position is not None
        assert amzn_position["avg_price"] == 3150.0

    def test_simulate_leg_with_quote_adapter(self):
        """Test leg simulation with quote adapter."""
        account_data = deepcopy(self.test_account_data)

        leg = OrderLeg(
            asset=Stock(symbol="NFLX"),
            quantity=20,
            order_type=OrderType.BUY,
            price=None,  # No order price
        )

        mock_adapter = MagicMock()
        mock_quote = MagicMock()
        mock_quote.price = 450.0
        mock_adapter.get_quote.return_value = mock_quote

        self.service._simulate_leg_execution(
            account_data, leg, quote_adapter=mock_adapter
        )

        # Should use quote price
        assert account_data["cash_balance"] == 41000.0  # 50000 - 9000

    def test_simulate_leg_no_price_available(self):
        """Test leg simulation with no price available."""
        account_data = deepcopy(self.test_account_data)

        leg = OrderLeg(
            asset=Stock(symbol="UNKNOWN"),
            quantity=100,
            order_type=OrderType.BUY,
            price=None,
        )

        self.service._simulate_leg_execution(account_data, leg)

        # Should use 0.0 fill price
        assert account_data["cash_balance"] == 50000.0  # No change

    def test_simulate_leg_with_options(self):
        """Test leg simulation with options (multiplier = 100)."""
        account_data = deepcopy(self.test_account_data)

        option = Option(
            symbol="AAPL240315C00150000",
            underlying=Stock(symbol="AAPL"),
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        leg = OrderLeg(
            asset=option,
            quantity=5,  # 5 contracts
            order_type=OrderType.BTO,
            price=10.0,  # $10 per contract
        )

        self.service._simulate_leg_execution(account_data, leg)

        # Cost: 5 contracts * $10 * 100 multiplier = $5000
        assert account_data["cash_balance"] == 45000.0  # 50000 - 5000

    def test_simulate_leg_quote_adapter_no_quote(self):
        """Test leg simulation when quote adapter returns None."""
        account_data = deepcopy(self.test_account_data)

        leg = OrderLeg(
            asset=Stock(symbol="TEST"),
            quantity=100,
            order_type=OrderType.BUY,
            price=None,
        )

        mock_adapter = MagicMock()
        mock_adapter.get_quote.return_value = None

        self.service._simulate_leg_execution(
            account_data, leg, quote_adapter=mock_adapter
        )

        # Should use 0.0 price when quote is None
        assert account_data["cash_balance"] == 50000.0

    def test_simulate_leg_quote_no_price(self):
        """Test leg simulation when quote has no price."""
        account_data = deepcopy(self.test_account_data)

        leg = OrderLeg(
            asset=Stock(symbol="TEST"),
            quantity=100,
            order_type=OrderType.BUY,
            price=None,
        )

        mock_adapter = MagicMock()
        mock_quote = MagicMock()
        mock_quote.price = None
        mock_adapter.get_quote.return_value = mock_quote

        self.service._simulate_leg_execution(
            account_data, leg, quote_adapter=mock_adapter
        )

        assert account_data["cash_balance"] == 50000.0


class TestPositionUpdates(TestOrderImpactService):
    """Test _update_position_in_simulation functionality."""

    def test_update_position_create_new_stock(self):
        """Test creating new stock position."""
        account_data = {"positions": []}

        self.service._update_position_in_simulation(
            account_data, "TSLA", 100, 250.0, Stock(symbol="TSLA")
        )

        assert len(account_data["positions"]) == 1
        position = account_data["positions"][0]

        assert position["symbol"] == "TSLA"
        assert position["quantity"] == 100
        assert position["avg_price"] == 250.0
        assert position["current_price"] == 250.0
        assert position["unrealized_pnl"] == 0.0
        assert position["realized_pnl"] == 0.0

    def test_update_position_create_new_option(self):
        """Test creating new option position."""
        account_data = {"positions": []}

        option = Option(
            symbol="AAPL240315C00150000",
            underlying=Stock(symbol="AAPL"),
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        self.service._update_position_in_simulation(
            account_data, "AAPL240315C00150000", 5, 12.0, option
        )

        position = account_data["positions"][0]
        assert position["option_type"] == OptionType.CALL
        assert position["strike"] == 150.0
        assert position["expiration_date"] == date(2024, 3, 15)
        assert position["underlying_symbol"] == "AAPL"

    def test_update_position_increase_existing_dict(self):
        """Test increasing existing position (dict format)."""
        account_data = {
            "positions": [{"symbol": "AAPL", "quantity": 100, "avg_price": 150.0}]
        }

        self.service._update_position_in_simulation(
            account_data,
            "AAPL",
            50,  # Add 50 more
            160.0,  # At higher price
            Stock(symbol="AAPL"),
        )

        position = account_data["positions"][0]
        assert position["quantity"] == 150
        # Weighted average: (100 * 150 + 50 * 160) / 150 = 153.33
        expected_avg = (100 * 150.0 + 50 * 160.0) / 150
        assert abs(position["avg_price"] - expected_avg) < 1e-6

    def test_update_position_increase_existing_object(self):
        """Test increasing existing position (Position object format)."""
        existing_position = Position(
            symbol="GOOGL", quantity=50, avg_price=2800.0, current_price=2750.0
        )

        account_data = {"positions": [existing_position]}

        self.service._update_position_in_simulation(
            account_data,
            "GOOGL",
            25,  # Add 25 more
            2700.0,  # At lower price
            Stock(symbol="GOOGL"),
        )

        position = account_data["positions"][0]
        assert position.quantity == 75
        # Weighted average: (50 * 2800 + 25 * 2700) / 75 = 2766.67
        expected_avg = (50 * 2800.0 + 25 * 2700.0) / 75
        assert abs(position.avg_price - expected_avg) < 1e-6

    def test_update_position_reduce_existing(self):
        """Test reducing existing position (opposite direction)."""
        account_data = {
            "positions": [{"symbol": "MSFT", "quantity": 100, "avg_price": 380.0}]
        }

        self.service._update_position_in_simulation(
            account_data,
            "MSFT",
            -30,  # Sell 30
            385.0,  # At higher price
            Stock(symbol="MSFT"),
        )

        position = account_data["positions"][0]
        assert position["quantity"] == 70
        assert position["avg_price"] == 380.0  # Keep original average price

    def test_update_position_close_position_dict(self):
        """Test closing position completely (dict format)."""
        account_data = {
            "positions": [
                {"symbol": "IBM", "quantity": 50, "avg_price": 140.0},
                {"symbol": "INTC", "quantity": 200, "avg_price": 45.0},
            ]
        }

        self.service._update_position_in_simulation(
            account_data,
            "IBM",
            -50,  # Sell all
            145.0,
            Stock(symbol="IBM"),
        )

        # IBM position should be removed
        assert len(account_data["positions"]) == 1
        assert account_data["positions"][0]["symbol"] == "INTC"

    def test_update_position_close_position_object(self):
        """Test closing position completely (Position object format)."""
        positions = [
            Position(symbol="AMD", quantity=75, avg_price=90.0),
            Position(symbol="NVDA", quantity=25, avg_price=600.0),
        ]

        account_data = {"positions": positions}

        self.service._update_position_in_simulation(
            account_data,
            "AMD",
            -75,  # Sell all
            95.0,
            Stock(symbol="AMD"),
        )

        # AMD position should be removed
        assert len(account_data["positions"]) == 1
        assert account_data["positions"][0].symbol == "NVDA"

    def test_update_position_negative_to_positive(self):
        """Test changing from short to long position."""
        account_data = {
            "positions": [
                {
                    "symbol": "SPY",
                    "quantity": -100,  # Short position
                    "avg_price": 420.0,
                }
            ]
        }

        self.service._update_position_in_simulation(
            account_data,
            "SPY",
            150,  # Buy 150 (net +50)
            415.0,
            Stock(symbol="SPY"),
        )

        position = account_data["positions"][0]
        assert position["quantity"] == 50  # -100 + 150
        assert position["avg_price"] == 420.0  # Keep original average price


class TestPositionChangeAnalysis(TestOrderImpactService):
    """Test _analyze_position_changes functionality."""

    def test_analyze_position_changes_new_positions(self):
        """Test analysis when new positions are created."""
        before_positions = [Position(symbol="AAPL", quantity=100, avg_price=150.0)]

        after_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0),
            Position(symbol="GOOGL", quantity=50, avg_price=2750.0),
            Position(symbol="MSFT", quantity=75, avg_price=380.0),
        ]

        changes = self.service._analyze_position_changes(
            before_positions, after_positions
        )

        assert "GOOGL" in changes["new_positions"]
        assert "MSFT" in changes["new_positions"]
        assert len(changes["new_positions"]) == 2
        assert len(changes["closed_positions"]) == 0
        assert len(changes["modified_positions"]) == 0

        assert changes["summary"]["positions_opened"] == 2
        assert changes["summary"]["positions_closed"] == 0
        assert changes["summary"]["positions_modified"] == 0

    def test_analyze_position_changes_closed_positions(self):
        """Test analysis when positions are closed."""
        before_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0),
            Position(symbol="GOOGL", quantity=50, avg_price=2750.0),
            Position(symbol="MSFT", quantity=75, avg_price=380.0),
        ]

        after_positions = [Position(symbol="AAPL", quantity=100, avg_price=150.0)]

        changes = self.service._analyze_position_changes(
            before_positions, after_positions
        )

        assert "GOOGL" in changes["closed_positions"]
        assert "MSFT" in changes["closed_positions"]
        assert len(changes["closed_positions"]) == 2
        assert len(changes["new_positions"]) == 0
        assert len(changes["modified_positions"]) == 0

        assert changes["summary"]["positions_closed"] == 2

    def test_analyze_position_changes_modified_positions(self):
        """Test analysis when positions are modified."""
        before_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0),
            Position(symbol="GOOGL", quantity=50, avg_price=2750.0),
        ]

        after_positions = [
            Position(symbol="AAPL", quantity=150, avg_price=152.0),  # Increased
            Position(symbol="GOOGL", quantity=25, avg_price=2750.0),  # Decreased
        ]

        changes = self.service._analyze_position_changes(
            before_positions, after_positions
        )

        assert len(changes["modified_positions"]) == 2

        # Find AAPL change
        aapl_change = None
        googl_change = None
        for change in changes["modified_positions"]:
            if change["symbol"] == "AAPL":
                aapl_change = change
            elif change["symbol"] == "GOOGL":
                googl_change = change

        assert aapl_change["quantity_change"] == 50  # 150 - 100
        assert aapl_change["before_quantity"] == 100
        assert aapl_change["after_quantity"] == 150

        assert googl_change["quantity_change"] == -25  # 25 - 50
        assert googl_change["before_quantity"] == 50
        assert googl_change["after_quantity"] == 25

        assert changes["summary"]["positions_modified"] == 2

    def test_analyze_position_changes_mixed(self):
        """Test analysis with mixed changes."""
        before_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0),
            Position(symbol="GOOGL", quantity=50, avg_price=2750.0),
            Position(symbol="MSFT", quantity=75, avg_price=380.0),
        ]

        after_positions = [
            Position(symbol="AAPL", quantity=150, avg_price=152.0),  # Modified
            Position(symbol="TSLA", quantity=100, avg_price=250.0),  # New
            # GOOGL closed, MSFT closed
        ]

        changes = self.service._analyze_position_changes(
            before_positions, after_positions
        )

        assert len(changes["new_positions"]) == 1
        assert "TSLA" in changes["new_positions"]

        assert len(changes["closed_positions"]) == 2
        assert "GOOGL" in changes["closed_positions"]
        assert "MSFT" in changes["closed_positions"]

        assert len(changes["modified_positions"]) == 1
        assert changes["modified_positions"][0]["symbol"] == "AAPL"

        summary = changes["summary"]
        assert summary["positions_opened"] == 1
        assert summary["positions_closed"] == 2
        assert summary["positions_modified"] == 1


class TestGreeksImpact(TestOrderImpactService):
    """Test _calculate_greeks_impact functionality."""

    def create_option_position(self, symbol: str, quantity: int, **greeks) -> Position:
        """Helper to create option position with Greeks."""
        position = Position(
            symbol=symbol, quantity=quantity, avg_price=10.0, is_option=True
        )

        # Manually set Greek attributes for testing
        for greek, value in greeks.items():
            setattr(position, greek, value)

        return position

    def test_calculate_greeks_impact_new_option_position(self):
        """Test Greeks impact when adding new option positions."""
        before_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0, is_option=False)
        ]

        after_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0, is_option=False),
            self.create_option_position(
                "AAPL240315C00150000", 5, delta=0.6, gamma=0.02, theta=-0.05, vega=0.15
            ),
        ]

        greeks_impact = self.service._calculate_greeks_impact(
            before_positions, after_positions
        )

        # 5 contracts * Greek values
        assert greeks_impact["delta"] == 3.0  # 5 * 0.6
        assert greeks_impact["gamma"] == 0.1  # 5 * 0.02
        assert greeks_impact["theta"] == -0.25  # 5 * -0.05
        assert greeks_impact["vega"] == 0.75  # 5 * 0.15

    def test_calculate_greeks_impact_close_option_position(self):
        """Test Greeks impact when closing option positions."""
        before_positions = [
            self.create_option_position(
                "SPY240315P00400000",
                -3,  # Short puts
                delta=-0.4,
                gamma=0.03,
                theta=-0.08,
                vega=0.12,
            )
        ]

        after_positions = []  # Position closed

        greeks_impact = self.service._calculate_greeks_impact(
            before_positions, after_positions
        )

        # Closing -3 contracts (impact is opposite)
        assert greeks_impact["delta"] == 1.2  # -(-3 * -0.4)
        assert greeks_impact["gamma"] == -0.09  # -(−3 * 0.03)
        assert greeks_impact["theta"] == 0.24  # -(−3 * -0.08)
        assert greeks_impact["vega"] == -0.36  # -(−3 * 0.12)

    def test_calculate_greeks_impact_mixed_positions(self):
        """Test Greeks impact with multiple option positions."""
        before_positions = [
            self.create_option_position(
                "AAPL240315C00150000", 2, delta=0.6, gamma=0.02, theta=-0.05, vega=0.15
            )
        ]

        after_positions = [
            self.create_option_position(
                "AAPL240315C00150000",
                5,  # Increased position
                delta=0.6,
                gamma=0.02,
                theta=-0.05,
                vega=0.15,
            ),
            self.create_option_position(
                "AAPL240315P00150000",
                -2,  # New short puts
                delta=-0.4,
                gamma=0.02,
                theta=-0.04,
                vega=0.15,
            ),
        ]

        greeks_impact = self.service._calculate_greeks_impact(
            before_positions, after_positions
        )

        # Before: 2 * (0.6, 0.02, -0.05, 0.15) = (1.2, 0.04, -0.1, 0.3)
        # After: 5 * (0.6, 0.02, -0.05, 0.15) + (-2) * (-0.4, 0.02, -0.04, 0.15)
        #        = (3.0, 0.1, -0.25, 0.75) + (0.8, -0.04, 0.08, -0.3)
        #        = (3.8, 0.06, -0.17, 0.45)
        # Impact: (3.8, 0.06, -0.17, 0.45) - (1.2, 0.04, -0.1, 0.3) = (2.6, 0.02, -0.07, 0.15)

        assert abs(greeks_impact["delta"] - 2.6) < 1e-6
        assert abs(greeks_impact["gamma"] - 0.02) < 1e-6
        assert abs(greeks_impact["theta"] - (-0.07)) < 1e-6
        assert abs(greeks_impact["vega"] - 0.15) < 1e-6

    def test_calculate_greeks_impact_none_greeks(self):
        """Test Greeks impact with None values (treated as 0)."""
        before_positions = []

        after_positions = [
            self.create_option_position(
                "TEST240315C00100000", 1, delta=None, gamma=None, theta=None, vega=None
            )
        ]

        greeks_impact = self.service._calculate_greeks_impact(
            before_positions, after_positions
        )

        assert greeks_impact["delta"] == 0.0
        assert greeks_impact["gamma"] == 0.0
        assert greeks_impact["theta"] == 0.0
        assert greeks_impact["vega"] == 0.0

    def test_calculate_greeks_impact_non_option_positions(self):
        """Test Greeks impact ignores non-option positions."""
        before_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0, is_option=False)
        ]

        after_positions = [
            Position(symbol="AAPL", quantity=200, avg_price=155.0, is_option=False),
            Position(symbol="GOOGL", quantity=50, avg_price=2750.0, is_option=False),
        ]

        greeks_impact = self.service._calculate_greeks_impact(
            before_positions, after_positions
        )

        # Should be all zeros since no option positions
        assert greeks_impact["delta"] == 0.0
        assert greeks_impact["gamma"] == 0.0
        assert greeks_impact["theta"] == 0.0
        assert greeks_impact["vega"] == 0.0


class TestOrderValidation(TestOrderImpactService):
    """Test _validate_order functionality."""

    def test_validate_order_success(self):
        """Test successful order validation."""
        order = self.create_test_order()

        errors = self.service._validate_order(self.test_account_data, order)

        assert len(errors) == 0

    def test_validate_order_validation_error(self):
        """Test order validation with validation error."""
        mock_validator = MagicMock()
        mock_validator.validate_account_state.side_effect = ValidationError(
            "Test error"
        )

        service = OrderImpactService(validator=mock_validator)
        order = self.create_test_order()

        errors = service._validate_order(self.test_account_data, order)

        assert len(errors) == 1
        assert "Validation error: Test error" in errors[0]


class TestNakedOptionCovering(TestOrderImpactService):
    """Test _has_covering_position functionality."""

    def test_has_covering_position_underlying_stock(self):
        """Test checking for covering stock position."""
        underlying = Stock(symbol="AAPL")
        option = Option(
            symbol="AAPL240315C00150000",
            underlying=underlying,
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        positions = [
            Position(
                symbol="AAPL",
                quantity=100,  # 100+ shares to cover
                avg_price=150.0,
                is_option=False,
            )
        ]

        result = self.service._has_covering_position(option, positions)
        assert result is True

    def test_has_covering_position_insufficient_stock(self):
        """Test checking for covering position with insufficient stock."""
        underlying = Stock(symbol="AAPL")
        option = Option(
            symbol="AAPL240315C00150000",
            underlying=underlying,
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        positions = [
            Position(
                symbol="AAPL",
                quantity=50,  # Less than 100 shares
                avg_price=150.0,
                is_option=False,
            )
        ]

        result = self.service._has_covering_position(option, positions)
        assert result is False

    def test_has_covering_position_option_spread(self):
        """Test checking for covering option position."""
        underlying = Stock(symbol="AAPL")
        option = Option(
            symbol="AAPL240315C00150000",
            underlying=underlying,
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        # Mock position with proper asset structure
        covering_position = Position(
            symbol="AAPL240315C00160000", quantity=5, avg_price=8.0, is_option=True
        )

        # Mock the asset attribute
        covering_asset = Option(
            symbol="AAPL240315C00160000",
            underlying=underlying,
            option_type=OptionType.CALL,
            strike=160.0,
            expiration_date=date(2024, 3, 15),
        )
        covering_position.asset = covering_asset

        positions = [covering_position]

        result = self.service._has_covering_position(option, positions)
        assert (
            result is True
        )  # Simplified logic returns True for any option with same underlying

    def test_has_covering_position_no_covering(self):
        """Test checking for covering position with no cover."""
        underlying = Stock(symbol="AAPL")
        option = Option(
            symbol="AAPL240315C00150000",
            underlying=underlying,
            option_type=OptionType.CALL,
            strike=150.0,
            expiration_date=date(2024, 3, 15),
        )

        positions = [
            Position(
                symbol="GOOGL",  # Different underlying
                quantity=100,
                avg_price=2750.0,
                is_option=False,
            )
        ]

        result = self.service._has_covering_position(option, positions)
        assert result is False


class TestOrderTypeDescription(TestOrderImpactService):
    """Test _get_order_type_description functionality."""

    def test_get_order_type_description_single_order(self):
        """Test description for single order."""
        order = self.create_test_order(order_type=OrderType.BUY)

        description = self.service._get_order_type_description(order)
        assert description == "Single leg OrderType.BUY"

    def test_get_order_type_description_multi_leg_order(self):
        """Test description for multi-leg order."""
        legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"), quantity=100, order_type=OrderType.BUY
            ),
            OrderLeg(
                asset=Stock(symbol="GOOGL"), quantity=-50, order_type=OrderType.SELL
            ),
        ]

        multi_order = MultiLegOrder(
            id="multi_test",
            legs=legs,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        description = self.service._get_order_type_description(multi_order)
        assert description == "Multi-leg order with 2 legs"

    def test_get_order_type_description_list_of_legs(self):
        """Test description for list of legs."""
        legs = [
            OrderLeg(asset=Stock(symbol="MSFT"), quantity=75, order_type=OrderType.BUY)
        ]

        description = self.service._get_order_type_description(legs)
        assert description == "Order with 1 legs"

    def test_get_order_type_description_unknown(self):
        """Test description for unknown order type."""
        unknown_order = "not an order"

        description = self.service._get_order_type_description(unknown_order)
        assert description == "Unknown order type"


class TestEstimatedFillPrice(TestOrderImpactService):
    """Test _get_estimated_fill_price functionality."""

    def test_get_estimated_fill_price_single_order_with_override(self):
        """Test getting fill price for single order with override."""
        order = self.create_test_order(symbol="AAPL", price=155.0)
        estimated_fill_prices = {"AAPL": 157.0}

        fill_price = self.service._get_estimated_fill_price(
            order, estimated_fill_prices
        )
        assert fill_price == 157.0  # Uses override

    def test_get_estimated_fill_price_single_order_no_override(self):
        """Test getting fill price for single order without override."""
        order = self.create_test_order(symbol="GOOGL", price=2750.0)

        fill_price = self.service._get_estimated_fill_price(order, None)
        assert fill_price == 2750.0  # Uses order price

    def test_get_estimated_fill_price_multi_leg_order(self):
        """Test getting fill price for multi-leg order."""
        legs = [
            OrderLeg(
                asset=Stock(symbol="AAPL"), quantity=100, order_type=OrderType.BUY
            ),
            OrderLeg(
                asset=Stock(symbol="GOOGL"), quantity=-50, order_type=OrderType.SELL
            ),
        ]

        multi_order = MultiLegOrder(
            id="multi_test",
            legs=legs,
            net_price=25.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

        fill_price = self.service._get_estimated_fill_price(multi_order, None)
        assert fill_price == 25.0  # Uses net price

    def test_get_estimated_fill_price_unknown_type(self):
        """Test getting fill price for unknown order type."""
        unknown_order = "not an order"

        fill_price = self.service._get_estimated_fill_price(unknown_order, None)
        assert fill_price is None


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_analyze_order_impact_function(self):
        """Test analyze_order_impact convenience function."""
        account_data = {"cash_balance": 50000.0, "positions": []}

        order = Order(
            id="test",
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=155.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        analysis = analyze_order_impact(account_data, order)

        assert isinstance(analysis, OrderImpactAnalysis)
        assert analysis.order_id == "test"
        assert analysis.cash_impact == -15500.0

    def test_preview_order_impact_function(self):
        """Test preview_order_impact convenience function."""
        account_data = {"cash_balance": 50000.0, "positions": []}

        order = Order(
            id="test",
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=50,
            price=2750.0,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            condition=OrderCondition.LIMIT,
            stop_price=None,
            trail_percent=None,
            trail_amount=None,
            net_price=None,
        )

        preview = preview_order_impact(account_data, order)

        assert "estimated_cost" in preview
        assert "approval_status" in preview
        assert "buying_power_after" in preview
        assert "errors" in preview
        assert "estimated_fill" in preview

        assert preview["estimated_cost"] == 137500.0
        assert preview["approval_status"] == "approved"


class TestEdgeCases(TestOrderImpactService):
    """Test edge cases and error conditions."""

    def test_analyze_impact_with_empty_account(self):
        """Test analysis with empty account data."""
        empty_account = {"cash_balance": 0.0, "positions": []}

        order = self.create_test_order(quantity=1, price=1.0)

        analysis = self.service.analyze_order_impact(empty_account, order)

        assert analysis.before.cash_balance == 0.0
        assert len(analysis.before.positions) == 0
        assert analysis.cash_impact == -1.0

    def test_analyze_impact_large_order(self):
        """Test analysis with very large order."""
        order = self.create_test_order(quantity=1000000, price=500.0)

        analysis = self.service.analyze_order_impact(self.test_account_data, order)

        assert analysis.cash_impact == -500000000.0  # Very large negative impact

    def test_simulate_execution_with_malformed_position_data(self):
        """Test simulation with mixed position formats."""
        account_data = {
            "cash_balance": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "avg_price": 150.0},  # Dict
                Position(symbol="GOOGL", quantity=50, avg_price=2750.0),  # Object
            ],
        }

        order = self.create_test_order(symbol="MSFT", quantity=10, price=380.0)

        result = self.service._simulate_order_execution(account_data, order)

        # Should handle mixed formats gracefully
        assert result["cash_balance"] == 6200.0  # 10000 - 3800
        assert len(result["positions"]) == 3

    def test_position_update_with_zero_new_quantity(self):
        """Test position update that results in zero quantity."""
        account_data = {
            "positions": [{"symbol": "TEST", "quantity": 100, "avg_price": 50.0}]
        }

        # Sell exact amount to close position
        self.service._update_position_in_simulation(
            account_data, "TEST", -100, 55.0, Stock(symbol="TEST")
        )

        # Position should be removed
        assert len(account_data["positions"]) == 0

    def test_position_update_symbol_string_vs_asset(self):
        """Test position update handles different symbol formats."""
        account_data = {"positions": []}

        # Use asset object with symbol attribute
        asset = Stock(symbol="COMPLEX_SYMBOL")

        self.service._update_position_in_simulation(
            account_data, "COMPLEX_SYMBOL", 50, 100.0, asset
        )

        assert len(account_data["positions"]) == 1
        assert account_data["positions"][0]["symbol"] == "COMPLEX_SYMBOL"

    def test_deep_copy_preserves_complex_structures(self):
        """Test that deepcopy properly handles complex account structures."""
        complex_account = {
            "cash_balance": 50000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "avg_price": 150.0,
                    "metadata": {
                        "purchase_date": "2024-01-15",
                        "broker": "test_broker",
                    },
                }
            ],
            "settings": {"risk_tolerance": "moderate", "auto_reinvest": True},
        }

        order = self.create_test_order(symbol="GOOGL", quantity=10, price=2750.0)

        original_metadata = complex_account["positions"][0]["metadata"]

        result = self.service._simulate_order_execution(complex_account, order)

        # Original should be unchanged
        assert complex_account["positions"][0]["metadata"] == original_metadata
        assert complex_account["cash_balance"] == 50000.0

        # Result should have changes
        assert result["cash_balance"] == 22500.0  # 50000 - 27500
        assert len(result["positions"]) == 2
