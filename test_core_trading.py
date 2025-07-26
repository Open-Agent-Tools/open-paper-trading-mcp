#!/usr/bin/env python3
"""
Simple tests for core trading service functionality.
Tests the clean architecture with just adapters + main server.
"""

import pytest
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_app_imports():
    """Test that our clean app structure imports correctly."""
    try:
        import app.main
        print("✅ app.main imports successfully")
    except ImportError as e:
        pytest.fail(f"Failed to import app.main: {e}")

def test_adapters_import():
    """Test that core adapters import correctly."""
    try:
        from app.adapters import base, robinhood, markets, test_data
        print("✅ Core adapters import successfully")
    except ImportError as e:
        pytest.fail(f"Failed to import adapters: {e}")

def test_base_adapter():
    """Test the base adapter interface."""
    try:
        from app.adapters.base import BaseAdapter
        
        # Check if it's a proper class
        assert hasattr(BaseAdapter, '__init__')
        print("✅ BaseAdapter class exists")
    except Exception as e:
        pytest.fail(f"BaseAdapter test failed: {e}")

def test_test_data_adapter():
    """Test the test data adapter."""
    try:
        from app.adapters.test_data import TestDataAdapter
        
        # Try to create an instance
        adapter = TestDataAdapter()
        print("✅ TestDataAdapter instantiated successfully")
        
        # Test if it has basic methods (if any)
        if hasattr(adapter, 'get_quote'):
            print("✅ TestDataAdapter has get_quote method")
            
    except Exception as e:
        pytest.fail(f"TestDataAdapter test failed: {e}")

def test_server_creation():
    """Test that the FastAPI server can be created."""
    try:
        from app.main import app
        
        # Check if it's a FastAPI app
        assert hasattr(app, 'routes')
        print(f"✅ FastAPI app created with {len(app.routes)} routes")
        
        # Check for basic routes
        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        assert "/health" in route_paths
        assert "/" in route_paths
        print("✅ Basic routes (/health, /) exist")
        
    except Exception as e:
        pytest.fail(f"Server creation test failed: {e}")

if __name__ == "__main__":
    """Run tests directly."""
    print("🧪 Testing Core Trading Service - Clean Architecture")
    print("=" * 50)
    
    try:
        test_app_imports()
        test_adapters_import()
        test_base_adapter()
        test_test_data_adapter()
        test_server_creation()
        
        print("=" * 50)
        print("🎉 All core trading tests PASSED!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)