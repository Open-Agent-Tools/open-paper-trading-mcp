# User Testing Script - New Frontend Elements
**Open Paper Trading MCP - Frontend Testing Narrative**

## Overview
This script provides a step-by-step testing narrative for all newly implemented frontend components. Use the UITESTER01 account which has comprehensive test data including 5 stock positions ($99K+ portfolio value) and historical orders.

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

## 📊 PHASE 1: Portfolio Analytics Testing

### Test 1.1: Performance Chart Component
**Location**: Dashboard or Portfolio section

**Narrative**: 
*"As a trader, I want to see how my portfolio has performed over time to evaluate my trading strategy effectiveness."*

**Testing Steps**:
1. Navigate to Portfolio Analytics section
2. Locate the **Performance Chart** component
3. Verify chart displays with time series data
4. Test time period selectors (1M, 3M, 6M, 1Y, All)
5. Hover over chart points to see detailed values
6. Check that chart shows portfolio growth trajectory

**Expected Results**:
- Interactive chart with historical performance simulation
- Responsive design on different screen sizes
- Loading state displays while fetching data
- Error handling if API fails
- Chart shows positive performance based on UITESTER01 portfolio (+59.45% unrealized gains)

### Test 1.2: Risk Metrics Dashboard
**Location**: Portfolio Analytics section

**Narrative**:
*"As a risk-conscious investor, I need to understand my portfolio's risk profile including concentration, diversification, and volatility metrics."*

**Testing Steps**:
1. Locate the **Risk Metrics** component
2. Verify display of key metrics:
   - Portfolio Concentration (should show concentration due to SPY position)
   - Diversification Score
   - Estimated Portfolio Beta
   - Volatility Metrics
3. Check that metrics update based on current positions
4. Verify explanatory tooltips for each metric

**Expected Results**:
- Clear display of risk statistics
- Color-coded risk levels (Green/Yellow/Red)
- Proper calculation based on 5-stock portfolio
- Responsive card layout

### Test 1.3: Asset Allocation Visualization
**Location**: Portfolio Analytics section

**Narrative**:
*"I want to visualize how my investments are distributed across different asset types and individual holdings."*

**Testing Steps**:
1. Find the **Asset Allocation** component
2. Verify pie chart displays with 5 segments for each stock
3. Check allocation percentages add up to 100%
4. Test toggle between "By Asset Type" and "By Individual Holdings"
5. Verify table view shows detailed breakdown
6. Check that largest holding (SPY) is prominently displayed

**Expected Results**:
- Interactive pie chart with hover effects
- Accurate percentages for each position
- Table view with sorting capabilities
- SPY should show as largest allocation (~37% of portfolio)

---

## 📈 PHASE 2: Options Trading Interface Testing

### Test 2.1: Options Analytics Component
**Location**: Options Trading section

**Narrative**:
*"As an options trader, I need to analyze potential strategies with profit/loss diagrams and Greeks calculations."*

**Testing Steps**:
1. Navigate to Options Trading section
2. Access **Options Analytics** component
3. Enter a liquid stock symbol (e.g., "AAPL", "SPY", "MSFT")
4. Verify options chain loads with current strikes and expirations
5. Select different strike prices and expiration dates
6. Check Greeks display (Delta, Gamma, Theta, Vega, Rho)
7. Verify profit/loss diagram renders correctly

**Expected Results**:
- Options chain data loads from API
- Greeks calculations display properly
- Interactive P&L diagram shows breakeven points
- Responsive design for mobile devices
- Loading states during API calls

### Test 2.2: Spread Builder Interface
**Location**: Options Trading section

**Narrative**:
*"I want to construct multi-leg options strategies and visualize their payoff profiles before placing orders."*

**Testing Steps**:
1. Locate **Spread Builder** component
2. Select a strategy template:
   - Long Call Spread
   - Long Put Spread
   - Iron Condor
   - Long Straddle
3. Configure strategy parameters (underlying, strikes, expiration)
4. Verify payoff diagram updates in real-time
5. Check maximum profit/loss calculations
6. Test "Reset" and "Save Template" functionality

**Expected Results**:
- Strategy templates load correctly
- Interactive payoff diagrams
- Accurate profit/loss calculations
- Ability to save custom strategies
- Clear visualization of breakeven points

### Test 2.3: Expiration Calendar
**Location**: Options Trading section

**Narrative**:
*"I need to track when my options positions expire to manage risk and avoid assignment."*

**Testing Steps**:
1. Access **Options Expiration Calendar**
2. Verify calendar displays current month
3. Check color coding for expiration urgency:
   - Red: Expiring today
   - Orange: Expiring within 3 days
   - Green: Normal expiration timeframe
4. Navigate between months using arrow controls
5. Click on expiration dates to see available options

**Expected Results**:
- Calendar view with proper date navigation
- Color-coded expiration indicators
- Responsive calendar layout
- Integration with options chain data
- Clear visual hierarchy

---

## 📋 PHASE 3: Order Management Testing

### Test 3.1: Bulk Order Operations
**Location**: Order History/Management section

**Narrative**:
*"As an active trader, I need to efficiently cancel multiple orders at once rather than handling them individually."*

**Testing Steps**:
1. Navigate to Order Management section
2. Verify order history displays (should show UITESTER01's historical XOM orders)
3. Access **Bulk Order Operations** component
4. Test multi-select functionality on order list
5. Select multiple orders for cancellation
6. Verify confirmation dialog appears
7. Test "Select All" and "Clear Selection" buttons
8. Attempt bulk cancellation (should work with pending orders)

**Expected Results**:
- Multi-select checkboxes on order rows
- Confirmation dialog before bulk actions
- Progress indicator during bulk operations
- Success/error messages for each operation
- Updated order list after operations

### Test 3.2: Order Templates System
**Location**: Order Entry/Management section

**Narrative**:
*"I want to save frequently used order configurations as templates to speed up my trading workflow."*

**Testing Steps**:
1. Locate **Order Templates** component
2. Create a new order template:
   - Stock: AAPL
   - Order Type: Limit Buy
   - Quantity: 100
   - Price: $200.00
3. Save template with name "AAPL Long Position"
4. Verify template appears in saved templates list
5. Test loading template back into order form
6. Modify and update existing template
7. Test template deletion functionality

**Expected Results**:
- Template creation with validation
- Persistent storage (localStorage)
- Template list with search/filter
- One-click template loading
- Usage statistics tracking

---

## 🔍 PHASE 4: Advanced Trading Features

### Test 4.1: Watchlists Management
**Location**: Market Data/Trading section

**Narrative**:
*"I want to track specific stocks I'm interested in trading, with real-time price updates and quick access to trading actions."*

**Testing Steps**:
1. Access **Watchlists** component
2. Create a new watchlist named "Tech Stocks"
3. Search and add stocks:
   - AAPL (already in portfolio)
   - NVDA
   - META
   - AMZN
4. Verify real-time price updates
5. Check percentage change indicators (green/red)
6. Test "Add to Watchlist" from stock search
7. Remove stocks from watchlist
8. Create multiple watchlists and switch between them

**Expected Results**:
- Real-time price streaming
- Color-coded price changes
- Quick action buttons (Buy/Sell)
- Multiple watchlist support
- Persistent data storage

### Test 4.2: Alerts System
**Location**: Trading Tools section

**Narrative**:
*"I need to monitor stock prices and get notified when they reach certain levels, so I don't have to constantly watch the market."*

**Testing Steps**:
1. Navigate to **Alerts System** component
2. Create a price alert:
   - Stock: TSLA (currently in UITESTER01 portfolio)
   - Alert Type: "Price Above"
   - Target Price: $320.00 (slightly above current)
3. Create a second alert:
   - Stock: AAPL
   - Alert Type: "Price Below"  
   - Target Price: $200.00
4. Verify alerts appear in active alerts list
5. Test alert status monitoring
6. Check alert notification system (if implemented)
7. Deactivate and delete alerts

**Expected Results**:
- Alert creation with validation
- Active monitoring of price conditions
- Alert status indicators
- Historical alert log
- Easy alert management interface

---

## 🧪 PHASE 5: Error Handling & Edge Cases

### Test 5.1: API Failure Scenarios
**Narrative**:
*"The system should gracefully handle API failures and provide meaningful feedback to users."*

**Testing Steps**:
1. With browser dev tools, throttle network to "Slow 3G"
2. Test each new component's loading behavior
3. Temporarily block API calls (Network tab > Block patterns)
4. Verify error states display properly
5. Test retry functionality where available
6. Restore normal network conditions

**Expected Results**:
- Loading spinners during API calls
- Meaningful error messages
- Retry mechanisms
- Graceful degradation
- No application crashes

### Test 5.2: Data Validation Testing
**Narrative**:
*"The system should validate user inputs and prevent invalid operations."*

**Testing Steps**:
1. **Order Templates**: Try creating template with invalid data
2. **Alerts System**: Set impossible price targets
3. **Spread Builder**: Configure invalid strike combinations
4. **Watchlists**: Add invalid stock symbols
5. Verify validation messages appear
6. Test form submission prevention with invalid data

**Expected Results**:
- Client-side validation messages
- Form submission blocked for invalid data
- Clear instructions for fixing errors
- No console errors in browser

---

## 📱 PHASE 6: Responsive Design Testing

### Test 6.1: Mobile Device Simulation
**Testing Steps**:
1. Open browser dev tools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Test each component on different screen sizes:
   - iPhone 12 Pro (390x844)
   - iPad (768x1024)
   - Desktop (1920x1080)
4. Verify all components remain functional
5. Check that charts and tables are scrollable/responsive

**Expected Results**:
- Components adapt to screen size
- Touch-friendly buttons on mobile
- Scrollable tables and charts
- Readable text at all sizes
- Maintained functionality across devices

---

## ✅ SUCCESS CRITERIA CHECKLIST

After completing all testing phases, verify:

**Portfolio Analytics (4/4 components)**:
- [ ] Performance Chart loads and displays data
- [ ] Risk Metrics show calculated values  
- [ ] Asset Allocation pie chart renders correctly
- [ ] All components handle UITESTER01 data properly

**Options Trading (3/3 components)**:
- [ ] Options Analytics displays chains and Greeks
- [ ] Spread Builder creates strategy diagrams
- [ ] Expiration Calendar shows proper date navigation

**Order Management (2/2 components)**:
- [ ] Bulk Operations handles multiple order selection
- [ ] Order Templates saves and loads configurations

**Advanced Features (2/2 components)**:
- [ ] Watchlists manages stock lists with real-time prices
- [ ] Alerts System creates and monitors price alerts

**Quality Assurance**:
- [ ] No console errors in browser
- [ ] All API endpoints respond correctly
- [ ] Loading states display appropriately
- [ ] Error handling works gracefully
- [ ] Responsive design functions on mobile/tablet

---

## 🎯 Expected Completion Time
- **Full Testing**: 45-60 minutes
- **Quick Smoke Test**: 10-15 minutes  
- **Per Component**: 3-5 minutes average

This comprehensive testing script ensures all new frontend elements work correctly with the existing backend infrastructure and provide a smooth user experience for trading operations.