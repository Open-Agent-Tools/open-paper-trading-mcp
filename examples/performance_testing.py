"""
Performance Testing Examples - Phase 5.4 implementation.
Demonstrates performance testing for Greeks calculations, database operations, and API endpoints.
"""

import time
import statistics
from typing import Dict, Any, Callable
from decimal import Decimal
from datetime import datetime
import psutil
import tracemalloc

from app.services.greeks import calculate_option_greeks
from app.services.order_execution import OrderExecutionService
from app.services.strategies.recognition import StrategyRecognitionService
from app.models.trading import (
    Order,
    Position,
    OrderType,
    OrderSide,
    OrderCondition,
    OrderStatus,
)


class PerformanceTester:
    """Performance testing utilities for the trading platform."""

    def __init__(self):
        self.results = {}

    def time_function(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Time a function execution with memory tracking."""
        tracemalloc.start()
        start_time = time.perf_counter()
        start_cpu = time.process_time()

        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)

        end_cpu = time.process_time()
        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return {
            "result": result,
            "success": success,
            "error": error,
            "wall_time": end_time - start_time,
            "cpu_time": end_cpu - start_cpu,
            "memory_current": current,
            "memory_peak": peak,
        }

    async def time_async_function(
        self, func: Callable, *args, **kwargs
    ) -> Dict[str, Any]:
        """Time an async function execution with memory tracking."""
        tracemalloc.start()
        start_time = time.perf_counter()
        start_cpu = time.process_time()

        try:
            result = await func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)

        end_cpu = time.process_time()
        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return {
            "result": result,
            "success": success,
            "error": error,
            "wall_time": end_time - start_time,
            "cpu_time": end_cpu - start_cpu,
            "memory_current": current,
            "memory_peak": peak,
        }

    def run_benchmark(
        self, name: str, func: Callable, iterations: int = 100, *args, **kwargs
    ) -> Dict[str, Any]:
        """Run a benchmark with multiple iterations."""
        print(f"\nRunning benchmark: {name} ({iterations} iterations)")

        times = []
        cpu_times = []
        memory_peaks = []
        successes = 0

        for i in range(iterations):
            if i % (iterations // 10) == 0 and iterations >= 10:
                print(f"  Progress: {i}/{iterations}")

            result = self.time_function(func, *args, **kwargs)

            if result["success"]:
                times.append(result["wall_time"])
                cpu_times.append(result["cpu_time"])
                memory_peaks.append(result["memory_peak"])
                successes += 1
            else:
                print(f"  Error in iteration {i}: {result['error']}")

        if not times:
            return {"error": "All iterations failed"}

        benchmark_result = {
            "iterations": iterations,
            "successes": successes,
            "success_rate": successes / iterations,
            "wall_time": {
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "min": min(times),
                "max": max(times),
                "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            },
            "cpu_time": {
                "mean": statistics.mean(cpu_times),
                "median": statistics.median(cpu_times),
                "min": min(cpu_times),
                "max": max(cpu_times),
                "stdev": statistics.stdev(cpu_times) if len(cpu_times) > 1 else 0,
            },
            "memory": {
                "mean_peak": statistics.mean(memory_peaks),
                "max_peak": max(memory_peaks),
                "min_peak": min(memory_peaks),
            },
        }

        self.results[name] = benchmark_result
        self.print_benchmark_result(name, benchmark_result)
        return benchmark_result

    def print_benchmark_result(self, name: str, result: Dict[str, Any]):
        """Print formatted benchmark results."""
        print(f"\n{name} Results:")
        print(f"  Success Rate: {result['success_rate']:.1%}")
        print(
            f"  Wall Time: {result['wall_time']['mean']:.4f}s ± {result['wall_time']['stdev']:.4f}s"
        )
        print(
            f"  CPU Time: {result['cpu_time']['mean']:.4f}s ± {result['cpu_time']['stdev']:.4f}s"
        )
        print(f"  Memory Peak: {result['memory']['mean_peak'] / 1024 / 1024:.2f} MB")
        print(
            f"  Range: {result['wall_time']['min']:.4f}s - {result['wall_time']['max']:.4f}s"
        )


class GreeksPerformanceTesting:
    """Performance tests for Greeks calculations."""

    def __init__(self):
        self.tester = PerformanceTester()

    def test_single_greeks_calculation(self):
        """Test performance of single Greeks calculation."""

        def calculate_single_greeks():
            return calculate_option_greeks(
                option_type="call",
                strike=150.0,
                underlying_price=150.0,
                days_to_expiration=30,
                option_price=5.50,
                risk_free_rate=0.05,
                dividend_yield=0.0,
            )

        return self.tester.run_benchmark(
            "Single Greeks Calculation", calculate_single_greeks, iterations=1000
        )

    def test_bulk_greeks_calculation(self):
        """Test performance of bulk Greeks calculations."""

        def calculate_bulk_greeks():
            results = []
            # Calculate Greeks for 50 different options
            for i in range(50):
                strike = 100.0 + i * 2.5  # Strikes from 100 to 222.5
                underlying = 150.0
                days = 30 + i  # Days from 30 to 79
                price = max(1.0, 5.0 + i * 0.1)  # Option prices

                greeks = calculate_option_greeks(
                    option_type="call" if i % 2 == 0 else "put",
                    strike=strike,
                    underlying_price=underlying,
                    days_to_expiration=days,
                    option_price=price,
                    risk_free_rate=0.05,
                    dividend_yield=0.0,
                )
                results.append(greeks)
            return results

        return self.tester.run_benchmark(
            "Bulk Greeks Calculation (50 options)", calculate_bulk_greeks, iterations=20
        )

    def test_greeks_edge_cases(self):
        """Test performance with edge case scenarios."""

        def calculate_edge_case_greeks():
            edge_cases = [
                # Zero DTE
                {"days": 0, "strike": 150, "underlying": 155, "price": 5.0},
                # Deep ITM
                {"days": 30, "strike": 100, "underlying": 150, "price": 50.5},
                # Deep OTM
                {"days": 30, "strike": 200, "underlying": 150, "price": 0.5},
                # High volatility
                {"days": 90, "strike": 150, "underlying": 150, "price": 25.0},
                # Very long term
                {"days": 365, "strike": 150, "underlying": 150, "price": 35.0},
            ]

            results = []
            for case in edge_cases:
                greeks = calculate_option_greeks(
                    option_type="call",
                    strike=case["strike"],
                    underlying_price=case["underlying"],
                    days_to_expiration=case["days"],
                    option_price=case["price"],
                    risk_free_rate=0.05,
                    dividend_yield=0.0,
                )
                results.append(greeks)
            return results

        return self.tester.run_benchmark(
            "Greeks Edge Cases", calculate_edge_case_greeks, iterations=200
        )


class DatabasePerformanceTesting:
    """Performance tests for database operations."""

    def __init__(self):
        self.tester = PerformanceTester()

    def simulate_bulk_position_updates(self):
        """Simulate bulk position updates for performance testing."""

        def create_bulk_positions():
            positions = []
            for i in range(100):
                position = Position(
                    account_id="PERF_TEST_ACCOUNT",
                    symbol=f"STOCK_{i}",
                    quantity=Decimal(str(100 + i)),
                    cost_basis=Decimal(str(50.0 + i * 0.5)),
                    current_price=Decimal(str(55.0 + i * 0.5)),
                    market_value=Decimal(str((100 + i) * (55.0 + i * 0.5))),
                    delta=Decimal(str(0.5 + i * 0.01)) if i % 2 == 0 else None,
                    created_at=datetime.utcnow(),
                )
                positions.append(position)
            return positions

        return self.tester.run_benchmark(
            "Bulk Position Creation (100 positions)",
            create_bulk_positions,
            iterations=50,
        )

    def simulate_bulk_order_processing(self):
        """Simulate bulk order processing."""

        def create_bulk_orders():
            orders = []
            for i in range(50):
                order = Order(
                    account_id="PERF_TEST_ACCOUNT",
                    symbol=f"STOCK_{i % 20}",  # 20 different symbols
                    order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                    quantity=Decimal(str(100 + i * 10)),
                    price=Decimal(str(100.0 + i)),
                    condition=OrderCondition.LIMIT,
                    status=OrderStatus.PENDING,
                    created_at=datetime.utcnow(),
                )
                orders.append(order)
            return orders

        return self.tester.run_benchmark(
            "Bulk Order Creation (50 orders)", create_bulk_orders, iterations=100
        )


class OrderExecutionPerformanceTesting:
    """Performance tests for order execution logic."""

    def __init__(self):
        self.tester = PerformanceTester()
        self.execution_service = OrderExecutionService()

    def test_simple_order_validation(self):
        """Test performance of simple order validation."""

        def validate_simple_order():
            order = Order(
                account_id="TEST_ACCOUNT",
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                condition=OrderCondition.LIMIT,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
            )

            # Simulate validation logic (simplified)
            validations = [
                order.quantity > 0,
                order.price > 0,
                order.symbol is not None,
                order.order_type in [OrderType.BUY, OrderType.SELL],
                order.condition in [OrderCondition.MARKET, OrderCondition.LIMIT],
            ]

            return all(validations)

        return self.tester.run_benchmark(
            "Simple Order Validation", validate_simple_order, iterations=1000
        )

    def test_multi_leg_order_validation(self):
        """Test performance of multi-leg order validation."""

        def validate_multi_leg_order():
            # Create a complex multi-leg order (iron condor)
            from app.models.trading import MultiLegOrder, OrderLeg

            legs = [
                OrderLeg(
                    symbol="SPY240315P00420000",
                    side=OrderSide.SELL,
                    quantity=Decimal("1"),
                    price=Decimal("2.50"),
                ),
                OrderLeg(
                    symbol="SPY240315P00415000",
                    side=OrderSide.BUY,
                    quantity=Decimal("1"),
                    price=Decimal("1.50"),
                ),
                OrderLeg(
                    symbol="SPY240315C00470000",
                    side=OrderSide.SELL,
                    quantity=Decimal("1"),
                    price=Decimal("2.20"),
                ),
                OrderLeg(
                    symbol="SPY240315C00475000",
                    side=OrderSide.BUY,
                    quantity=Decimal("1"),
                    price=Decimal("1.40"),
                ),
            ]

            order = MultiLegOrder(
                symbol="SPY_IRON_CONDOR",
                order_type=OrderType.MULTI_LEG,
                legs=legs,
                total_price=Decimal("1.80"),
                condition=OrderCondition.LIMIT,
            )

            # Simulate complex validation
            validations = [
                len(order.legs) > 1,
                all(leg.quantity > 0 for leg in order.legs),
                all(leg.price > 0 for leg in order.legs),
                order.total_price is not None,
                # Check for balanced quantities (simplified)
                sum(leg.quantity for leg in order.legs if leg.side == OrderSide.BUY)
                == sum(
                    leg.quantity for leg in order.legs if leg.side == OrderSide.SELL
                ),
            ]

            return all(validations)

        return self.tester.run_benchmark(
            "Multi-leg Order Validation", validate_multi_leg_order, iterations=500
        )


class StrategyRecognitionPerformanceTesting:
    """Performance tests for strategy recognition."""

    def __init__(self):
        self.tester = PerformanceTester()
        self.strategy_service = StrategyRecognitionService()

    def test_simple_strategy_recognition(self):
        """Test performance of recognizing simple strategies."""

        def recognize_simple_strategies():
            # Create positions for covered call
            positions = [
                Position(
                    account_id="TEST",
                    symbol="AAPL",
                    quantity=Decimal("100"),
                    cost_basis=Decimal("150.00"),
                    current_price=Decimal("155.00"),
                    market_value=Decimal("15500.00"),
                ),
                Position(
                    account_id="TEST",
                    symbol="AAPL240315C00160000",
                    quantity=Decimal("-1"),  # Short call
                    cost_basis=Decimal("3.50"),
                    current_price=Decimal("2.80"),
                    market_value=Decimal("-280.00"),
                ),
            ]

            # Simulate strategy recognition logic
            strategies = []

            # Look for covered calls
            stock_positions = {
                pos.symbol: pos
                for pos in positions
                if not pos.symbol.endswith(("C", "P"))
            }
            option_positions = {
                pos.symbol: pos for pos in positions if pos.symbol.endswith(("C", "P"))
            }

            for stock_symbol, stock_pos in stock_positions.items():
                for opt_symbol, opt_pos in option_positions.items():
                    if (
                        stock_symbol in opt_symbol
                        and stock_pos.quantity > 0
                        and opt_pos.quantity < 0
                        and opt_symbol.endswith("C")
                    ):  # Short call
                        strategies.append(
                            {
                                "type": "COVERED_CALL",
                                "stock": stock_symbol,
                                "option": opt_symbol,
                            }
                        )

            return strategies

        return self.tester.run_benchmark(
            "Simple Strategy Recognition", recognize_simple_strategies, iterations=500
        )

    def test_complex_strategy_recognition(self):
        """Test performance of recognizing complex strategies."""

        def recognize_complex_strategies():
            # Create positions for iron condor
            positions = [
                Position(
                    account_id="TEST",
                    symbol="SPY240315P00420000",
                    quantity=Decimal("-1"),
                    cost_basis=Decimal("2.50"),
                    current_price=Decimal("2.30"),
                    market_value=Decimal("-230.00"),
                ),
                Position(
                    account_id="TEST",
                    symbol="SPY240315P00415000",
                    quantity=Decimal("1"),
                    cost_basis=Decimal("1.50"),
                    current_price=Decimal("1.40"),
                    market_value=Decimal("140.00"),
                ),
                Position(
                    account_id="TEST",
                    symbol="SPY240315C00470000",
                    quantity=Decimal("-1"),
                    cost_basis=Decimal("2.20"),
                    current_price=Decimal("2.00"),
                    market_value=Decimal("-200.00"),
                ),
                Position(
                    account_id="TEST",
                    symbol="SPY240315C00475000",
                    quantity=Decimal("1"),
                    cost_basis=Decimal("1.40"),
                    current_price=Decimal("1.30"),
                    market_value=Decimal("130.00"),
                ),
            ]

            # Simulate complex strategy recognition
            strategies = []

            # Group by underlying and expiration
            by_underlying = {}
            for pos in positions:
                symbol = pos.symbol
                if len(symbol) >= 15:  # Option symbol
                    underlying = (
                        symbol[:3] if symbol.startswith(("SPY", "QQQ")) else symbol[:4]
                    )
                    expiration = (
                        symbol[3:9]
                        if symbol.startswith(("SPY", "QQQ"))
                        else symbol[4:10]
                    )
                    key = f"{underlying}_{expiration}"

                    if key not in by_underlying:
                        by_underlying[key] = []
                    by_underlying[key].append(pos)

            # Look for iron condors (4 legs, puts and calls, specific pattern)
            for key, group in by_underlying.items():
                if len(group) == 4:
                    puts = [pos for pos in group if "P" in pos.symbol]
                    calls = [pos for pos in group if "C" in pos.symbol]

                    if len(puts) == 2 and len(calls) == 2:
                        # Check for iron condor pattern
                        put_quantities = [pos.quantity for pos in puts]
                        call_quantities = [pos.quantity for pos in calls]

                        if (
                            put_quantities.count(Decimal("1")) == 1
                            and put_quantities.count(Decimal("-1")) == 1
                            and call_quantities.count(Decimal("1")) == 1
                            and call_quantities.count(Decimal("-1")) == 1
                        ):
                            strategies.append(
                                {
                                    "type": "IRON_CONDOR",
                                    "underlying": key,
                                    "legs": len(group),
                                }
                            )

            return strategies

        return self.tester.run_benchmark(
            "Complex Strategy Recognition", recognize_complex_strategies, iterations=200
        )


class SystemResourceTesting:
    """Test system resource usage under load."""

    def __init__(self):
        self.tester = PerformanceTester()

    def test_memory_usage_under_load(self):
        """Test memory usage when creating many objects."""

        def create_large_dataset():
            orders = []
            positions = []

            # Create 1000 orders
            for i in range(1000):
                order = Order(
                    account_id=f"ACCOUNT_{i % 10}",
                    symbol=f"STOCK_{i % 100}",
                    order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                    quantity=Decimal(str(100 + i % 100)),
                    price=Decimal(str(100.0 + i % 50)),
                    condition=OrderCondition.LIMIT,
                    status=OrderStatus.PENDING,
                    created_at=datetime.utcnow(),
                )
                orders.append(order)

            # Create 500 positions
            for i in range(500):
                position = Position(
                    account_id=f"ACCOUNT_{i % 10}",
                    symbol=f"STOCK_{i % 50}",
                    quantity=Decimal(str(100 + i)),
                    cost_basis=Decimal(str(50.0 + i * 0.1)),
                    current_price=Decimal(str(55.0 + i * 0.1)),
                    market_value=Decimal(str((100 + i) * (55.0 + i * 0.1))),
                    created_at=datetime.utcnow(),
                )
                positions.append(position)

            return {"orders": len(orders), "positions": len(positions)}

        return self.tester.run_benchmark(
            "Large Dataset Creation (1000 orders + 500 positions)",
            create_large_dataset,
            iterations=10,
        )

    def test_cpu_intensive_calculations(self):
        """Test CPU usage with intensive calculations."""

        def intensive_greeks_calculation():
            results = []

            # Calculate Greeks for many option combinations
            strikes = range(50, 201, 5)  # 31 strikes
            days_list = [1, 7, 14, 30, 60, 90]  # 6 time periods

            for strike in strikes:
                for days in days_list:
                    try:
                        greeks = calculate_option_greeks(
                            option_type="call",
                            strike=float(strike),
                            underlying_price=100.0,
                            days_to_expiration=days,
                            option_price=max(1.0, 10.0 - abs(strike - 100) * 0.1),
                            risk_free_rate=0.05,
                            dividend_yield=0.0,
                        )
                        results.append(greeks)
                    except Exception:
                        continue

            return len(results)

        return self.tester.run_benchmark(
            "Intensive Greeks Calculation (31 strikes × 6 periods)",
            intensive_greeks_calculation,
            iterations=5,
        )


def run_performance_test_suite():
    """Run the complete performance test suite."""
    print("=" * 80)
    print("PERFORMANCE TEST SUITE")
    print("=" * 80)
    print("\nTesting platform performance across multiple dimensions...")

    # System info
    print("\nSystem Information:")
    print(f"  CPU Count: {psutil.cpu_count()} cores")
    print(f"  Memory: {psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB")
    print(
        f"  Python Version: {psutil.Process().environ.get('PYTHON_VERSION', 'Unknown')}"
    )

    results_summary = {}

    # 1. Greeks Performance Testing
    print("\n" + "=" * 60)
    print("GREEKS CALCULATION PERFORMANCE")
    print("=" * 60)

    greeks_tester = GreeksPerformanceTesting()
    results_summary["greeks_single"] = greeks_tester.test_single_greeks_calculation()
    results_summary["greeks_bulk"] = greeks_tester.test_bulk_greeks_calculation()
    results_summary["greeks_edge_cases"] = greeks_tester.test_greeks_edge_cases()

    # 2. Database Performance Testing
    print("\n" + "=" * 60)
    print("DATABASE OPERATIONS PERFORMANCE")
    print("=" * 60)

    db_tester = DatabasePerformanceTesting()
    results_summary["db_positions"] = db_tester.simulate_bulk_position_updates()
    results_summary["db_orders"] = db_tester.simulate_bulk_order_processing()

    # 3. Order Execution Performance Testing
    print("\n" + "=" * 60)
    print("ORDER EXECUTION PERFORMANCE")
    print("=" * 60)

    order_tester = OrderExecutionPerformanceTesting()
    results_summary["order_validation_simple"] = (
        order_tester.test_simple_order_validation()
    )
    results_summary["order_validation_multileg"] = (
        order_tester.test_multi_leg_order_validation()
    )

    # 4. Strategy Recognition Performance Testing
    print("\n" + "=" * 60)
    print("STRATEGY RECOGNITION PERFORMANCE")
    print("=" * 60)

    strategy_tester = StrategyRecognitionPerformanceTesting()
    results_summary["strategy_simple"] = (
        strategy_tester.test_simple_strategy_recognition()
    )
    results_summary["strategy_complex"] = (
        strategy_tester.test_complex_strategy_recognition()
    )

    # 5. System Resource Testing
    print("\n" + "=" * 60)
    print("SYSTEM RESOURCE USAGE")
    print("=" * 60)

    resource_tester = SystemResourceTesting()
    results_summary["memory_load"] = resource_tester.test_memory_usage_under_load()
    results_summary["cpu_intensive"] = resource_tester.test_cpu_intensive_calculations()

    # Performance Summary
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)

    print(f"{'Test Category':<35} {'Avg Time':<12} {'Success Rate':<12} {'Memory':<10}")
    print("-" * 70)

    for test_name, result in results_summary.items():
        if "error" not in result:
            avg_time = result["wall_time"]["mean"]
            success_rate = result["success_rate"]
            memory_mb = result["memory"]["mean_peak"] / 1024 / 1024

            print(
                f"{test_name:<35} {avg_time:<12.4f}s {success_rate:<12.1%} {memory_mb:<10.1f}MB"
            )
        else:
            print(f"{test_name:<35} {'ERROR':<12} {'N/A':<12} {'N/A':<10}")

    # Performance Recommendations
    print("\n" + "=" * 80)
    print("PERFORMANCE RECOMMENDATIONS")
    print("=" * 80)

    recommendations = []

    # Analyze results and provide recommendations
    if (
        "greeks_single" in results_summary
        and results_summary["greeks_single"]["wall_time"]["mean"] > 0.01
    ):
        recommendations.append(
            "Greeks calculation is slower than optimal. Consider caching or optimization."
        )

    if (
        "greeks_bulk" in results_summary
        and results_summary["greeks_bulk"]["wall_time"]["mean"] > 2.0
    ):
        recommendations.append(
            "Bulk Greeks calculation needs optimization. Consider parallel processing."
        )

    memory_tests = ["memory_load", "cpu_intensive"]
    for test in memory_tests:
        if (
            test in results_summary
            and results_summary[test]["memory"]["mean_peak"] > 100 * 1024 * 1024
        ):  # > 100MB
            recommendations.append(
                f"High memory usage in {test}. Consider memory optimization."
            )

    if not recommendations:
        recommendations.append("All performance metrics are within acceptable ranges.")

    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

    print(
        f"\nPerformance testing completed. {len(results_summary)} test categories executed."
    )

    return results_summary


if __name__ == "__main__":
    """Run performance testing examples."""

    print("PERFORMANCE TESTING EXAMPLES")
    print("============================")
    print("\nThis module demonstrates performance testing capabilities")
    print("for the options trading platform.")

    # Run the full performance test suite
    results = run_performance_test_suite()

    print("\n" + "=" * 80)
    print("PERFORMANCE TESTING COMPLETE")
    print("=" * 80)
    print("""
Performance testing helps ensure that the trading platform can handle:

1. High-frequency Greeks calculations for real-time pricing
2. Bulk database operations for portfolio management
3. Complex order validation and execution
4. Strategy recognition across large portfolios
5. System resource management under load

Key Performance Metrics:
- Greeks calculation: < 0.01s per option (target)
- Bulk operations: < 2.0s for 100 items (target)
- Memory usage: < 100MB for typical operations
- Success rate: > 99% for all operations

Optimization Strategies:
- Implement caching for frequently calculated Greeks
- Use vectorized operations for bulk calculations
- Optimize database queries with proper indexing
- Consider async processing for non-critical operations
- Monitor memory usage and implement garbage collection

Regular performance testing ensures the platform maintains
acceptable response times as features are added and usage scales.
    """)
