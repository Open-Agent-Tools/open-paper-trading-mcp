"""
Test suite for Order Impact Analysis service.
"""

from unittest.mock import Mock

from app.services.order_impact import (
    OrderImpactService,
    OrderImpactAnalysis,
    AccountSnapshot,
)
from app.models.trading import Order, MultiLegOrder, OrderType, Position
from app.models.assets import asset_factory


class TestOrderImpactService:
    """Test order impact analysis functionality."""

    def setup_method(self):
        """Set up test service and mock data."""
        self.service = OrderImpactService()

        # Mock account data
        self.mock_account = {
            "cash_balance": 10000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 10,
                    "avg_price": 150.0,
                    "current_price": 155.0,
                    "unrealized_pnl": 50.0,
                    "realized_pnl": 0.0,
                }
            ],
            "orders": [],
        }

        # Mock quote adapter
        self.mock_quote_adapter = Mock()
        mock_quote = Mock()
        mock_quote.price = 155.0
        self.mock_quote_adapter.get_quote.return_value = mock_quote

    def test_service_initialization(self):
        """Test service initializes correctly."""
        assert self.service.margin_service is not None
        assert self.service.validator is not None

    def test_create_account_snapshot(self):
        """Test account snapshot creation."""
        snapshot = self.service._create_account_snapshot(
            self.mock_account, self.mock_quote_adapter
        )

        assert isinstance(snapshot, AccountSnapshot)
        assert snapshot.cash_balance == 10000.0
        assert len(snapshot.positions) == 1
        assert snapshot.total_value > 0
        assert snapshot.buying_power >= 0

    def test_analyze_simple_order_impact(self):
        """Test impact analysis for simple order."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=5, price=160.0)

        analysis = self.service.analyze_order_impact(
            self.mock_account, order, self.mock_quote_adapter
        )

        assert isinstance(analysis, OrderImpactAnalysis)
        assert analysis.order_type == "Single leg buy"
        assert analysis.cash_impact < 0  # Buying should reduce cash
        assert analysis.approval_status in ["approved", "warning", "rejected"]
        assert isinstance(analysis.before, AccountSnapshot)
        assert isinstance(analysis.after, AccountSnapshot)

    def test_analyze_multileg_order_impact(self):
        """Test impact analysis for multi-leg order."""
        multileg_order = MultiLegOrder(legs=[])
        multileg_order.buy_to_open("AAPL240119C00195000", 1, 5.50)
        multileg_order.sell_to_open("AAPL240119C00200000", 1, 3.25)

        # Mock option quotes
        mock_option_quote = Mock()
        mock_option_quote.price = 5.00
        self.mock_quote_adapter.get_quote.return_value = mock_option_quote

        analysis = self.service.analyze_order_impact(
            self.mock_account, multileg_order, self.mock_quote_adapter
        )

        assert isinstance(analysis, OrderImpactAnalysis)
        assert "multi-leg" in analysis.order_type.lower()
        assert analysis.cash_impact != 0  # Should have some cash impact

    def test_order_preview(self):
        """Test order preview functionality."""
        order = Order(symbol="AAPL", order_type=OrderType.SELL, quantity=5, price=160.0)

        preview = self.service.preview_order(
            self.mock_account, order, self.mock_quote_adapter
        )

        assert isinstance(preview, dict)
        assert "estimated_cost" in preview
        assert "approval_status" in preview
        assert "buying_power_after" in preview
        assert "warnings" in preview
        assert "errors" in preview

    def test_simulate_order_execution(self):
        """Test order execution simulation."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=5, price=160.0)

        simulated_account = self.service._simulate_order_execution(
            self.mock_account, order, self.mock_quote_adapter
        )

        # Cash should be reduced
        assert simulated_account["cash_balance"] < self.mock_account["cash_balance"]

        # Should have updated positions
        positions = simulated_account["positions"]
        aapl_position = next(
            (p for p in positions if p.get("symbol", p.symbol) == "AAPL"), None
        )
        assert aapl_position is not None

    def test_position_changes_analysis(self):
        """Test position changes analysis."""
        before_positions = [
            Position(symbol="AAPL", quantity=10, avg_price=150.0, current_price=155.0)
        ]

        after_positions = [
            Position(symbol="AAPL", quantity=15, avg_price=152.0, current_price=155.0),
            Position(
                symbol="GOOGL", quantity=5, avg_price=2800.0, current_price=2850.0
            ),
        ]

        changes = self.service._analyze_position_changes(
            before_positions, after_positions
        )

        assert isinstance(changes, dict)
        assert "new_positions" in changes
        assert "modified_positions" in changes
        assert "summary" in changes

        assert "GOOGL" in changes["new_positions"]
        assert len(changes["modified_positions"]) == 1
        assert changes["modified_positions"][0]["symbol"] == "AAPL"

    def test_greeks_impact_calculation(self):
        """Test Greeks impact calculation."""
        before_positions = [
            Position(
                symbol="AAPL240119C00195000",
                quantity=1,
                avg_price=5.50,
                current_price=6.00,
                delta=65.0,
                gamma=3.0,
                asset=asset_factory("AAPL240119C00195000"),
            )
        ]

        after_positions = [
            Position(
                symbol="AAPL240119C00195000",
                quantity=2,
                avg_price=5.75,
                current_price=6.00,
                delta=130.0,
                gamma=6.0,
                asset=asset_factory("AAPL240119C00195000"),
            )
        ]

        greeks_impact = self.service._calculate_greeks_impact(
            before_positions, after_positions
        )

        assert isinstance(greeks_impact, dict)
        assert "delta" in greeks_impact
        assert "gamma" in greeks_impact
        assert "theta" in greeks_impact
        assert "vega" in greeks_impact

        assert greeks_impact["delta"] == 65.0  # 130 - 65
        assert greeks_impact["gamma"] == 3.0  # 6 - 3

    def test_risk_assessment(self):
        """Test risk assessment functionality."""
        # Create account that will trigger warnings
        risky_account = {"cash_balance": 1000.0, "positions": []}  # Low cash

        before_snapshot = self.service._create_account_snapshot(
            risky_account, self.mock_quote_adapter
        )

        # Simulate large order
        large_order = Order(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,  # Large quantity
            price=160.0,
        )

        after_account = self.service._simulate_order_execution(
            risky_account, large_order, self.mock_quote_adapter
        )
        after_snapshot = self.service._create_account_snapshot(
            after_account, self.mock_quote_adapter
        )

        warnings = self.service._assess_risks(
            before_snapshot, after_snapshot, large_order
        )

        assert isinstance(warnings, list)
        # Should have warnings about negative cash or low buying power
        warning_text = " ".join(warnings).lower()
        assert "cash" in warning_text or "buying power" in warning_text

    def test_options_risk_assessment(self):
        """Test options-specific risk assessment."""
        # Create short option order
        option_order = MultiLegOrder(legs=[])
        option_order.sell_to_open("AAPL240119C00195000", 1, 5.50)  # Naked call

        before_snapshot = self.service._create_account_snapshot(
            self.mock_account, self.mock_quote_adapter
        )
        after_account = self.service._simulate_order_execution(
            self.mock_account, option_order, self.mock_quote_adapter
        )
        after_snapshot = self.service._create_account_snapshot(
            after_account, self.mock_quote_adapter
        )

        warnings = self.service._assess_risks(
            before_snapshot, after_snapshot, option_order
        )

        # Should warn about naked option
        warning_text = " ".join(warnings).lower()
        assert "naked" in warning_text or "unlimited risk" in warning_text

    def test_validation_integration(self):
        """Test integration with validation service."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=5, price=160.0)

        errors = self.service._validate_order(
            self.mock_account, order, self.mock_quote_adapter
        )

        assert isinstance(errors, list)
        # Should not have errors for valid order

    def test_estimated_fill_prices(self):
        """Test order analysis with estimated fill prices."""
        order = Order(symbol="AAPL", order_type=OrderType.BUY, quantity=5, price=160.0)
        estimated_fill_prices = {"AAPL": 158.0}  # Different from order price

        analysis = self.service.analyze_order_impact(
            self.mock_account, order, self.mock_quote_adapter, estimated_fill_prices
        )

        assert analysis.estimated_fill_price == 158.0
        # Cash impact should reflect the estimated price, not order price

    def test_order_type_descriptions(self):
        """Test order type description generation."""
        # Single order
        single_order = Order(
            symbol="AAPL", order_type=OrderType.BUY, quantity=5, price=160.0
        )
        desc = self.service._get_order_type_description(single_order)
        assert "single leg" in desc.lower()
        assert "buy" in desc.lower()

        # Multi-leg order
        multileg_order = MultiLegOrder(legs=[])
        multileg_order.buy_to_open("AAPL", 10, 160.0)
        multileg_order.sell_to_open("AAPL240119C00195000", 1, 5.50)

        desc = self.service._get_order_type_description(multileg_order)
        assert "multi-leg" in desc.lower()
        assert "2 legs" in desc.lower()

    def test_covering_position_detection(self):
        """Test detection of covering positions for naked options."""
        option = asset_factory("AAPL240119C00195000")

        # Positions with sufficient stock to cover
        covering_positions = [
            Position(symbol="AAPL", quantity=100, avg_price=150.0, current_price=155.0)
        ]

        assert self.service._has_covering_position(option, covering_positions)

        # Positions without sufficient stock
        insufficient_positions = [
            Position(symbol="AAPL", quantity=50, avg_price=150.0, current_price=155.0)
        ]

        assert not self.service._has_covering_position(option, insufficient_positions)

        # No covering positions
        assert not self.service._has_covering_position(option, [])


class TestOrderImpactAnalysis:
    """Test OrderImpactAnalysis model."""

    def test_impact_analysis_creation(self):
        """Test impact analysis model creation."""
        before_snapshot = AccountSnapshot(
            cash_balance=10000.0,
            positions=[],
            total_value=10000.0,
            buying_power=10000.0,
        )

        after_snapshot = AccountSnapshot(
            cash_balance=9200.0, positions=[], total_value=9200.0, buying_power=9200.0
        )

        analysis = OrderImpactAnalysis(
            order_type="Single leg buy",
            before=before_snapshot,
            after=after_snapshot,
            cash_impact=-800.0,
            margin_impact=0.0,
            buying_power_impact=-800.0,
            approval_status="approved",
        )

        assert analysis.cash_impact == -800.0
        assert analysis.approval_status == "approved"
        assert analysis.before.cash_balance == 10000.0
        assert analysis.after.cash_balance == 9200.0
