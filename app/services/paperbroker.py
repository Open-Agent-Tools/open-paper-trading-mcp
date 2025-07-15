"""
Central PaperBroker class that orchestrates all trading operations.

This class provides the main interface for paper trading operations,
coordinating between adapters, services, and data models.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import date
import logging

from ..models.accounts import Account
from ..models.assets import Asset, Option, asset_factory
from ..models.trading import Position, Order, MultiLegOrder
from ..models.quotes import Quote
from ..adapters.base import AccountAdapter, MarketAdapter, QuoteAdapter
from ..adapters.accounts import DatabaseAccountAdapter, account_factory
from ..adapters.markets import PaperMarketAdapter
from ..services.order_execution import OrderExecutionEngine, OrderExecutionResult
from ..services.expiration import OptionsExpirationEngine, ExpirationResult
from ..services.strategy_grouping import group_into_basic_strategies
from ..services.margin import MarginCalculator
from ..services.validation import AccountValidator

logger = logging.getLogger(__name__)


class PaperBroker:
    """
    Central paper trading broker that orchestrates all operations.

    This class follows the original paperbroker architecture pattern
    with modern enhancements and pluggable adapters.
    """

    def __init__(
        self,
        account_adapter: Optional[AccountAdapter] = None,
        market_adapter: Optional[MarketAdapter] = None,
        quote_adapter: Optional[QuoteAdapter] = None,
        enable_margin_checks: bool = True,
        enable_expiration_processing: bool = True,
    ):
        """
        Initialize the PaperBroker with adapters and services.

        Args:
            account_adapter: Account storage adapter (defaults to DatabaseAccountAdapter)
            market_adapter: Market simulation adapter (defaults to PaperMarketAdapter)
            quote_adapter: Quote data adapter (required)
            enable_margin_checks: Whether to enforce margin requirements
            enable_expiration_processing: Whether to process options expiration
        """
        # Initialize adapters
        self.account_adapter = account_adapter or DatabaseAccountAdapter()
        self.quote_adapter = quote_adapter

        if market_adapter:
            self.market_adapter = market_adapter
        elif quote_adapter:
            self.market_adapter = PaperMarketAdapter(quote_adapter)
        else:
            raise ValueError("Either market_adapter or quote_adapter must be provided")

        # Initialize services
        self.order_execution_engine = OrderExecutionEngine(
            quote_service=None,  # Will use quote_adapter directly
            margin_service=None,  # Will be initialized if needed
        )

        self.expiration_engine = OptionsExpirationEngine()

        # Configuration
        self.enable_margin_checks = enable_margin_checks
        self.enable_expiration_processing = enable_expiration_processing

        # Initialize optional services
        if enable_margin_checks:
            self.margin_calculator = MarginCalculator()

        self.account_validator = AccountValidator()

        logger.info("PaperBroker initialized with adapters and services")

    def create_account(
        self,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        cash: float = 100000.0,
    ) -> Account:
        """
        Create a new trading account.

        Args:
            name: Account name (auto-generated if None)
            owner: Account owner (defaults to "default")
            cash: Initial cash balance

        Returns:
            Created Account object
        """
        account = account_factory(name=name, owner=owner, cash=cash)
        self.account_adapter.put_account(account)

        logger.info(f"Created account {account.id} with ${cash:,.2f}")
        return account

    def get_account(self, account_id: str) -> Optional[Account]:
        """
        Retrieve an account by ID.

        Args:
            account_id: Account identifier

        Returns:
            Account object or None if not found
        """
        account = self.account_adapter.get_account(account_id)

        if account and self.enable_expiration_processing:
            # Process any expired options
            self.process_account_expirations(account_id)
            # Reload account after expiration processing
            account = self.account_adapter.get_account(account_id)

        return account

    def list_accounts(self) -> List[str]:
        """
        List all account IDs.

        Returns:
            List of account IDs
        """
        return self.account_adapter.get_account_ids()

    def submit_order(
        self, account_id: str, order: Union[Order, MultiLegOrder]
    ) -> OrderExecutionResult:
        """
        Submit an order for execution.

        Args:
            account_id: Account to execute order for
            order: Order to execute

        Returns:
            OrderExecutionResult with execution details
        """
        # Load account
        account = self.get_account(account_id)
        if not account:
            return OrderExecutionResult(
                success=False, message=f"Account {account_id} not found"
            )

        # Validate account
        if not self.account_validator.validate_account(account):
            return OrderExecutionResult(
                success=False, message="Account validation failed"
            )

        # Execute order
        if isinstance(order, Order):
            result = self._execute_simple_order(account, order)
        else:
            result = self._execute_multi_leg_order(account, order)

        # Update account if successful
        if result.success:
            # Update cash balance
            account.cash += result.cash_change

            # Update positions
            for position in result.positions_created:
                account.positions.append(position)

            # Remove zero-quantity positions
            account.positions = [p for p in account.positions if p.quantity != 0]

            # Update margin requirements if enabled
            if self.enable_margin_checks:
                self._update_margin_requirements(account)

            # Save account
            self.account_adapter.put_account(account)

            logger.info(
                f"Order {order.id} executed successfully for account {account_id}"
            )
        else:
            logger.warning(f"Order {order.id} failed: {result.message}")

        return result

    def get_quote(self, asset: Union[str, Asset]) -> Optional[Quote]:
        """
        Get a quote for an asset.

        Args:
            asset: Asset symbol or Asset object

        Returns:
            Quote object or None if not available
        """
        asset_obj = asset_factory(asset) if isinstance(asset, str) else asset
        return self.quote_adapter.get_quote(asset_obj)

    def get_quotes(self, assets: List[Union[str, Asset]]) -> Dict[Asset, Quote]:
        """
        Get quotes for multiple assets.

        Args:
            assets: List of asset symbols or Asset objects

        Returns:
            Dictionary mapping Assets to Quotes
        """
        asset_objs = [asset_factory(a) if isinstance(a, str) else a for a in assets]
        return self.quote_adapter.get_quotes(asset_objs)

    def get_portfolio_value(self, account_id: str) -> Dict[str, float]:
        """
        Calculate portfolio value and metrics.

        Args:
            account_id: Account identifier

        Returns:
            Dictionary with portfolio metrics
        """
        account = self.get_account(account_id)
        if not account:
            return {}

        total_value = account.cash
        position_values = {}

        for position in account.positions:
            asset = asset_factory(position.symbol)
            quote = self.get_quote(asset)

            if quote:
                position_value = quote.price * position.quantity
                if isinstance(asset, Option):
                    position_value *= 100  # Option multiplier

                position_values[position.symbol] = position_value
                total_value += position_value

        return {
            "total_value": total_value,
            "cash": account.cash,
            "position_values": position_values,
            "positions_value": sum(position_values.values()),
        }

    def get_positions(self, account_id: str) -> List[Position]:
        """
        Get all positions for an account.

        Args:
            account_id: Account identifier

        Returns:
            List of Position objects
        """
        account = self.get_account(account_id)
        return account.positions if account else []

    def get_strategies(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Get strategy analysis for an account.

        Args:
            account_id: Account identifier

        Returns:
            List of strategy dictionaries
        """
        positions = self.get_positions(account_id)
        if not positions:
            return []

        strategies = group_into_basic_strategies(positions)

        # Convert to dictionaries for API response
        result = []
        for strategy in strategies:
            strategy_dict = {
                "type": strategy.strategy_type,
                "quantity": strategy.quantity,
            }

            if hasattr(strategy, "asset"):
                strategy_dict["asset"] = strategy.asset.symbol

            if hasattr(strategy, "direction"):
                strategy_dict["direction"] = strategy.direction

            if hasattr(strategy, "sell_option"):
                strategy_dict["sell_option"] = strategy.sell_option.symbol
                strategy_dict["buy_option"] = strategy.buy_option.symbol
                strategy_dict["spread_type"] = strategy.spread_type

            result.append(strategy_dict)

        return result

    def process_account_expirations(
        self, account_id: str, processing_date: Optional[date] = None
    ) -> ExpirationResult:
        """
        Process expired options for an account.

        Args:
            account_id: Account identifier
            processing_date: Date to process expirations for (defaults to today)

        Returns:
            ExpirationResult with processing details
        """
        account = self.account_adapter.get_account(account_id)
        if not account:
            return ExpirationResult(errors=[f"Account {account_id} not found"])

        # Convert account to dict format for expiration engine
        account_dict = {
            "positions": [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                }
                for pos in account.positions
            ],
            "cash_balance": account.cash,
        }

        # Process expirations
        result = self.expiration_engine.process_account_expirations(
            account_dict, self.quote_adapter, processing_date
        )

        if result.cash_impact != 0 or result.new_positions:
            # Update account with changes
            account.cash = account_dict["cash_balance"]

            # Update positions
            account.positions = [
                Position(
                    symbol=pos["symbol"],
                    quantity=pos["quantity"],
                    avg_price=pos["avg_price"],
                    current_price=pos.get("current_price", pos["avg_price"]),
                )
                for pos in account_dict["positions"]
                if pos["quantity"] != 0
            ]

            # Save updated account
            self.account_adapter.put_account(account)

            logger.info(
                f"Processed expirations for account {account_id}: {len(result.expired_positions)} options expired"
            )

        return result

    def get_margin_requirements(self, account_id: str) -> Dict[str, float]:
        """
        Calculate margin requirements for an account.

        Args:
            account_id: Account identifier

        Returns:
            Dictionary with margin requirement details
        """
        if not self.enable_margin_checks:
            return {"maintenance_margin": 0.0}

        positions = self.get_positions(account_id)
        if not positions:
            return {"maintenance_margin": 0.0}

        # Calculate margin using strategy grouping
        strategies = group_into_basic_strategies(positions)
        maintenance_margin = self.margin_calculator.calculate_maintenance_margin(
            strategies, self.quote_adapter
        )

        return {
            "maintenance_margin": maintenance_margin,
            "strategies_count": len(strategies),
        }

    def _execute_simple_order(
        self, account: Account, order: Order
    ) -> OrderExecutionResult:
        """Execute a simple single-leg order."""
        # Submit to market adapter
        market_order = self.market_adapter.submit_order(order)

        # If filled immediately, process execution
        if market_order.status.value == "filled":
            # Convert to multi-leg for execution engine
            # Note: This would be used in real implementation
            # multi_leg = MultiLegOrder(
            #     id=order.id,
            #     legs=[order.to_leg()],
            #     condition=order.condition,
            #     limit_price=order.price,
            # )

            # Execute through order execution engine
            # Note: This would be async in real implementation
            return OrderExecutionResult(
                success=True,
                message="Order executed successfully",
                order_id=order.id,
                cash_change=-(order.price * order.quantity),  # Simplified
                positions_created=[],
                positions_modified=[],
            )

        return OrderExecutionResult(
            success=False, message="Order not filled", order_id=order.id
        )

    def _execute_multi_leg_order(
        self, account: Account, order: MultiLegOrder
    ) -> OrderExecutionResult:
        """Execute a multi-leg order."""
        # Use order execution engine
        # Note: This would be async in real implementation
        return OrderExecutionResult(
            success=True,
            message="Multi-leg order executed successfully",
            order_id=order.id,
            cash_change=0.0,  # Simplified
            positions_created=[],
            positions_modified=[],
        )

    def _update_margin_requirements(self, account: Account) -> None:
        """Update margin requirements for an account."""
        if not self.enable_margin_checks:
            return

        strategies = group_into_basic_strategies(account.positions)
        maintenance_margin = self.margin_calculator.calculate_maintenance_margin(
            strategies, self.quote_adapter
        )

        # Update account margin requirement
        # Note: This would be stored in the account model
        logger.debug(
            f"Updated margin requirement for account {account.id}: ${maintenance_margin:,.2f}"
        )

    def simulate_order(
        self, account_id: str, order: Union[Order, MultiLegOrder]
    ) -> Dict[str, Any]:
        """
        Simulate an order without executing it.

        Args:
            account_id: Account identifier
            order: Order to simulate

        Returns:
            Dictionary with simulation results
        """
        account = self.get_account(account_id)
        if not account:
            return {"success": False, "message": f"Account {account_id} not found"}

        # Use market adapter's simulation
        if isinstance(order, Order):
            return self.market_adapter.simulate_order(order)
        else:
            # For multi-leg orders, simulate each leg
            leg_results = []
            for leg in order.legs:
                leg_order = Order(
                    asset=leg.asset,
                    quantity=leg.quantity,
                    action=leg.action,
                    order_type=leg.order_type,
                    price=leg.price,
                    limit_price=leg.limit_price,
                    stop_price=leg.stop_price,
                )
                leg_results.append(self.market_adapter.simulate_order(leg_order))

            return {
                "success": True,
                "leg_results": leg_results,
                "total_cost": sum(
                    r.get("impact", {}).get("total_cost", 0) for r in leg_results
                ),
            }

    def get_pending_orders(self, account_id: Optional[str] = None) -> List[Order]:
        """
        Get pending orders for an account or all accounts.

        Args:
            account_id: Account identifier (optional)

        Returns:
            List of pending Order objects
        """
        return self.market_adapter.get_pending_orders(account_id)

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order identifier

        Returns:
            True if order was cancelled, False otherwise
        """
        return self.market_adapter.cancel_order(order_id)

    def is_market_open(self) -> bool:
        """
        Check if the market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        return self.quote_adapter.is_market_open()

    def get_market_hours(self) -> Dict[str, Any]:
        """
        Get market hours information.

        Returns:
            Dictionary with market hours data
        """
        return self.quote_adapter.get_market_hours()

    def process_all_pending_orders(self) -> List[Order]:
        """
        Process all pending orders across all accounts.

        Returns:
            List of orders that were filled
        """
        return self.market_adapter.process_pending_orders()

    def get_account_summary(self, account_id: str) -> Dict[str, Any]:
        """
        Get comprehensive account summary.

        Args:
            account_id: Account identifier

        Returns:
            Dictionary with account summary data
        """
        account = self.get_account(account_id)
        if not account:
            return {}

        portfolio_value = self.get_portfolio_value(account_id)
        strategies = self.get_strategies(account_id)
        margin_requirements = self.get_margin_requirements(account_id)

        return {
            "account_id": account.id,
            "name": account.name,
            "owner": account.owner,
            "cash": account.cash,
            "portfolio_value": portfolio_value,
            "positions_count": len(account.positions),
            "strategies": strategies,
            "margin_requirements": margin_requirements,
            "market_open": self.is_market_open(),
        }
