"""
Performance benchmarks for critical trading operations.

Tests response times and throughput for key system operations
to ensure they meet performance targets.
"""

import asyncio
import time
from statistics import mean, median

from httpx import AsyncClient

from app.services.trading_service import TradingService
from tests.e2e.conftest import E2ETestHelpers


class TestPerformanceBenchmarks:
    """Performance benchmark tests for critical operations."""

    async def test_order_creation_performance(
        self, test_client: AsyncClient, created_test_account: str
    ):
        """Benchmark order creation performance."""
        account_id = created_test_account

        # Benchmark order creation
        times = []
        order_count = 100

        for i in range(order_count):
            order_data = {
                "symbol": f"TEST{i:03d}",
                "order_type": "buy",
                "quantity": 10,
                "price": 100.0 + i * 0.01,
                "condition": "limit",
            }

            start_time = time.time()
            response = await test_client.post(
                f"/api/v1/accounts/{account_id}/orders", json=order_data
            )
            end_time = time.time()

            assert response.status_code == 201
            times.append(end_time - start_time)

        # Performance assertions
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)
        min_time = min(times)

        print("\nOrder Creation Performance:")
        print(f"  Orders created: {order_count}")
        print(f"  Average time: {avg_time:.3f}s")
        print(f"  Median time: {median_time:.3f}s")
        print(f"  Min time: {min_time:.3f}s")
        print(f"  Max time: {max_time:.3f}s")
        print(f"  Rate: {order_count / sum(times):.1f} orders/second")

        # Performance targets
        assert (
            avg_time < 0.1
        ), f"Average order creation time {avg_time:.3f}s exceeds 100ms"
        assert (
            median_time < 0.05
        ), f"Median order creation time {median_time:.3f}s exceeds 50ms"
        assert max_time < 0.5, f"Max order creation time {max_time:.3f}s exceeds 500ms"

    async def test_portfolio_calculation_performance(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Benchmark portfolio calculation with many positions."""
        account_id = created_test_account

        # Create many positions
        position_count = 100
        symbols = [f"STOCK{i:04d}" for i in range(position_count)]

        print(f"\nCreating {position_count} positions...")
        creation_start = time.time()

        for i, symbol in enumerate(symbols):
            order_data = {
                "symbol": symbol,
                "order_type": "buy",
                "quantity": 10 + i % 100,
                "price": 100.0 + i * 0.1,
                "condition": "limit",
            }

            await e2e_helpers.create_and_fill_order(test_client, account_id, order_data)

        creation_time = time.time() - creation_start
        print(f"Position creation took: {creation_time:.1f}s")

        # Benchmark portfolio calculation
        times = []
        calculation_count = 10

        for _ in range(calculation_count):
            start_time = time.time()
            response = await test_client.get(f"/api/v1/accounts/{account_id}/portfolio")
            end_time = time.time()

            assert response.status_code == 200
            portfolio = response.json()
            assert len(portfolio["positions"]) == position_count

            times.append(end_time - start_time)

        # Performance results
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)

        print("\nPortfolio Calculation Performance:")
        print(f"  Positions: {position_count}")
        print(f"  Calculations: {calculation_count}")
        print(f"  Average time: {avg_time:.3f}s")
        print(f"  Median time: {median_time:.3f}s")
        print(f"  Max time: {max_time:.3f}s")

        # Performance assertions
        assert (
            avg_time < 0.5
        ), f"Portfolio calculation time {avg_time:.3f}s exceeds 500ms"
        assert (
            max_time < 1.0
        ), f"Max portfolio calculation time {max_time:.3f}s exceeds 1s"

    async def test_quote_retrieval_performance(self):
        """Benchmark quote retrieval performance."""
        trading_service = TradingService()

        # Test symbols
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META", "NFLX"]
        times = []

        for symbol in symbols:
            start_time = time.time()
            quote = await trading_service.get_quote(symbol)
            end_time = time.time()

            assert quote is not None
            assert quote.symbol == symbol
            assert quote.price > 0

            times.append(end_time - start_time)

        # Performance results
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)

        print("\nQuote Retrieval Performance:")
        print(f"  Symbols tested: {len(symbols)}")
        print(f"  Average time: {avg_time:.3f}s")
        print(f"  Median time: {median_time:.3f}s")
        print(f"  Max time: {max_time:.3f}s")

        # Performance assertions
        assert (
            avg_time < 0.1
        ), f"Average quote retrieval time {avg_time:.3f}s exceeds 100ms"
        assert max_time < 0.5, f"Max quote retrieval time {max_time:.3f}s exceeds 500ms"

    async def test_concurrent_order_processing(
        self, test_client: AsyncClient, created_test_account: str
    ):
        """Benchmark concurrent order processing."""
        account_id = created_test_account

        async def create_order_batch(batch_id: int, batch_size: int = 10):
            """Create a batch of orders concurrently."""
            tasks = []
            for i in range(batch_size):
                order_data = {
                    "symbol": f"BATCH{batch_id}_{i:02d}",
                    "order_type": "buy",
                    "quantity": 10,
                    "price": 100.0 + i,
                    "condition": "limit",
                }

                task = test_client.post(
                    f"/api/v1/accounts/{account_id}/orders", json=order_data
                )
                tasks.append(task)

            return await asyncio.gather(*tasks)

        # Test concurrent batches
        batch_count = 5
        batch_size = 10
        total_orders = batch_count * batch_size

        print(
            f"\nTesting {batch_count} concurrent batches of {batch_size} orders each..."
        )

        start_time = time.time()

        # Create all batches concurrently
        batch_tasks = [
            create_order_batch(batch_id, batch_size) for batch_id in range(batch_count)
        ]

        batch_results = await asyncio.gather(*batch_tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Verify all orders were created
        success_count = 0
        for batch_result in batch_results:
            for response in batch_result:
                if response.status_code == 201:
                    success_count += 1

        # Performance results
        throughput = success_count / total_time

        print("\nConcurrent Order Processing Performance:")
        print(f"  Total orders: {total_orders}")
        print(f"  Successful orders: {success_count}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.1f} orders/second")
        print(f"  Success rate: {success_count / total_orders * 100:.1f}%")

        # Performance assertions
        assert success_count >= total_orders * 0.95  # 95% success rate
        assert throughput > 20, f"Throughput {throughput:.1f} orders/sec is too low"

    async def test_database_query_performance(
        self, test_client: AsyncClient, populated_test_account: dict
    ):
        """Benchmark database query performance."""
        account_id = populated_test_account["account_id"]

        # Test different query types
        query_tests = [
            ("Get Account", f"/api/v1/accounts/{account_id}"),
            ("Get Orders", f"/api/v1/accounts/{account_id}/orders"),
            ("Get Positions", f"/api/v1/accounts/{account_id}/positions"),
            ("Get Portfolio", f"/api/v1/accounts/{account_id}/portfolio"),
        ]

        results = {}

        for query_name, endpoint in query_tests:
            times = []
            iterations = 20

            for _ in range(iterations):
                start_time = time.time()
                response = await test_client.get(endpoint)
                end_time = time.time()

                assert response.status_code == 200
                times.append(end_time - start_time)

            avg_time = mean(times)
            results[query_name] = avg_time

            print(f"\n{query_name} Query Performance:")
            print(f"  Iterations: {iterations}")
            print(f"  Average time: {avg_time:.3f}s")
            print(f"  Min time: {min(times):.3f}s")
            print(f"  Max time: {max(times):.3f}s")

        # Performance assertions
        for query_name, avg_time in results.items():
            assert (
                avg_time < 0.1
            ), f"{query_name} query time {avg_time:.3f}s exceeds 100ms"

    async def test_memory_usage_under_load(
        self,
        test_client: AsyncClient,
        created_test_account: str,
        e2e_helpers: E2ETestHelpers,
    ):
        """Test memory usage during sustained operation."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        print(f"\nInitial memory usage: {initial_memory:.1f}MB")

        account_id = created_test_account
        max_memory_increase = 0

        # Sustained operation cycles
        for cycle in range(20):
            # Create and execute orders
            orders = []
            for i in range(20):
                order_data = {
                    "symbol": f"CYCLE{cycle:02d}_{i:02d}",
                    "order_type": "buy",
                    "quantity": 10,
                    "price": 100.0 + i,
                    "condition": "limit",
                }

                order = await e2e_helpers.create_and_fill_order(
                    test_client, account_id, order_data
                )
                orders.append(order)

            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            max_memory_increase = max(max_memory_increase, memory_increase)

            if cycle % 5 == 0:
                print(
                    f"Cycle {cycle}: Memory {current_memory:.1f}MB (+{memory_increase:.1f}MB)"
                )

        print("\nMemory Usage Test Results:")
        print(f"  Initial memory: {initial_memory:.1f}MB")
        print(f"  Final memory: {current_memory:.1f}MB")
        print(f"  Max increase: {max_memory_increase:.1f}MB")

        # Memory should not grow indefinitely
        assert (
            max_memory_increase < 200
        ), f"Memory usage increased by {max_memory_increase:.1f}MB"

    async def test_stress_test_high_volume(
        self, test_client: AsyncClient, created_test_account: str
    ):
        """Stress test with high volume of orders."""
        account_id = created_test_account

        # High volume test
        total_orders = 1000
        batch_size = 50
        batches = total_orders // batch_size

        print(
            f"\nStress test: {total_orders} orders in {batches} batches of {batch_size}"
        )

        start_time = time.time()
        successful_orders = 0

        for batch in range(batches):
            batch_start = time.time()

            # Create batch of orders
            tasks = []
            for i in range(batch_size):
                order_data = {
                    "symbol": f"STRESS{batch:03d}_{i:02d}",
                    "order_type": "buy",
                    "quantity": 1,
                    "price": 100.0 + (batch * batch_size + i) * 0.01,
                    "condition": "limit",
                }

                task = test_client.post(
                    f"/api/v1/accounts/{account_id}/orders", json=order_data
                )
                tasks.append(task)

            # Execute batch
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes
            batch_successes = sum(
                1
                for r in responses
                if not isinstance(r, Exception) and r.status_code == 201
            )
            successful_orders += batch_successes

            batch_time = time.time() - batch_start

            if batch % 5 == 0:
                rate = batch_successes / batch_time
                print(
                    f"Batch {batch}: {batch_successes}/{batch_size} orders in {batch_time:.2f}s ({rate:.1f}/s)"
                )

        total_time = time.time() - start_time
        overall_rate = successful_orders / total_time
        success_rate = successful_orders / total_orders * 100

        print("\nStress Test Results:")
        print(f"  Total orders attempted: {total_orders}")
        print(f"  Successful orders: {successful_orders}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  Overall rate: {overall_rate:.1f} orders/second")

        # Stress test assertions
        assert success_rate >= 95, f"Success rate {success_rate:.1f}% too low"
        assert overall_rate > 50, f"Overall rate {overall_rate:.1f} orders/sec too low"
