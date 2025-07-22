"""
Database indexing service for advanced order management optimization.

This module provides utilities for managing database indexes to optimize
query performance for order processing, execution monitoring, and analytics.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DatabaseIndexManager:
    """
    Manages database indexes for optimal query performance.

    Provides utilities for:
    - Creating performance indexes
    - Monitoring index usage
    - Analyzing query performance
    - Index maintenance and optimization
    """

    def __init__(self, engine: Engine):
        self.engine = engine
        self.index_definitions = self._get_index_definitions()

    def _get_index_definitions(self) -> dict[str, str]:
        """Get all index definitions for order management."""
        return {
            # Core order processing indexes
            "idx_orders_status_type": """
                CREATE INDEX IF NOT EXISTS idx_orders_status_type 
                ON orders (status, order_type)
            """,
            "idx_orders_status_created": """
                CREATE INDEX IF NOT EXISTS idx_orders_status_created 
                ON orders (status, created_at)
            """,
            "idx_orders_symbol_status": """
                CREATE INDEX IF NOT EXISTS idx_orders_symbol_status 
                ON orders (symbol, status)
            """,
            "idx_orders_symbol_type": """
                CREATE INDEX IF NOT EXISTS idx_orders_symbol_type 
                ON orders (symbol, order_type)
            """,
            # Trigger-based order indexes
            "idx_orders_stop_price": """
                CREATE INDEX IF NOT EXISTS idx_orders_stop_price 
                ON orders (stop_price) WHERE stop_price IS NOT NULL
            """,
            "idx_orders_triggered_at": """
                CREATE INDEX IF NOT EXISTS idx_orders_triggered_at 
                ON orders (triggered_at) WHERE triggered_at IS NOT NULL
            """,
            "idx_orders_trigger_fields": """
                CREATE INDEX IF NOT EXISTS idx_orders_trigger_fields 
                ON orders (stop_price, trail_percent, trail_amount) 
                WHERE stop_price IS NOT NULL OR trail_percent IS NOT NULL OR trail_amount IS NOT NULL
            """,
            # Order queue processing indexes
            "idx_orders_status_created_type": """
                CREATE INDEX IF NOT EXISTS idx_orders_status_created_type 
                ON orders (status, created_at, order_type)
            """,
            "idx_orders_account_status_symbol": """
                CREATE INDEX IF NOT EXISTS idx_orders_account_status_symbol 
                ON orders (account_id, status, symbol)
            """,
            # Time-based lifecycle indexes
            "idx_orders_created_status": """
                CREATE INDEX IF NOT EXISTS idx_orders_created_status 
                ON orders (created_at, status)
            """,
            "idx_orders_filled_at": """
                CREATE INDEX IF NOT EXISTS idx_orders_filled_at 
                ON orders (filled_at) WHERE filled_at IS NOT NULL
            """,
            "idx_orders_created_filled": """
                CREATE INDEX IF NOT EXISTS idx_orders_created_filled 
                ON orders (created_at, filled_at)
            """,
            # Symbol-based analysis indexes
            "idx_orders_symbol_created": """
                CREATE INDEX IF NOT EXISTS idx_orders_symbol_created 
                ON orders (symbol, created_at)
            """,
            "idx_orders_symbol_filled": """
                CREATE INDEX IF NOT EXISTS idx_orders_symbol_filled 
                ON orders (symbol, filled_at) WHERE filled_at IS NOT NULL
            """,
            # Performance monitoring indexes
            "idx_orders_account_created_status": """
                CREATE INDEX IF NOT EXISTS idx_orders_account_created_status 
                ON orders (account_id, created_at, status)
            """,
            "idx_orders_type_status_created": """
                CREATE INDEX IF NOT EXISTS idx_orders_type_status_created 
                ON orders (order_type, status, created_at)
            """,
            # Advanced order execution indexes
            "idx_orders_pending_triggers": """
                CREATE INDEX IF NOT EXISTS idx_orders_pending_triggers 
                ON orders (status, stop_price, created_at) 
                WHERE status = 'pending' AND stop_price IS NOT NULL
            """,
            "idx_orders_trailing_stops": """
                CREATE INDEX IF NOT EXISTS idx_orders_trailing_stops 
                ON orders (status, trail_percent, trail_amount, created_at) 
                WHERE status = 'pending' AND (trail_percent IS NOT NULL OR trail_amount IS NOT NULL)
            """,
            # Transaction analysis indexes
            "idx_transactions_symbol_timestamp": """
                CREATE INDEX IF NOT EXISTS idx_transactions_symbol_timestamp 
                ON transactions (symbol, timestamp)
            """,
            "idx_transactions_type_timestamp": """
                CREATE INDEX IF NOT EXISTS idx_transactions_type_timestamp 
                ON transactions (transaction_type, timestamp)
            """,
            # Position management indexes
            "idx_positions_symbol_quantity": """
                CREATE INDEX IF NOT EXISTS idx_positions_symbol_quantity 
                ON positions (symbol, quantity) WHERE quantity != 0
            """,
        }

    async def create_all_indexes(self) -> dict[str, bool]:
        """Create all performance optimization indexes."""
        results = {}

        logger.info("Creating database indexes for order management optimization")

        for index_name, index_sql in self.index_definitions.items():
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(index_sql))
                    conn.commit()

                results[index_name] = True
                logger.info(f"Created index: {index_name}")

            except SQLAlchemyError as e:
                results[index_name] = False
                logger.error(f"Failed to create index {index_name}: {e}")

        success_count = sum(results.values())
        total_count = len(results)

        logger.info(
            f"Index creation completed: {success_count}/{total_count} successful"
        )

        return results

    async def analyze_index_usage(self) -> dict[str, dict]:
        """Analyze database index usage statistics."""
        usage_stats = {}

        # PostgreSQL index usage query
        usage_query = """
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched
            FROM pg_stat_user_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('orders', 'transactions', 'positions')
            ORDER BY idx_scan DESC
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(usage_query))

                for row in result:
                    index_name = row.indexname
                    usage_stats[index_name] = {
                        "table": row.tablename,
                        "scans": row.scans,
                        "tuples_read": row.tuples_read,
                        "tuples_fetched": row.tuples_fetched,
                        "efficiency": row.tuples_fetched / max(row.tuples_read, 1),
                    }

        except SQLAlchemyError as e:
            logger.error(f"Failed to analyze index usage: {e}")

        return usage_stats

    async def get_slow_queries(self, min_duration_ms: int = 100) -> list[dict]:
        """Get slow query information for optimization analysis."""
        slow_queries = []

        # PostgreSQL slow query analysis
        slow_query_sql = """
            SELECT 
                query,
                calls,
                total_time,
                mean_time,
                rows
            FROM pg_stat_statements 
            WHERE query LIKE '%orders%' 
            AND mean_time > :min_duration
            ORDER BY mean_time DESC 
            LIMIT 20
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(slow_query_sql), {"min_duration": min_duration_ms}
                )

                for row in result:
                    slow_queries.append(
                        {
                            "query": (
                                row.query[:200] + "..."
                                if len(row.query) > 200
                                else row.query
                            ),
                            "calls": row.calls,
                            "total_time_ms": row.total_time,
                            "avg_time_ms": row.mean_time,
                            "avg_rows": row.rows,
                        }
                    )

        except SQLAlchemyError as e:
            logger.error(f"Failed to get slow queries: {e}")

        return slow_queries

    async def optimize_table_statistics(self) -> dict[str, bool]:
        """Update table statistics for better query planning."""
        results = {}
        tables = ["orders", "transactions", "positions", "accounts"]

        for table in tables:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(f"ANALYZE {table}"))
                    conn.commit()

                results[table] = True
                logger.info(f"Updated statistics for table: {table}")

            except SQLAlchemyError as e:
                results[table] = False
                logger.error(f"Failed to update statistics for {table}: {e}")

        return results

    async def check_index_bloat(self) -> dict[str, dict]:
        """Check for index bloat that may affect performance."""
        bloat_info = {}

        # PostgreSQL index bloat query
        bloat_query = """
            SELECT 
                schemaname,
                tablename,
                indexname,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                pg_relation_size(indexrelid) as index_size_bytes
            FROM pg_stat_user_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('orders', 'transactions', 'positions')
            ORDER BY pg_relation_size(indexrelid) DESC
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(bloat_query))

                for row in result:
                    bloat_info[row.indexname] = {
                        "table": row.tablename,
                        "size_pretty": row.index_size,
                        "size_bytes": row.index_size_bytes,
                    }

        except SQLAlchemyError as e:
            logger.error(f"Failed to check index bloat: {e}")

        return bloat_info

    async def suggest_missing_indexes(self) -> list[dict]:
        """Suggest potentially missing indexes based on query patterns."""
        suggestions = []

        # Query to find missing indexes (PostgreSQL specific)
        missing_index_query = """
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                correlation
            FROM pg_stats 
            WHERE schemaname = 'public' 
            AND tablename IN ('orders', 'transactions', 'positions')
            AND n_distinct > 100
            ORDER BY n_distinct DESC
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(missing_index_query))

                for row in result:
                    # Basic heuristic for suggesting indexes
                    if row.n_distinct > 1000 and abs(row.correlation) < 0.1:
                        suggestions.append(
                            {
                                "table": row.tablename,
                                "column": row.attname,
                                "distinct_values": row.n_distinct,
                                "correlation": row.correlation,
                                "suggestion": f"Consider adding index on {row.tablename}({row.attname})",
                            }
                        )

        except SQLAlchemyError as e:
            logger.error(f"Failed to suggest missing indexes: {e}")

        return suggestions

    async def vacuum_and_reindex(self, table_name: str) -> bool:
        """Vacuum and reindex a specific table for maintenance."""
        try:
            with self.engine.connect() as conn:
                # Vacuum the table
                conn.execute(text(f"VACUUM ANALYZE {table_name}"))

                # Reindex the table
                conn.execute(text(f"REINDEX TABLE {table_name}"))

                conn.commit()

            logger.info(f"Successfully vacuumed and reindexed table: {table_name}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to vacuum/reindex {table_name}: {e}")
            return False

    async def generate_performance_report(self) -> dict:
        """Generate comprehensive database performance report."""
        logger.info("Generating database performance report")

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "index_usage": await self.analyze_index_usage(),
            "slow_queries": await self.get_slow_queries(),
            "index_bloat": await self.check_index_bloat(),
            "missing_indexes": await self.suggest_missing_indexes(),
            "table_sizes": await self._get_table_sizes(),
            "recommendations": [],
        }

        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(report)

        return report

    async def _get_table_sizes(self) -> dict[str, dict]:
        """Get table and index sizes."""
        sizes = {}

        size_query = """
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                pg_total_relation_size(schemaname||'.'||tablename) as total_bytes,
                pg_relation_size(schemaname||'.'||tablename) as table_bytes
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('orders', 'transactions', 'positions', 'accounts')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(size_query))

                for row in result:
                    sizes[row.tablename] = {
                        "total_size": row.total_size,
                        "table_size": row.table_size,
                        "total_bytes": row.total_bytes,
                        "table_bytes": row.table_bytes,
                        "index_size_bytes": row.total_bytes - row.table_bytes,
                    }

        except SQLAlchemyError as e:
            logger.error(f"Failed to get table sizes: {e}")

        return sizes

    def _generate_recommendations(self, report: dict) -> list[str]:
        """Generate performance recommendations based on report data."""
        recommendations = []

        # Check for unused indexes
        for index_name, stats in report["index_usage"].items():
            if stats["scans"] == 0:
                recommendations.append(f"Consider dropping unused index: {index_name}")

        # Check for inefficient indexes
        for index_name, stats in report["index_usage"].items():
            if stats["efficiency"] < 0.1 and stats["scans"] > 0:
                recommendations.append(
                    f"Index {index_name} has low efficiency ({stats['efficiency']:.2%})"
                )

        # Check for slow queries
        if report["slow_queries"]:
            recommendations.append(
                f"Found {len(report['slow_queries'])} slow queries - review for optimization"
            )

        # Check for large tables
        for table_name, size_info in report["table_sizes"].items():
            if size_info["total_bytes"] > 100 * 1024 * 1024:  # > 100MB
                recommendations.append(
                    f"Large table {table_name} ({size_info['total_size']}) - consider partitioning"
                )

        # Check for missing indexes from suggestions
        if report["missing_indexes"]:
            recommendations.append(
                f"Consider {len(report['missing_indexes'])} additional index suggestions"
            )

        if not recommendations:
            recommendations.append("Database indexes appear to be well-optimized")

        return recommendations


# Global database index manager
db_index_manager: DatabaseIndexManager | None = None


def get_database_index_manager(engine: Engine) -> DatabaseIndexManager:
    """Get or create the global database index manager."""
    global db_index_manager
    if db_index_manager is None:
        db_index_manager = DatabaseIndexManager(engine)
    return db_index_manager


def initialize_database_indexes(engine: Engine) -> DatabaseIndexManager:
    """Initialize database indexes for optimal performance."""
    global db_index_manager
    db_index_manager = DatabaseIndexManager(engine)
    return db_index_manager
