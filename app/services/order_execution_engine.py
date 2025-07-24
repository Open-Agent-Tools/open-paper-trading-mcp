"""
Order Execution Engine for advanced order management.

This module implements a persistent, background service that monitors market data
and executes orders when trigger conditions are met. It operates independently
of the API request/response cycle and handles sophisticated order types.
"""

import asyncio
import contextlib
import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC
from typing import Any, cast

from sqlalchemy import and_, select

from ..models.assets import asset_factory
from ..models.database.trading import Order as DBOrder
from ..schemas.orders import Order, OrderCondition, OrderStatus, OrderType
from ..services.order_conversion import order_converter
from ..services.trading_service import TradingService, _get_quote_adapter
from ..storage.database import get_async_session

logger = logging.getLogger(__name__)


class OrderExecutionError(Exception):
    """Error during order execution."""

    pass


class TriggerCondition:
    """Represents a trigger condition for an order."""

    def __init__(
        self,
        order_id: str,
        symbol: str,
        trigger_type: str,
        trigger_price: float,
        order_type: OrderType,
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.trigger_type = trigger_type  # 'stop_loss', 'stop_limit', 'trailing_stop'
        self.trigger_price = trigger_price
        self.order_type = order_type
        self.created_at = datetime.now(UTC)
        self.high_water_mark: float | None = None  # For trailing stops
        self.low_water_mark: float | None = None  # For trailing stops

    def should_trigger(self, current_price: float) -> bool:
        """Check if current price should trigger this condition."""
        if self.trigger_type in ["stop_loss", "stop_limit"]:
            # For stop loss: SELL orders trigger when price drops below trigger
            # For stop limit: same logic
            if self.order_type == OrderType.SELL:
                return current_price <= self.trigger_price
            else:  # BUY order
                return current_price >= self.trigger_price

        elif self.trigger_type == "trailing_stop":
            # For trailing stops, the trigger price is updated dynamically
            if self.order_type == OrderType.SELL:
                return current_price <= self.trigger_price
            else:
                return current_price >= self.trigger_price

        return False

    def update_trailing_stop(self, current_price: float, order: "Order") -> bool:
        """Update trailing stop trigger price. Returns True if updated."""
        if self.trigger_type != "trailing_stop":
            return False

        is_sell_order = order.quantity < 0
        updated = False

        if order.trail_percent is not None:
            # Percentage-based trailing
            if is_sell_order:
                # Trail below the high water mark
                if self.high_water_mark is None or current_price > self.high_water_mark:
                    self.high_water_mark = current_price
                    new_trigger = current_price * (1 - order.trail_percent / 100)
                    if new_trigger > self.trigger_price:
                        self.trigger_price = new_trigger
                        updated = True
            else:
                # Trail above the low water mark
                if self.low_water_mark is None or current_price < self.low_water_mark:
                    self.low_water_mark = current_price
                    new_trigger = current_price * (1 + order.trail_percent / 100)
                    if new_trigger < self.trigger_price:
                        self.trigger_price = new_trigger
                        updated = True

        elif order.trail_amount is not None:
            # Dollar amount-based trailing
            if is_sell_order:
                if self.high_water_mark is None or current_price > self.high_water_mark:
                    self.high_water_mark = current_price
                    new_trigger = current_price - order.trail_amount
                    if new_trigger > self.trigger_price:
                        self.trigger_price = new_trigger
                        updated = True
            else:
                if self.low_water_mark is None or current_price < self.low_water_mark:
                    self.low_water_mark = current_price
                    new_trigger = current_price + order.trail_amount
                    if new_trigger < self.trigger_price:
                        self.trigger_price = new_trigger
                        updated = True

        return updated


class OrderExecutionEngine:
    """
    Persistent background service for order execution and monitoring.

    This engine runs independently of the API layer and continuously monitors
    market data to execute orders when trigger conditions are met.
    """

    def __init__(self, trading_service: TradingService):
        self.trading_service = trading_service
        self.is_running = False
        self.monitoring_task: asyncio.Task[None] | None = None
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Track trigger conditions by symbol
        self.trigger_conditions: dict[str, list[TriggerCondition]] = defaultdict(list)
        self.monitored_symbols: set[str] = set()

        # Performance tracking
        self.orders_processed = 0
        self.orders_triggered = 0
        self.last_market_data_update = datetime.now(UTC)

        # Thread safety
        self._lock = threading.Lock()

    async def add_trigger_order(self, order: Order) -> None:
        """Add a trigger order for monitoring (async version for tests)."""
        await self.add_order(order)

    def _should_trigger(
        self, condition: TriggerCondition, current_price: float
    ) -> bool:
        """Check if a trigger condition should fire."""
        return condition.should_trigger(current_price)

    async def start(self) -> None:
        """Start the order execution engine."""
        if self.is_running:
            logger.warning("Order execution engine is already running")
            return

        logger.info("Starting Order Execution Engine...")
        self.is_running = True

        # Load existing orders from database
        await self._load_pending_orders()

        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info(
            f"Order Execution Engine started. Monitoring {len(self.monitored_symbols)} symbols"
        )

    async def stop(self) -> None:
        """Stop the order execution engine."""
        if not self.is_running:
            return

        logger.info("Stopping Order Execution Engine...")
        self.is_running = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitoring_task

        self.executor.shutdown(wait=True)
        logger.info("Order Execution Engine stopped")

    async def add_order(self, order: Order) -> None:
        """Add an order to be monitored for execution."""
        if not order_converter.can_convert_order(order):
            logger.debug(
                f"Order {order.id} is not a trigger order, skipping monitoring"
            )
            return

        try:
            order_converter.validate_order_for_conversion(order)
        except Exception as e:
            logger.error(f"Order {order.id} failed validation: {e}")
            raise OrderExecutionError(f"Invalid order for monitoring: {e}")

        with self._lock:
            # Create trigger condition
            condition_type = order.order_type.value
            trigger_price = self._get_initial_trigger_price(order)

            # Determine order type for trigger condition
            if order.order_type in [OrderType.STOP_LOSS, OrderType.TRAILING_STOP]:
                trigger_order_type = OrderType.SELL  # Stop losses are usually sells
            else:
                trigger_order_type = (
                    OrderType.SELL if order.quantity > 0 else OrderType.BUY
                )

            condition = TriggerCondition(
                order_id=str(order.id),
                symbol=order.symbol,
                trigger_type=condition_type,
                trigger_price=trigger_price,
                order_type=trigger_order_type,
            )

            # Add to monitoring
            self.trigger_conditions[order.symbol].append(condition)
            self.monitored_symbols.add(order.symbol)

        logger.info(
            f"Added order {order.id} to monitoring: {order.order_type} {order.symbol}"
        )

    async def remove_order(self, order_id: str) -> None:
        """Remove an order from monitoring."""
        with self._lock:
            for symbol, conditions in self.trigger_conditions.items():
                self.trigger_conditions[symbol] = [
                    c for c in conditions if c.order_id != order_id
                ]

            # Clean up empty symbol lists
            empty_symbols = [
                s for s, conditions in self.trigger_conditions.items() if not conditions
            ]
            for symbol in empty_symbols:
                del self.trigger_conditions[symbol]
                self.monitored_symbols.discard(symbol)

        logger.info(f"Removed order {order_id} from monitoring")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that checks trigger conditions."""
        logger.info("Starting order monitoring loop")

        while self.is_running:
            try:
                await self._check_trigger_conditions()
                await asyncio.sleep(1.0)  # Check every second
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)  # Back off on error

        logger.info("Order monitoring loop stopped")

    async def _check_trigger_conditions(
        self, symbol: str | None = None, price: float | None = None
    ) -> None:
        """Check all trigger conditions against current market data."""
        logger.debug(
            f"_check_trigger_conditions called with symbol={symbol}, price={price}"
        )
        logger.debug(f"Monitored symbols: {self.monitored_symbols}")

        if not self.monitored_symbols:
            logger.debug("No monitored symbols, returning early")
            return

        try:
            # Get current market data for all monitored symbols
            quote_adapter = _get_quote_adapter()
            triggered_orders = []

            # If specific symbol and price provided (for testing), use those
            if symbol and price:
                symbols_to_check = [symbol] if symbol in self.monitored_symbols else []
                price_lookup = {symbol: price}
            else:
                symbols_to_check = list(
                    self.monitored_symbols
                )  # Copy to avoid modification during iteration
                price_lookup = {}

            for symbol in symbols_to_check:
                try:
                    # Use provided price or get from market data
                    if symbol in price_lookup:
                        current_price = price_lookup[symbol]
                        logger.debug(
                            f"Using provided price for {symbol}: {current_price}"
                        )
                    else:
                        asset = asset_factory(symbol)
                        if not asset:
                            continue

                        quote = await quote_adapter.get_quote(asset)
                        if not quote or quote.price is None:
                            continue

                        current_price = quote.price

                    with self._lock:
                        conditions = self.trigger_conditions.get(symbol, [])
                        logger.debug(f"Found {len(conditions)} conditions for {symbol}")

                        for condition in conditions[
                            :
                        ]:  # Copy list to allow modification
                            logger.debug(
                                f"Checking condition: {condition.trigger_type} at trigger={condition.trigger_price}, current={current_price}"
                            )

                            # Update trailing stops (we need to find the original order)
                            if condition.trigger_type == "trailing_stop":
                                # For now, skip trailing stop updates since we need the original order
                                # TODO: Store reference to original order in TriggerCondition
                                pass

                            # Check if should trigger
                            should_trigger = condition.should_trigger(current_price)
                            logger.debug(f"Should trigger: {should_trigger}")

                            if should_trigger:
                                triggered_orders.append((condition, current_price))
                                logger.info(
                                    f"Order {condition.order_id} triggered at price {current_price}"
                                )

                                # Remove from monitoring
                                conditions.remove(condition)
                                if not conditions:
                                    self.monitored_symbols.discard(symbol)

                except Exception as e:
                    logger.error(f"Error checking conditions for {symbol}: {e}")
                    continue

            # Process triggered orders
            for condition, trigger_price in triggered_orders:
                await self._process_triggered_order(condition, trigger_price)

            self.last_market_data_update = datetime.now(UTC)

        except Exception as e:
            logger.error(f"Error in check_trigger_conditions: {e}", exc_info=True)

    async def _process_triggered_order(
        self, condition: TriggerCondition, trigger_price: float
    ) -> None:
        """Process a triggered order by converting and executing it."""
        try:
            logger.info(
                f"Processing triggered order: {condition.order_id} at price {trigger_price}"
            )

            # First, load the original order from database
            original_order = await self._load_order_by_id(condition.order_id)
            if not original_order:
                logger.error(f"Could not load original order {condition.order_id}")
                return

            # Convert the order
            converted_order: Order | None = None
            if condition.trigger_type == "stop_loss":
                converted_order = order_converter.convert_stop_loss_to_market(
                    original_order, trigger_price
                )
            elif condition.trigger_type == "stop_limit":
                converted_order = order_converter.convert_stop_limit_to_limit(
                    original_order, trigger_price
                )
            elif condition.trigger_type == "trailing_stop":
                converted_order = order_converter.convert_trailing_stop_to_market(
                    original_order, trigger_price
                )

            if converted_order:
                # Update original order status in database
                await self._update_order_triggered_status(
                    condition.order_id, trigger_price
                )

                # Execute the converted order
                await self._execute_converted_order(converted_order)

                self.orders_triggered += 1
                logger.info(
                    f"Successfully processed triggered order {condition.order_id}"
                )

        except Exception as e:
            logger.error(
                f"Error processing triggered order {condition.order_id}: {e}",
                exc_info=True,
            )
            # Could implement retry logic or dead letter queue here

    async def _load_order_by_id(self, order_id: str) -> Order | None:
        """Load an order from the database by ID."""
        try:
            async for db in get_async_session():
                result = await db.execute(select(DBOrder).where(DBOrder.id == order_id))
                db_order = result.scalar_one_or_none()

                if db_order:
                    return Order(
                        id=db_order.id,
                        symbol=db_order.symbol,
                        order_type=db_order.order_type,
                        quantity=db_order.quantity,
                        price=db_order.price,
                        status=db_order.status,
                        created_at=cast(datetime | None, db_order.created_at),
                        stop_price=db_order.stop_price,
                        trail_percent=db_order.trail_percent,
                        trail_amount=db_order.trail_amount,
                        condition=db_order.condition or OrderCondition.MARKET,
                        net_price=db_order.net_price,
                        filled_at=cast(datetime | None, db_order.filled_at),
                    )
                break
        except Exception as e:
            logger.error(f"Failed to load order {order_id}: {e}")

        return None

    async def _execute_converted_order(self, order: Order) -> None:
        """Execute a converted order through the trading service."""
        try:
            # Use the trading service to execute the order
            if hasattr(self.trading_service, "execute_order"):
                await self.trading_service.execute_order(order)
            else:
                logger.error("Trading service does not have an execute_order method")

            logger.info(f"Executed converted order: {order.id}")

        except Exception as e:
            logger.error(f"Failed to execute converted order {order.id}: {e}")
            raise

    async def _update_order_triggered_status(
        self, order_id: str, trigger_price: float
    ) -> None:
        """Update the original order status to indicate it was triggered."""
        try:
            async for db in get_async_session():
                # Find the order
                result = await db.execute(select(DBOrder).where(DBOrder.id == order_id))
                db_order = result.scalar_one_or_none()

                if db_order:
                    db_order.status = (
                        OrderStatus.FILLED
                    )  # Or could add TRIGGERED status
                    current_time = datetime.now(UTC)
                    db_order.triggered_at = current_time  # type: ignore[assignment]
                    db_order.filled_at = current_time  # type: ignore[assignment]

                    await db.commit()
                    logger.info(f"Updated order {order_id} status to triggered")
                break

        except Exception as e:
            logger.error(f"Failed to update order status for {order_id}: {e}")

    async def _load_pending_orders(self) -> None:
        """Load pending trigger orders from the database."""
        try:
            async for db in get_async_session():
                # Load pending orders that can be converted
                result = await db.execute(
                    select(DBOrder).where(
                        and_(
                            DBOrder.status == OrderStatus.PENDING,
                            DBOrder.order_type.in_(
                                [
                                    OrderType.STOP_LOSS,
                                    OrderType.STOP_LIMIT,
                                    OrderType.TRAILING_STOP,
                                ]
                            ),
                        )
                    )
                )

                db_orders = result.scalars().all()

                for db_order in db_orders:
                    try:
                        # Convert DB order to schema
                        order = Order(
                            id=db_order.id,
                            symbol=db_order.symbol,
                            order_type=db_order.order_type,
                            quantity=db_order.quantity,
                            price=db_order.price,
                            status=db_order.status,
                            created_at=cast(datetime | None, db_order.created_at),
                            stop_price=db_order.stop_price,
                            trail_percent=db_order.trail_percent,
                            trail_amount=db_order.trail_amount,
                            condition=db_order.condition or OrderCondition.MARKET,
                            net_price=db_order.net_price,
                        )

                        await self.add_order(order)

                    except Exception as e:
                        logger.error(f"Failed to load order {db_order.id}: {e}")
                        continue

                logger.info(f"Loaded {len(db_orders)} pending trigger orders")
                break

        except Exception as e:
            logger.error(f"Failed to load pending orders: {e}")

    def _get_initial_trigger_price(self, order: Order) -> float:
        """Get the initial trigger price for an order."""
        if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT]:
            if order.stop_price is None:
                raise OrderExecutionError(f"Missing stop_price for {order.order_type}")
            return order.stop_price

        elif order.order_type == OrderType.TRAILING_STOP:
            # For trailing stops, we'll set the initial trigger based on current market price
            # This would need to be updated when we get the first market data point
            return 0.0  # Will be updated dynamically

        else:
            raise OrderExecutionError(
                f"Unsupported order type for trigger: {order.order_type}"
            )

    def get_status(self) -> dict[str, Any]:
        """Get current status of the execution engine."""
        with self._lock:
            total_conditions = sum(
                len(conditions) for conditions in self.trigger_conditions.values()
            )

        return {
            "is_running": self.is_running,
            "monitored_symbols": len(self.monitored_symbols),
            "total_trigger_conditions": total_conditions,
            "orders_processed": self.orders_processed,
            "orders_triggered": self.orders_triggered,
            "last_market_data_update": self.last_market_data_update,
            "symbols": list(self.monitored_symbols),
        }

    def get_monitored_orders(self) -> dict[str, list[dict[str, Any]]]:
        """Get currently monitored orders by symbol."""
        with self._lock:
            result = {}
            for symbol, conditions in self.trigger_conditions.items():
                result[symbol] = [
                    {
                        "order_id": condition.order_id,
                        "order_type": condition.order_type,
                        "trigger_price": condition.trigger_price,
                        "trigger_type": condition.trigger_type,
                        "created_at": condition.created_at,
                        "high_water_mark": condition.high_water_mark,
                        "low_water_mark": condition.low_water_mark,
                    }
                    for condition in conditions
                ]
            return result


# Global execution engine instance - will be initialized in main.py
execution_engine: OrderExecutionEngine | None = None


def get_execution_engine() -> OrderExecutionEngine:
    """Get the global execution engine instance."""
    if execution_engine is None:
        raise RuntimeError("Order execution engine not initialized")
    return execution_engine


def initialize_execution_engine(
    trading_service: TradingService,
) -> OrderExecutionEngine:
    """Initialize the global execution engine instance."""
    global execution_engine
    execution_engine = OrderExecutionEngine(trading_service)
    return execution_engine
