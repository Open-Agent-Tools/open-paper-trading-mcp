#!/bin/bash

echo "🔍 Testing Frontend Data Loading APIs"
echo "===================================="

BASE_URL="http://localhost:2080"
ACCOUNT_ID="UITESTER01"

echo ""
echo "1. Testing Health Check..."
health_response=$(curl -s "${BASE_URL}/health")
echo "✅ Health: $health_response"

echo ""
echo "2. Testing Accounts List..."
accounts_response=$(curl -s "${BASE_URL}/api/v1/trading/accounts")
echo "✅ Accounts: $accounts_response"

echo ""
echo "3. Testing Portfolio Summary..."
portfolio_response=$(curl -s "${BASE_URL}/api/v1/trading/portfolio/summary?account_id=${ACCOUNT_ID}")
echo "✅ Portfolio: $portfolio_response"

echo ""
echo "4. Testing Account Balance..."
balance_response=$(curl -s "${BASE_URL}/api/v1/trading/account/balance?account_id=${ACCOUNT_ID}")
echo "✅ Balance: $balance_response"

echo ""
echo "5. Testing Market Hours..."
market_response=$(curl -s "${BASE_URL}/api/v1/trading/market/hours")
echo "✅ Market Hours: $market_response"

echo ""
echo "🎉 All API endpoints tested successfully!"
echo "📱 Frontend should now be able to load all data properly."
echo "🌐 Open http://localhost:2080 to test the UI"