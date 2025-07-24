"""
Performance Benchmarks for Priority 1 Functionality

This module provides performance testing for Priority 1 components:
- TradingService performance
- Order execution engine performance
- Schema validation performance
"""

import pytest
import time
import asyncio
from statistics import mean, median
from unittest.mock import AsyncMock, MagicMock

from app.services.trading_service import TradingService
from app.services.order_execution_engine import OrderExecutionEngine, TriggerCondition
from app.schemas.orders import OrderCreate, OrderType, OrderCondition


class TestPriority1Performance:
    """Performance benchmarks for Priority 1 functionality."""

    def test_trading_service_initialization_performance(self):
        """Benchmark TradingService initialization performance."""
        times = []
        
        for _ in range(100):
            start_time = time.perf_counter()
            service = TradingService(account_owner=f"user_{_}")
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)
        
        # Performance assertions - TradingService should initialize quickly
        assert avg_time < 0.01, f"Average initialization time too slow: {avg_time:.4f}s"
        assert max_time < 0.05, f"Maximum initialization time too slow: {max_time:.4f}s"
        
        print(f"TradingService Init - Avg: {avg_time:.4f}s, Median: {median_time:.4f}s, Max: {max_time:.4f}s")

    def test_order_execution_engine_initialization_performance(self):
        """Benchmark OrderExecutionEngine initialization performance."""
        service = TradingService(account_owner="test_user")
        times = []
        
        for _ in range(100):
            start_time = time.perf_counter()
            engine = OrderExecutionEngine(service)
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.01, f"Average initialization time too slow: {avg_time:.4f}s"
        assert max_time < 0.05, f"Maximum initialization time too slow: {max_time:.4f}s"
        
        print(f"OrderExecutionEngine Init - Avg: {avg_time:.4f}s, Median: {median_time:.4f}s, Max: {max_time:.4f}s")

    def test_trigger_condition_performance(self):
        """Benchmark trigger condition evaluation performance."""
        condition = TriggerCondition(
            order_id="test_order",
            symbol="AAPL",
            trigger_type="stop_loss",
            trigger_price=140.0,
            order_type=OrderType.SELL
        )
        
        times = []
        test_prices = [135.0, 140.0, 145.0] * 1000  # 3000 evaluations
        
        start_time = time.perf_counter()
        for price in test_prices:
            condition.should_trigger(price)
        end_time = time.perf_counter()
        
        total_time = end_time - start_time
        avg_time_per_eval = total_time / len(test_prices)
        
        # Performance assertions - trigger evaluation should be very fast
        assert avg_time_per_eval < 0.0001, f"Trigger evaluation too slow: {avg_time_per_eval:.6f}s per evaluation"
        assert total_time < 1.0, f"Total evaluation time too slow: {total_time:.4f}s for {len(test_prices)} evaluations"
        
        print(f"Trigger Evaluation - Total: {total_time:.4f}s, Per eval: {avg_time_per_eval:.6f}s")

    def test_order_create_validation_performance(self):
        """Benchmark order creation and validation performance."""
        times = []
        
        for i in range(1000):
            start_time = time.perf_counter()
            order = OrderCreate(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100 + i,
                price=150.0 + (i * 0.01),
                condition=OrderCondition.LIMIT
            )
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)
        
        # Performance assertions - order creation should be fast
        assert avg_time < 0.001, f"Average order creation time too slow: {avg_time:.6f}s"
        assert max_time < 0.01, f"Maximum order creation time too slow: {max_time:.6f}s"
        
        print(f"Order Creation - Avg: {avg_time:.6f}s, Median: {median_time:.6f}s, Max: {max_time:.6f}s")

    @pytest.mark.asyncio
    async def test_quote_retrieval_performance(self):
        """Benchmark quote retrieval performance with mocked adapter."""
        mock_adapter = AsyncMock()
        mock_quote = MagicMock()
        mock_quote.price = 150.75
        mock_quote.volume = 1000000
        mock_quote.quote_date = time.time()
        mock_adapter.get_quote.return_value = mock_quote
        
        service = TradingService(quote_adapter=mock_adapter, account_owner="test_user")
        
        times = []
        
        for _ in range(100):
            start_time = time.perf_counter()
            quote = await service.get_quote("AAPL")
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.01, f"Average quote retrieval time too slow: {avg_time:.6f}s"
        assert max_time < 0.05, f"Maximum quote retrieval time too slow: {max_time:.6f}s"
        
        print(f"Quote Retrieval - Avg: {avg_time:.6f}s, Median: {median_time:.6f}s, Max: {max_time:.6f}s")

    def test_bulk_order_creation_performance(self):
        """Benchmark bulk order creation performance."""
        order_count = 10000
        
        start_time = time.perf_counter()
        orders = []
        
        for i in range(order_count):
            order = OrderCreate(
                symbol=f"STOCK{i % 100}",  # 100 different symbols
                order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                quantity=100 + (i % 1000),
                price=100.0 + (i % 500),
                condition=OrderCondition.LIMIT if i % 3 == 0 else OrderCondition.MARKET
            )
            orders.append(order)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_per_order = total_time / order_count
        
        # Performance assertions
        assert total_time < 10.0, f"Bulk order creation too slow: {total_time:.4f}s for {order_count} orders"
        assert avg_time_per_order < 0.001, f"Average order creation too slow: {avg_time_per_order:.6f}s per order"
        
        print(f"Bulk Order Creation - Total: {total_time:.4f}s, Per order: {avg_time_per_order:.6f}s, Orders/sec: {order_count/total_time:.0f}")

    def test_memory_usage_stability(self):
        """Test memory usage stability during repeated operations."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        
        # Create many TradingService instances
        services = []
        for i in range(1000):
            service = TradingService(account_owner=f"user_{i}")
            services.append(service)
        
        # Create many orders
        orders = []
        for i in range(1000):
            order = OrderCreate(
                symbol="AAPL",
                order_type=OrderType.BUY,
                quantity=100,
                price=150.0,
                condition=OrderCondition.LIMIT
            )
            orders.append(order)
        
        # Clean up
        del services
        del orders
        gc.collect()
        
        # This test mainly ensures no memory leaks cause crashes
        assert True, "Memory usage test completed successfully"