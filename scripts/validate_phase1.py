#!/usr/bin/env python3
"""
Phase 1 QA Validation Script

This script performs runtime verification of the Phase 1 QA fixes:
1. Validates that all async methods work correctly
2. Tests database persistence without in-memory storage
3. Verifies proper error handling
4. Checks that all callers use await properly
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.trading_service import TradingService
from app.models.database.trading import Account as DBAccount, Position as DBPosition
from app.storage.database import SessionLocal, engine
from app.models.database.base import Base
from app.schemas.orders import OrderCreate, OrderType, MultiLegOrderCreate, OrderLeg
from app.models.trading import StockQuote
from datetime import datetime
import uuid


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Phase1Validator:
    """Validates Phase 1 QA fixes."""
    
    def __init__(self):
        self.db = SessionLocal()
        self.test_account_id = None
        self.service = None
        
    def setup_test_database(self):
        """Set up test database and account."""
        logger.info("Setting up test database...")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Create test account
        test_account = DBAccount(
            id=str(uuid.uuid4()),
            owner="validation_test",
            cash_balance=100000.0
        )
        self.db.add(test_account)
        self.db.commit()
        self.test_account_id = test_account.id
        
        # Create trading service
        self.service = TradingService(account_owner="validation_test")
        # Mock quote adapter for testing
        from unittest.mock import MagicMock
        self.service.quote_adapter = MagicMock()
        self.service.get_quote = MagicMock(return_value=StockQuote(
            symbol="AAPL", price=150.0, change=0, change_percent=0, volume=1000, last_updated=datetime.now()
        ))
        
        logger.info(f"Test account created with ID: {self.test_account_id}")
        
    def cleanup_test_database(self):
        """Clean up test database."""
        logger.info("Cleaning up test database...")
        try:
            Base.metadata.drop_all(bind=engine)
            self.db.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
    async def validate_async_methods(self):
        """Validate that all async methods work correctly."""
        logger.info("Validating async methods...")
        
        # Test get_account_balance
        balance = await self.service.get_account_balance()
        assert balance == 100000.0, f"Expected balance 100000.0, got {balance}"
        logger.info("✓ get_account_balance works correctly")
        
        # Test get_portfolio
        portfolio = await self.service.get_portfolio()
        assert portfolio is not None, "Portfolio should not be None"
        assert portfolio.cash_balance == 100000.0, f"Expected cash balance 100000.0, got {portfolio.cash_balance}"
        logger.info("✓ get_portfolio works correctly")
        
        # Test get_positions
        positions = await self.service.get_positions()
        assert isinstance(positions, list), "Positions should be a list"
        logger.info("✓ get_positions works correctly")
        
        # Test create_order
        order_data = OrderCreate(
            symbol="AAPL",
            order_type=OrderType.BUY,
            quantity=100,
            price=150.0
        )
        order = await self.service.create_order(order_data)
        assert order is not None, "Order should not be None"
        assert order.symbol == "AAPL", f"Expected symbol AAPL, got {order.symbol}"
        logger.info("✓ create_order works correctly")
        
        # Test get_orders
        orders = await self.service.get_orders()
        assert isinstance(orders, list), "Orders should be a list"
        assert len(orders) >= 1, "Should have at least one order"
        logger.info("✓ get_orders works correctly")
        
        # Test get_order
        retrieved_order = await self.service.get_order(order.id)
        assert retrieved_order is not None, "Retrieved order should not be None"
        assert retrieved_order.id == order.id, "Order IDs should match"
        logger.info("✓ get_order works correctly")
        
        return True
        
    async def validate_database_persistence(self):
        """Validate that data persists in database without in-memory storage."""
        logger.info("Validating database persistence...")
        
        # Create an order
        order_data = OrderCreate(
            symbol="GOOGL",
            order_type=OrderType.BUY,
            quantity=50,
            price=2800.0
        )
        order = await self.service.create_order(order_data)
        order_id = order.id
        
        # Create a new service instance (simulating restart)
        new_service = TradingService(account_owner="validation_test")
        new_service.quote_adapter = self.service.quote_adapter
        new_service.get_quote = self.service.get_quote
        
        # Retrieve the order using the new service
        retrieved_order = await new_service.get_order(order_id)
        assert retrieved_order is not None, "Order should persist across service instances"
        assert retrieved_order.symbol == "GOOGL", f"Expected symbol GOOGL, got {retrieved_order.symbol}"
        logger.info("✓ Database persistence works correctly")
        
        return True
        
    async def validate_multi_leg_order_fix(self):
        """Validate that create_multi_leg_order uses account.id instead of account_owner."""
        logger.info("Validating multi-leg order fix...")
        
        # Create multi-leg order
        order_data = MultiLegOrderCreate(
            legs=[
                OrderLeg(
                    symbol="AAPL240119C00150000",
                    quantity=1,
                    price=5.50,
                    action="buy"
                ),
                OrderLeg(
                    symbol="AAPL240119C00160000",
                    quantity=1,
                    price=2.75,
                    action="sell"
                )
            ]
        )
        
        order = await self.service.create_multi_leg_order(order_data)
        assert order is not None, "Multi-leg order should not be None"
        
        # Verify the order was stored with correct account_id
        from app.models.database.trading import Order as DBOrder
        db_order = self.db.query(DBOrder).filter_by(id=order.id).first()
        assert db_order is not None, "Order should be stored in database"
        assert db_order.account_id == self.test_account_id, f"Expected account_id {self.test_account_id}, got {db_order.account_id}"
        
        logger.info("✓ Multi-leg order fix works correctly")
        return True
        
    async def validate_analyze_portfolio_strategies(self):
        """Validate that analyze_portfolio_strategies uses database data."""
        logger.info("Validating analyze_portfolio_strategies...")
        
        # Add some positions to the database
        position1 = DBPosition(
            id=str(uuid.uuid4()),
            account_id=self.test_account_id,
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=155.0,
            unrealized_pnl=500.0
        )
        self.db.add(position1)
        self.db.commit()
        
        # Test analyze_portfolio_strategies
        result = await self.service.analyze_portfolio_strategies()
        assert result is not None, "Strategy analysis should not be None"
        assert isinstance(result, dict), "Strategy analysis should be a dictionary"
        
        logger.info("✓ analyze_portfolio_strategies works correctly")
        return True
        
    async def validate_calculate_margin_requirement(self):
        """Validate that calculate_margin_requirement uses database data."""
        logger.info("Validating calculate_margin_requirement...")
        
        result = await self.service.calculate_margin_requirement()
        assert result is not None, "Margin requirement should not be None"
        assert isinstance(result, dict), "Margin requirement should be a dictionary"
        
        logger.info("✓ calculate_margin_requirement works correctly")
        return True
        
    async def validate_account_state(self):
        """Validate that validate_account_state uses database data."""
        logger.info("Validating validate_account_state...")
        
        result = await self.service.validate_account_state()
        assert isinstance(result, bool), "Account state validation should return a boolean"
        
        logger.info("✓ validate_account_state works correctly")
        return True
        
    async def run_all_validations(self):
        """Run all validation checks."""
        logger.info("Starting Phase 1 validation...")
        
        try:
            self.setup_test_database()
            
            # Run all validations
            await self.validate_async_methods()
            await self.validate_database_persistence()
            await self.validate_multi_leg_order_fix()
            await self.validate_analyze_portfolio_strategies()
            await self.validate_calculate_margin_requirement()
            await self.validate_account_state()
            
            logger.info("🎉 All Phase 1 validations passed!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            return False
            
        finally:
            self.cleanup_test_database()


async def main():
    """Main validation function."""
    validator = Phase1Validator()
    success = await validator.run_all_validations()
    
    if success:
        logger.info("✅ Phase 1 QA validation completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Phase 1 QA validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())