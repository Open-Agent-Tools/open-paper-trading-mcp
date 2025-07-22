"""
Query optimization utilities for order management performance.

This module provides optimized database queries for common order management
operations, leveraging the created indexes for maximum performance.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from ..models.database.trading import Order
from ..schemas.orders import OrderStatus, OrderType

logger = logging.getLogger(__name__)


class OptimizedOrderQueries:
    """
    Optimized database queries for order management operations.

    Provides high-performance queries that leverage database indexes
    for common order processing patterns.
    """

    def __init__(self, session: Session):
        self.session = session

    async def get_pending_triggered_orders(self, limit: int = 1000) -> list[Order]:
        """
        Get pending orders with trigger conditions for monitoring.
        Uses: idx_orders_pending_triggers
        """
        query = (
            select(Order)
            .where(
                and_(
                    Order.status == OrderStatus.PENDING,
                    or_(
                        Order.stop_price.isnot(None),
                        Order.trail_percent.isnot(None),
                        Order.trail_amount.isnot(None),
                    ),
                )
            )
            .order_by(Order.created_at)
            .limit(limit)
        )

        result = self.session.execute(query)
        return result.scalars().all()

    async def get_orders_by_status_and_type(
        self,
        status: OrderStatus,
        order_type: OrderType | None = None,
        limit: int = 1000,
    ) -> list[Order]:
        """
        Get orders by status and optionally by type.
        Uses: idx_orders_status_type, idx_orders_status_created
        """
        conditions = [Order.status == status]

        if order_type:
            conditions.append(Order.order_type == order_type)

        query = (
            select(Order)
            .where(and_(*conditions))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )

        result = self.session.execute(query)
        return result.scalars().all()

    async def get_orders_for_symbol(
        self, symbol: str, status: OrderStatus | None = None, limit: int = 100
    ) -> list[Order]:
        """
        Get orders for a specific symbol.
        Uses: idx_orders_symbol_status, idx_orders_symbol_created
        """
        conditions = [Order.symbol == symbol]

        if status:
            conditions.append(Order.status == status)

        query = (
            select(Order)
            .where(and_(*conditions))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )

        result = self.session.execute(query)
        return result.scalars().all()

    async def get_account_orders_summary(
        self,
        account_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """
        Get order summary for an account.
        Uses: idx_orders_account_created_status
        """
        conditions = [Order.account_id == account_id]

        if start_date:
            conditions.append(Order.created_at >= start_date)
        if end_date:
            conditions.append(Order.created_at <= end_date)

        # Count by status
        status_query = (
            select(Order.status, func.count(Order.id).label("count"))
            .where(and_(*conditions))
            .group_by(Order.status)
        )

        status_result = self.session.execute(status_query)
        status_counts = {row.status: row.count for row in status_result}

        # Count by type
        type_query = (
            select(Order.order_type, func.count(Order.id).label("count"))
            .where(and_(*conditions))
            .group_by(Order.order_type)
        )

        type_result = self.session.execute(type_query)
        type_counts = {row.order_type: row.count for row in type_result}

        return {
            "status_counts": status_counts,
            "type_counts": type_counts,
            "total_orders": sum(status_counts.values()),
        }

    async def get_recent_filled_orders(
        self, hours: int = 24, limit: int = 100
    ) -> list[Order]:
        """
        Get recently filled orders.
        Uses: idx_orders_filled_at
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = (
            select(Order)
            .where(
                and_(Order.status == OrderStatus.FILLED, Order.filled_at >= cutoff_time)
            )
            .order_by(Order.filled_at.desc())
            .limit(limit)
        )

        result = self.session.execute(query)
        return result.scalars().all()

    async def get_order_execution_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> dict:
        """
        Get order execution performance metrics.
        Uses multiple indexes for complex aggregation.
        """
        # Average execution time
        execution_time_query = select(
            func.avg(func.extract("epoch", Order.filled_at - Order.created_at)).label(
                "avg_execution_seconds"
            )
        ).where(
            and_(
                Order.status == OrderStatus.FILLED,
                Order.created_at >= start_date,
                Order.created_at <= end_date,
                Order.filled_at.isnot(None),
            )
        )

        execution_result = self.session.execute(execution_time_query)
        avg_execution_time = execution_result.scalar() or 0

        # Fill rate by order type
        fill_rate_query = (
            select(
                Order.order_type,
                func.count(Order.id).label("total"),
                func.sum(
                    func.case((Order.status == OrderStatus.FILLED, 1), else_=0)
                ).label("filled"),
            )
            .where(and_(Order.created_at >= start_date, Order.created_at <= end_date))
            .group_by(Order.order_type)
        )

        fill_rate_result = self.session.execute(fill_rate_query)
        fill_rates = {}

        for row in fill_rate_result:
            fill_rates[row.order_type] = {
                "total": row.total,
                "filled": row.filled,
                "rate": row.filled / row.total if row.total > 0 else 0,
            }

        return {
            "avg_execution_time_seconds": avg_execution_time,
            "fill_rates_by_type": fill_rates,
        }

    async def get_stop_loss_candidates(
        self, current_prices: dict[str, float], limit: int = 100
    ) -> list[tuple[Order, float]]:
        """
        Get orders that may need stop loss triggering.
        Uses: idx_orders_trigger_fields
        """
        candidates = []

        # Get orders with stop prices
        stop_orders_query = (
            select(Order)
            .where(
                and_(Order.status == OrderStatus.PENDING, Order.stop_price.isnot(None))
            )
            .limit(limit)
        )

        result = self.session.execute(stop_orders_query)
        stop_orders = result.scalars().all()

        for order in stop_orders:
            if order.symbol in current_prices:
                current_price = current_prices[order.symbol]

                # Check if stop should trigger
                should_trigger = False

                if (
                    order.order_type == OrderType.BUY
                    and current_price >= order.stop_price
                ) or (
                    order.order_type == OrderType.SELL
                    and current_price <= order.stop_price
                ):
                    should_trigger = True

                if should_trigger:
                    candidates.append((order, current_price))

        return candidates

    async def get_trailing_stop_candidates(
        self, current_prices: dict[str, float], limit: int = 100
    ) -> list[tuple[Order, float, float]]:
        """
        Get orders that may need trailing stop updates.
        Uses: idx_orders_trailing_stops
        """
        candidates = []

        # Get orders with trailing stops
        trailing_query = (
            select(Order)
            .where(
                and_(
                    Order.status == OrderStatus.PENDING,
                    or_(
                        Order.trail_percent.isnot(None), Order.trail_amount.isnot(None)
                    ),
                )
            )
            .limit(limit)
        )

        result = self.session.execute(trailing_query)
        trailing_orders = result.scalars().all()

        for order in trailing_orders:
            if order.symbol in current_prices:
                current_price = current_prices[order.symbol]

                # Calculate new trailing stop
                if order.trail_percent:
                    trail_amount = current_price * (order.trail_percent / 100)
                else:
                    trail_amount = order.trail_amount

                if order.order_type == OrderType.SELL:
                    new_stop = current_price - trail_amount
                else:
                    new_stop = current_price + trail_amount

                candidates.append((order, current_price, new_stop))

        return candidates

    async def get_order_queue_depth(self) -> dict[str, int]:
        """
        Get current order queue depth by status.
        Uses: idx_orders_status_created
        """
        depth_query = select(
            Order.status, func.count(Order.id).label("count")
        ).group_by(Order.status)

        result = self.session.execute(depth_query)
        return {row.status: row.count for row in result}

    async def get_high_frequency_symbols(
        self, hours: int = 24, min_orders: int = 10
    ) -> list[tuple[str, int]]:
        """
        Get symbols with high order frequency.
        Uses: idx_orders_symbol_created
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        frequency_query = (
            select(Order.symbol, func.count(Order.id).label("order_count"))
            .where(Order.created_at >= cutoff_time)
            .group_by(Order.symbol)
            .having(func.count(Order.id) >= min_orders)
            .order_by(func.count(Order.id).desc())
            .limit(50)
        )

        result = self.session.execute(frequency_query)
        return [(row.symbol, row.order_count) for row in result]

    async def bulk_update_order_status(
        self,
        order_ids: list[str],
        new_status: OrderStatus,
        filled_at: datetime | None = None,
    ) -> int:
        """
        Bulk update order status for performance.
        Uses primary key lookups for efficiency.
        """
        update_values = {"status": new_status}

        if filled_at:
            update_values["filled_at"] = filled_at

        # Use raw SQL for better performance on bulk updates
        if filled_at:
            query = text(
                """
                UPDATE orders 
                SET status = :status, filled_at = :filled_at
                WHERE id = ANY(:order_ids)
            """
            )
        else:
            query = text(
                """
                UPDATE orders 
                SET status = :status
                WHERE id = ANY(:order_ids)
            """
            )

        result = self.session.execute(
            query,
            {
                "status": new_status.value,
                "filled_at": filled_at,
                "order_ids": order_ids,
            },
        )

        return result.rowcount

    async def cleanup_old_completed_orders(
        self, days_old: int = 90, batch_size: int = 1000
    ) -> int:
        """
        Clean up old completed orders to maintain performance.
        Uses: idx_orders_created_status
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Count total orders to clean
        count_query = select(func.count(Order.id)).where(
            and_(
                Order.status.in_([OrderStatus.FILLED, OrderStatus.CANCELLED]),
                Order.created_at < cutoff_date,
            )
        )

        total_result = self.session.execute(count_query)
        total_count = total_result.scalar()

        logger.info(f"Found {total_count} old orders to archive/cleanup")

        # For now, just return count - actual cleanup would need archiving strategy
        return total_count


def get_optimized_order_queries(session: Session) -> OptimizedOrderQueries:
    """Get optimized order query utilities."""
    return OptimizedOrderQueries(session)
