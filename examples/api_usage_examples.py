"""
API Usage Examples - Phase 5.3 implementation.
Demonstrates how to use both REST API and MCP tools for options trading.
"""

import asyncio
import json
from datetime import date, timedelta
from typing import Any

import aiohttp


class RestApiExamples:
    """Examples for using the REST API endpoints."""

    def __init__(self, base_url: str = "http://localhost:2080"):
        self.base_url = base_url
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "RestApiExamples":
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.session:
            await self.session.close()

    async def create_account_example(self) -> dict[str, Any]:
        """Example: Create a new trading account."""
        print("=== CREATE ACCOUNT EXAMPLE ===")

        account_data = {
            "account_id": "DEMO_001",
            "name": "Demo Trading Account",
            "initial_cash": 50000.00,
        }

        assert self.session is not None
        async with self.session.post(
            f"{self.base_url}/api/v1/accounts", json=account_data
        ) as response:
            result = await response.json()

        print(f"Created account: {result}")
        return result

    async def get_account_info_example(self, account_id: str) -> dict[str, Any]:
        """Example: Get account information and balances."""
        print(f"=== GET ACCOUNT INFO: {account_id} ===")

        assert self.session is not None
        async with self.session.get(
            f"{self.base_url}/api/v1/accounts/{account_id}"
        ) as response:
            result = await response.json()

        print("Account Info:")
        print(f"  Cash Balance: ${result.get('cash_balance', 0):,.2f}")
        print(f"  Equity Value: ${result.get('equity_value', 0):,.2f}")
        print(f"  Margin Requirement: ${result.get('margin_requirement', 0):,.2f}")

        return result

    async def place_simple_order_example(self, account_id: str) -> dict[str, Any]:
        """Example: Place a simple stock buy order."""
        print("=== PLACE SIMPLE STOCK ORDER ===")

        order_data = {
            "account_id": account_id,
            "symbol": "AAPL",
            "order_type": "BUY",
            "quantity": 100,
            "price": 150.00,
            "condition": "LIMIT",
        }

        assert self.session is not None
        async with self.session.post(
            f"{self.base_url}/api/v1/orders", json=order_data
        ) as response:
            result = await response.json()

        print(f"Order placed: {result}")
        return result

    async def place_multi_leg_order_example(self, account_id: str) -> dict[str, Any]:
        """Example: Place a multi-leg options order (bull call spread)."""
        print("=== PLACE MULTI-LEG OPTIONS ORDER ===")

        # Bull call spread: Buy 150 call, Sell 155 call
        expiration = date.today() + timedelta(days=30)
        expiration_str = expiration.strftime("%y%m%d")

        order_data = {
            "account_id": account_id,
            "symbol": "AAPL_BULL_SPREAD",
            "order_type": "MULTI_LEG",
            "condition": "LIMIT",
            "total_price": 2.50,
            "legs": [
                {
                    "symbol": f"AAPL{expiration_str}C00150000",
                    "side": "BUY",
                    "quantity": 1,
                    "price": 5.50,
                },
                {
                    "symbol": f"AAPL{expiration_str}C00155000",
                    "side": "SELL",
                    "quantity": 1,
                    "price": 3.00,
                },
            ],
        }

        async with self.session.post(
            f"{self.base_url}/api/v1/orders/multi-leg", json=order_data
        ) as response:
            result = await response.json()

        print(f"Multi-leg order placed: {result}")
        return result

    async def get_options_chain_example(self, symbol: str) -> dict[str, Any]:
        """Example: Get options chain for a symbol."""
        print(f"=== GET OPTIONS CHAIN: {symbol} ===")

        # Get expiration dates first
        async with self.session.get(
            f"{self.base_url}/api/v1/options/{symbol}/expirations"
        ) as response:
            expirations = await response.json()

        print(f"Available expirations: {expirations}")

        if expirations:
            # Get chain for first expiration
            expiration_date = expirations[0]
            async with self.session.get(
                f"{self.base_url}/api/v1/options/{symbol}/chain",
                params={"expiration_date": expiration_date},
            ) as response:
                chain = await response.json()

            print(f"Options chain for {expiration_date}:")
            print(f"  Calls: {len(chain.get('calls', []))} strikes")
            print(f"  Puts: {len(chain.get('puts', []))} strikes")

            # Show a few examples
            calls = chain.get("calls", [])[:3]
            for call in calls:
                print(f"    {call['symbol']}: ${call['bid']}-${call['ask']}")

            return chain

        return {}

    async def get_portfolio_analysis_example(self, account_id: str) -> dict[str, Any]:
        """Example: Get portfolio analysis and strategy breakdown."""
        print(f"=== PORTFOLIO ANALYSIS: {account_id} ===")

        # Get current positions
        async with self.session.get(
            f"{self.base_url}/api/v1/accounts/{account_id}/positions"
        ) as response:
            positions = await response.json()

        print(f"Current positions: {len(positions)}")

        for position in positions[:5]:  # Show first 5
            print(
                f"  {position['symbol']}: {position['quantity']} @ ${position['current_price']}"
            )

        # Get strategy analysis
        async with self.session.get(
            f"{self.base_url}/api/v1/strategies/analyze",
            params={"account_id": account_id},
        ) as response:
            strategies = await response.json()

        print(f"Recognized strategies: {len(strategies)}")
        for strategy in strategies:
            print(f"  {strategy['type']}: {strategy['description']}")

        return {"positions": positions, "strategies": strategies}

    async def calculate_greeks_example(self, option_symbol: str) -> dict[str, Any]:
        """Example: Calculate option Greeks."""
        print(f"=== CALCULATE GREEKS: {option_symbol} ===")

        # Example parameters
        params = {
            "underlying_price": 150.00,
            "risk_free_rate": 0.05,
            "dividend_yield": 0.0,
        }

        async with self.session.get(
            f"{self.base_url}/api/v1/options/{option_symbol}/greeks", params=params
        ) as response:
            greeks = await response.json()

        print(f"Greeks for {option_symbol}:")
        print(f"  Delta: {greeks.get('delta', 'N/A'):.4f}")
        print(f"  Gamma: {greeks.get('gamma', 'N/A'):.4f}")
        print(f"  Theta: {greeks.get('theta', 'N/A'):.4f}")
        print(f"  Vega: {greeks.get('vega', 'N/A'):.4f}")
        print(f"  IV: {greeks.get('iv', 'N/A'):.4f}")

        return greeks


class McpToolsExamples:
    """Examples for using MCP tools."""

    async def create_account_with_mcp(self) -> dict[str, Any]:
        """Example: Create account using MCP tools."""
        print("=== MCP: CREATE ACCOUNT ===")

        # This would be called through the MCP interface
        # Showing the equivalent tool call
        tool_call = {
            "tool": "create_account",
            "arguments": {
                "account_id": "MCP_DEMO_001",
                "name": "MCP Demo Account",
                "initial_cash": 25000.00,
            },
        }

        print(f"MCP Tool Call: {json.dumps(tool_call, indent=2)}")
        print("Expected Response: Account created with ID MCP_DEMO_001")

        return tool_call

    async def place_order_with_mcp(self) -> dict[str, Any]:
        """Example: Place order using MCP tools."""
        print("=== MCP: PLACE ORDER ===")

        tool_call = {
            "tool": "place_order",
            "arguments": {
                "account_id": "MCP_DEMO_001",
                "symbol": "GOOGL",
                "order_type": "BUY",
                "quantity": 25,
                "price": 2800.00,
                "condition": "LIMIT",
            },
        }

        print(f"MCP Tool Call: {json.dumps(tool_call, indent=2)}")
        print("Expected Response: Order placed successfully with order ID")

        return tool_call

    async def create_multi_leg_order_with_mcp(self) -> dict[str, Any]:
        """Example: Create multi-leg order using MCP tools."""
        print("=== MCP: CREATE MULTI-LEG ORDER ===")

        expiration = date.today() + timedelta(days=45)
        expiration_str = expiration.strftime("%y%m%d")

        tool_call = {
            "tool": "create_multi_leg_order",
            "arguments": {
                "account_id": "MCP_DEMO_001",
                "strategy_type": "IRON_CONDOR",
                "legs": [
                    {
                        "symbol": f"SPY{expiration_str}P00420000",
                        "side": "SELL",
                        "quantity": 1,
                        "price": 2.50,
                    },
                    {
                        "symbol": f"SPY{expiration_str}P00415000",
                        "side": "BUY",
                        "quantity": 1,
                        "price": 1.50,
                    },
                    {
                        "symbol": f"SPY{expiration_str}C00470000",
                        "side": "SELL",
                        "quantity": 1,
                        "price": 2.20,
                    },
                    {
                        "symbol": f"SPY{expiration_str}C00475000",
                        "side": "BUY",
                        "quantity": 1,
                        "price": 1.40,
                    },
                ],
                "total_price": 1.80,
            },
        }

        print(f"MCP Tool Call: {json.dumps(tool_call, indent=2)}")
        print("Expected Response: Iron Condor order created and placed")

        return tool_call

    async def get_strategy_analysis_with_mcp(self) -> dict[str, Any]:
        """Example: Get strategy analysis using MCP tools."""
        print("=== MCP: STRATEGY ANALYSIS ===")

        tool_call = {
            "tool": "get_strategy_analysis",
            "arguments": {
                "account_id": "MCP_DEMO_001",
                "include_greeks": True,
                "include_risk_metrics": True,
            },
        }

        print(f"MCP Tool Call: {json.dumps(tool_call, indent=2)}")
        print(
            "Expected Response: Detailed strategy breakdown with Greeks and risk metrics"
        )

        return tool_call

    async def simulate_expiration_with_mcp(self) -> dict[str, Any]:
        """Example: Simulate option expiration using MCP tools."""
        print("=== MCP: SIMULATE OPTION EXPIRATION ===")

        tool_call = {
            "tool": "simulate_option_expiration",
            "arguments": {
                "account_id": "MCP_DEMO_001",
                "expiration_date": "2024-01-19",
                "underlying_prices": {"AAPL": 155.00, "SPY": 445.00, "GOOGL": 2850.00},
            },
        }

        print(f"MCP Tool Call: {json.dumps(tool_call, indent=2)}")
        print("Expected Response: Expiration simulation results with position changes")

        return tool_call


async def demonstrate_rest_api_workflow():
    """Demonstrate complete REST API workflow."""
    print("\n" + "=" * 60)
    print("REST API COMPLETE WORKFLOW DEMONSTRATION")
    print("=" * 60)

    async with RestApiExamples() as api:
        try:
            # 1. Create account
            account = await api.create_account_example()
            account_id = account.get("account_id", "DEMO_001")

            # 2. Get account info
            await api.get_account_info_example(account_id)

            # 3. Place simple order
            await api.place_simple_order_example(account_id)

            # 4. Place multi-leg order
            await api.place_multi_leg_order_example(account_id)

            # 5. Get options chain
            await api.get_options_chain_example("AAPL")

            # 6. Portfolio analysis
            await api.get_portfolio_analysis_example(account_id)

            # 7. Calculate Greeks
            expiration = date.today() + timedelta(days=30)
            option_symbol = f"AAPL{expiration.strftime('%y%m%d')}C00150000"
            await api.calculate_greeks_example(option_symbol)

        except Exception as e:
            print(f"API call failed (expected in demo): {e}")
            print(
                "Note: This is a demonstration - actual API server needed for real calls"
            )


async def demonstrate_mcp_workflow():
    """Demonstrate complete MCP tools workflow."""
    print("\n" + "=" * 60)
    print("MCP TOOLS COMPLETE WORKFLOW DEMONSTRATION")
    print("=" * 60)

    mcp = McpToolsExamples()

    # 1. Create account
    await mcp.create_account_with_mcp()

    # 2. Place simple order
    await mcp.place_order_with_mcp()

    # 3. Create multi-leg order
    await mcp.create_multi_leg_order_with_mcp()

    # 4. Strategy analysis
    await mcp.get_strategy_analysis_with_mcp()

    # 5. Simulate expiration
    await mcp.simulate_expiration_with_mcp()


def demonstrate_integration_patterns():
    """Demonstrate integration patterns and best practices."""
    print("\n" + "=" * 60)
    print("INTEGRATION PATTERNS AND BEST PRACTICES")
    print("=" * 60)

    print("""
1. REST API vs MCP Tools - When to Use What:

   REST API:
   - Web applications and dashboards
   - Real-time trading platforms
   - Mobile applications
   - Direct programmatic access
   
   MCP Tools:
   - AI agent integration (Claude, ChatGPT, etc.)
   - Conversational trading interfaces
   - Educational and research applications
   - Workflow automation with AI

2. Error Handling Best Practices:

   Always handle these scenarios:
   - Network timeouts and connection errors
   - Insufficient funds for orders
   - Invalid option symbols or expired contracts
   - Market closed / outside trading hours
   - Rate limiting and API quotas

3. Authentication and Security:

   - Use API keys for REST endpoints
   - Implement proper session management
   - Never log sensitive account information
   - Use HTTPS in production
   - Validate all inputs on both client and server

4. Performance Optimization:

   - Batch multiple API calls when possible
   - Cache options chains and static data
   - Use websockets for real-time updates
   - Implement proper pagination for large datasets
   - Monitor API response times and set timeouts

5. Risk Management Integration:

   - Always validate orders before submission
   - Implement position size limits
   - Monitor margin requirements in real-time
   - Set up alerts for approaching risk limits
   - Keep audit logs of all trading activity

6. Testing and Development:

   - Use test accounts for development
   - Implement comprehensive unit tests
   - Test with various market scenarios
   - Validate calculations against known values
   - Test error conditions and edge cases

Example Error Handling:

```python
async def safe_api_call():
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 400:
                    error = await response.json()
                    raise ValueError(f"Invalid request: {error['message']}")
                elif response.status == 429:
                    raise RuntimeError("Rate limit exceeded - retry later")
                else:
                    response.raise_for_status()
    except asyncio.TimeoutError:
        raise RuntimeError("API request timed out")
    except aiohttp.ClientError as e:
        raise RuntimeError(f"Network error: {e}")
```

Example MCP Tool Usage in Claude:

```
User: "Create a covered call strategy for my AAPL position"

Claude calls MCP tool:
{
  "tool": "create_multi_leg_order",
  "arguments": {
    "account_id": "user_account",
    "strategy_type": "COVERED_CALL",
    "underlying_symbol": "AAPL",
    "call_strike": 155.00,
    "expiration_date": "2024-02-16"
  }
}

Claude receives response and explains the strategy to user.
```
    """)


if __name__ == "__main__":
    """Run all API usage examples."""

    print("API USAGE EXAMPLES")
    print("==================")
    print("\nThis module demonstrates how to use both REST API and MCP tools")
    print("for options trading with our platform.")

    # Run demonstrations
    asyncio.run(demonstrate_rest_api_workflow())
    asyncio.run(demonstrate_mcp_workflow())
    demonstrate_integration_patterns()

    print("\n" + "=" * 60)
    print("API USAGE SUMMARY")
    print("=" * 60)
    print("""
REST API Endpoints Summary:
- POST /api/v1/accounts - Create account
- GET /api/v1/accounts/{id} - Get account info
- POST /api/v1/orders - Place simple order
- POST /api/v1/orders/multi-leg - Place multi-leg order
- GET /api/v1/options/{symbol}/chain - Get options chain
- GET /api/v1/options/{symbol}/expirations - Get expiration dates
- GET /api/v1/strategies/analyze - Analyze strategies
- GET /api/v1/options/{symbol}/greeks - Calculate Greeks

MCP Tools Summary:
- create_account - Create new trading account
- place_order - Place buy/sell orders
- create_multi_leg_order - Create complex options strategies
- get_strategy_analysis - Analyze portfolio strategies
- simulate_option_expiration - Simulate expiration scenarios
- calculate_option_greeks - Calculate option Greeks
- get_options_chain - Retrieve options chains

Both interfaces provide the same core functionality with different usage patterns
optimized for their respective use cases.
    """)
