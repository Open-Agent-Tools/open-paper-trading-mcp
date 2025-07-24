#!/usr/bin/env python3
"""
Database optimization script for order management performance.

This script creates and optimizes database indexes for improved
order processing, execution monitoring, and analytics performance.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.services.database_indexes import DatabaseIndexManager
from app.storage.database import async_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main optimization routine."""
    logger.info("Starting database optimization for order management")

    try:
        # Get database engine
        engine = get_engine()

        # Initialize index manager
        index_manager = DatabaseIndexManager(engine)

        # Create all performance indexes
        logger.info("Creating performance optimization indexes...")
        index_results = await index_manager.create_all_indexes()

        success_count = sum(index_results.values())
        total_count = len(index_results)

        print("\n📊 Index Creation Results:")
        print(f"Successfully created: {success_count}/{total_count} indexes")

        if success_count < total_count:
            print("\n❌ Failed indexes:")
            for index_name, success in index_results.items():
                if not success:
                    print(f"  - {index_name}")

        # Update table statistics
        logger.info("Updating table statistics...")
        stats_results = await index_manager.optimize_table_statistics()

        stats_success = sum(stats_results.values())
        stats_total = len(stats_results)

        print("\n📈 Statistics Update Results:")
        print(f"Successfully updated: {stats_success}/{stats_total} tables")

        # Generate performance report
        logger.info("Generating performance report...")
        report = await index_manager.generate_performance_report()

        print("\n📋 Performance Report:")
        print(f"Index usage analyzed: {len(report['index_usage'])} indexes")
        print(f"Slow queries found: {len(report['slow_queries'])}")
        print(f"Index suggestions: {len(report['missing_indexes'])}")

        print("\n💡 Recommendations:")
        for i, recommendation in enumerate(report["recommendations"], 1):
            print(f"  {i}. {recommendation}")

        # Show table sizes
        print("\n📦 Table Sizes:")
        for table_name, size_info in report["table_sizes"].items():
            print(
                f"  {table_name}: {size_info['total_size']} (table: {size_info['table_size']})"
            )

        logger.info("Database optimization completed successfully")

    except Exception as e:
        logger.error(f"Database optimization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
