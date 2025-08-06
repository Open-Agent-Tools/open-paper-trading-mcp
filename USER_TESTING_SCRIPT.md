# User Testing Script - Frontend Components
**Open Paper Trading MCP - Frontend Testing Narrative**

## Overview
This script provides step-by-step testing for frontend components. Use the UITESTER01 account which has comprehensive test data including 5 stock positions ($99K+ portfolio value) and historical orders.

## ✅ Recently Completed & Fully Functional
- **Options Trading Interface** - Core options chain with live Robinhood data, expiration-first workflow, ITM/ATM/OTM indicators
- **Chart Components** - Price history charts with professional styling, proper axis labels, time-based labels for 1-day charts  
- **Analyst Ratings** - Stock ratings display with buy/hold/sell breakdown
- **Market Data Integration** - Real-time quotes, stock search, company information
- **Account Management** - Complete portfolio display with positions, balances, and order history

---

## 🚀 Pre-Testing Setup

### 1. Start the Application
```bash
# Terminal 1: Start FastAPI server
cd /Users/wes/Development/open-paper-trading-mcp
python scripts/dev.py server

# Terminal 2: Start React frontend (if separate)
# Navigate to frontend directory and start if needed
```

### 2. Access the Application
- Open browser to `http://localhost:2080`
- Verify UITESTER01 account is available
- Expected: Dashboard loads with portfolio data showing $99,335.37 total value

---

## 🧪 PHASE 1: Recently Updated Components Testing

### Test 1.1: Options Trading Interface (✅ COMPLETED)
**Location**: Research page → Options Chain tab

**Narrative**: 
*"As an options trader, I need to view live options data with an intuitive workflow that requires expiration selection first."*

**Testing Steps**:
1. Navigate to `http://localhost:2080/research`  
2. Enter a liquid stock symbol (e.g., "AAPL", "XOM", "MSFT")
3. Click on **Options Chain** tab
4. Verify expiration date selection interface appears first
5. Click on an expiration date chip to select it
6. Verify options chain loads with calls/puts tables
7. Check ITM/ATM/OTM indicators and color coding
8. Test switching between Calls and Puts tabs
9. Verify null value handling (volume, open interest display as "-" when null)

**Expected Results** ✅:
- Expiration-first workflow prevents immediate data loading
- Live Robinhood options data displays correctly
- Professional table with ITM/ATM/OTM indicators
- Proper null value handling without crashes
- Responsive design with proper loading states

### Test 1.2: Price History Charts (✅ COMPLETED)  
**Location**: Research page → Charts tab

**Narrative**:
*"I need professional financial charts with proper axis labels and time-based formatting for day charts."*

**Testing Steps**:
1. Navigate to Charts tab for any stock symbol
2. Test different time periods (1D, 5D, 1M, 3M, 6M, 1Y)
3. Verify 1-day charts show time labels (9:30 AM, 12:00 PM, etc.)
4. Verify multi-day charts show date labels (Jan 15, Feb 1, etc.)  
5. Check chart sizing (600px height, full width)
6. Verify style guide compliance (Roboto Mono font, proper colors)

**Expected Results** ✅:
- Professional 600px height charts (not tiny sparklines)
- Time labels for 1-day charts, date labels for longer periods
- Style guide compliant typography and colors
- Responsive full-width design
- Proper axis labeling and scaling

### Test 1.3: Analyst Ratings (✅ COMPLETED)
**Location**: Research page → Ratings tab  

**Narrative**:
*"I want to see analyst ratings breakdown and target price information for stocks I'm researching."*

**Testing Steps**:
1. Navigate to Ratings tab for any covered stock
2. Verify ratings breakdown displays properly (Strong Buy, Buy, Hold, Sell, Strong Sell)
3. Check target price information (Average, High, Low)
4. Verify overall rating calculation
5. Test with different stock symbols

**Expected Results** ✅:
- Ratings breakdown displays without crashes
- Proper API response structure handling
- Clear visual presentation of analyst consensus
- Target price information properly formatted

---

## 📊 PHASE 2: Pending Portfolio Analytics Testing

### Test 2.1: Performance Charts (❌ NOT IMPLEMENTED)
**Location**: Portfolio Analytics section

**Narrative**: 
*"As a trader, I want to see how my portfolio has performed over time to evaluate my trading strategy effectiveness."*

**Current Status**: Component needs to be implemented
**Priority**: HIGH - Core portfolio analytics feature

### Test 2.2: Risk Metrics Dashboard (❌ NOT IMPLEMENTED)
**Location**: Portfolio Analytics section

**Narrative**:
*"As a risk-conscious investor, I need to understand my portfolio's risk profile including concentration, diversification, and volatility metrics."*

**Current Status**: Component needs to be implemented  
**Priority**: HIGH - Essential risk management tool

### Test 2.3: Asset Allocation Visualization (❌ NOT IMPLEMENTED)
**Location**: Portfolio Analytics section

**Narrative**:
*"I want to visualize how my investments are distributed across different asset types and individual holdings."*

**Current Status**: Component needs to be implemented
**Priority**: HIGH - Core portfolio visualization

---

## 📈 PHASE 3: Advanced Options Features Testing

### Test 3.1: Options Analytics Component (❌ NOT IMPLEMENTED)
**Location**: Options Trading section

**Narrative**:
*"As an options trader, I need to analyze potential strategies with profit/loss diagrams and Greeks calculations."*

**Current Status**: Advanced analytics not yet implemented (basic options chain works)
**Priority**: MEDIUM - Enhancement to existing options interface

### Test 3.2: Spread Builder Interface (❌ NOT IMPLEMENTED)  
**Location**: Options Trading section

**Narrative**:
*"I want to construct multi-leg options strategies and visualize their payoff profiles before placing orders."*

**Current Status**: Multi-leg strategy builder needs implementation
**Priority**: MEDIUM - Advanced options feature

### Test 3.3: Expiration Calendar (❌ NOT IMPLEMENTED)
**Location**: Options Trading section

**Narrative**:
*"I need to track when my options positions expire to manage risk and avoid assignment."*

**Current Status**: Expiration calendar component needs implementation
**Priority**: MEDIUM - Options position management tool

---

## 🧪 PHASE 4: Quality Assurance Testing

### Test 4.1: Completed Components Validation ✅
**Focus**: Test recently completed and working components

**Testing Steps**:
1. **Options Chain**: Verify live data loads, expiration selection works, null values handled
2. **Price History Charts**: Check professional styling, proper axis labels, time formatting  
3. **Analyst Ratings**: Confirm ratings breakdown displays without crashes
4. **Stock Research**: Test symbol search, company info, market data integration
5. **Portfolio Display**: Verify UITESTER01 data shows correctly with positions and balances

**Expected Results**:
- All completed components function without errors
- Professional styling and user experience
- Proper error handling and loading states
- Consistent behavior across different stock symbols

### Test 4.2: API Error Handling  
**Focus**: Test error scenarios for working components

**Testing Steps**:  
1. Network throttling (Slow 3G) for options chain loading
2. Invalid stock symbols in research page
3. Market hours testing (after-hours behavior)
4. Rate limiting scenarios with multiple rapid requests

**Expected Results**:
- Graceful error handling without crashes
- Meaningful error messages to users
- Loading states during network delays
- Proper fallback behavior

---

## 📱 PHASE 5: Responsive Design Testing

### Test 5.1: Mobile Device Simulation  
**Focus**: Test completed components on different screen sizes

**Testing Steps**:  
1. Open browser dev tools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)  
3. Test working components on different screen sizes:
   - iPhone 12 Pro (390x844) - Options chain, charts
   - iPad (768x1024) - Research page layout
   - Desktop (1920x1080) - Full interface
4. Verify charts and tables are scrollable/responsive
5. Test touch interactions on mobile

**Expected Results**:
- Options chain table scrolls horizontally on mobile
- Charts maintain readability at all sizes  
- Touch-friendly interface elements
- Responsive navigation and layout

---

## ✅ SUCCESS CRITERIA CHECKLIST

**Recently Completed & Working ✅**:
- [x] Options Trading Interface - Live data, expiration-first workflow, professional display
- [x] Price History Charts - 600px height, proper axis labels, time formatting for 1-day charts
- [x] Analyst Ratings - Ratings breakdown without crashes, proper API handling  
- [x] Market Data Integration - Stock search, quotes, company information
- [x] Account Management - Portfolio display with UITESTER01 test data

**High Priority Development Roadmap ❌**:
- [ ] Global Loading Indicators - Spinners for all long-running queries
- [ ] Performance Charts - Portfolio value over time with benchmarks
- [ ] Risk Metrics Dashboard - Portfolio concentration, beta, volatility
- [ ] Asset Allocation - Pie charts and sector breakdown

**Quality Assurance**:
- [ ] No console errors in browser dev tools
- [ ] All working components respond correctly  
- [ ] Loading states where implemented work properly
- [ ] Error handling graceful for network issues
- [ ] Responsive design functions on mobile/tablet

---

## 🎯 Updated Testing Timeline

**Immediate Testing (Working Components)**: 15-20 minutes
- Options chain, charts, ratings, research functionality  
- Portfolio display and account management
- Basic error handling and responsive design

**Future Testing (Development Roadmap)**: 30-45 minutes  
- Portfolio analytics suite (performance, risk, allocation)
- Loading state improvements across all components

**Current Focus**: Test and validate recently completed components while identifying areas needing loading state improvements.