import React, { useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Typography,
  TextField,
  Button,
  Alert,
  Divider,
  Chip,
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  AccountBalance as AccountIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useAccountContext, useRequireAccount } from '../contexts/AccountContext';

/**
 * Example 1: Trading Component that requires an account
 * 
 * This component demonstrates:
 * - Using useRequireAccount hook for required account context
 * - Accessing selected account data throughout the component
 * - Error handling when account context is missing
 */
const TradingFormExample: React.FC = () => {
  // This hook will throw an error if no account is selected
  // Use this pattern for components that absolutely require an account
  const selectedAccount = useRequireAccount();
  
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState('');
  const [orderType, setOrderType] = useState('market');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmitOrder = useCallback(async () => {
    setIsSubmitting(true);
    
    try {
      // Example API call using selected account
      const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: selectedAccount.id, // Use selected account
          symbol,
          quantity: parseInt(quantity),
          order_type: orderType,
        }),
      });
      
      if (!response.ok) throw new Error('Order failed');
      
      console.log('Order placed successfully for account:', selectedAccount.owner);
    } catch (error) {
      console.error('Order failed:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedAccount.id, selectedAccount.owner, symbol, quantity, orderType]);

  return (
    <Card>
      <CardHeader
        title="Place Order"
        subheader={`Trading as: ${selectedAccount.owner} (${selectedAccount.id})`}
        avatar={<TrendingUpIcon color="primary" />}
      />
      <CardContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          Available Balance: {selectedAccount.current_balance.toLocaleString('en-US', {
            style: 'currency',
            currency: 'USD',
          })}
        </Alert>
        
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="e.g., AAPL"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Quantity"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>Order Type</InputLabel>
              <Select
                value={orderType}
                label="Order Type"
                onChange={(e) => setOrderType(e.target.value)}
              >
                <MenuItem value="market">Market</MenuItem>
                <MenuItem value="limit">Limit</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
        
        <Box sx={{ mt: 2 }}>
          <Button
            variant="contained"
            fullWidth
            onClick={handleSubmitOrder}
            disabled={!symbol || !quantity || isSubmitting}
          >
            {isSubmitting ? 'Placing Order...' : 'Place Order'}
          </Button>
          {isSubmitting && <LinearProgress sx={{ mt: 1 }} />}
        </Box>
      </CardContent>
    </Card>
  );
};

/**
 * Example 2: Portfolio Component with flexible account context
 * 
 * This component demonstrates:
 * - Using useAccountContext hook for optional account access
 * - Graceful handling of missing account context
 * - Conditional rendering based on account selection
 */
const PortfolioExample: React.FC = () => {
  const { selectedAccount, availableAccounts, selectAccount } = useAccountContext();

  if (!selectedAccount) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <WarningIcon sx={{ fontSize: 48, color: 'warning.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            No Account Selected
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Please select an account to view your portfolio
          </Typography>
          {availableAccounts.length > 0 && (
            <Box>
              <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                Quick Select:
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
                {availableAccounts.slice(0, 3).map((account) => (
                  <Chip
                    key={account.id}
                    label={account.owner}
                    onClick={() => selectAccount(account)}
                    clickable
                    size="small"
                    icon={<AccountIcon />}
                  />
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Portfolio Overview"
        subheader={`Account: ${selectedAccount.owner}`}
        action={
          <Chip
            label={selectedAccount.id}
            size="small"
            variant="outlined"
          />
        }
      />
      <CardContent>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Current Balance
            </Typography>
            <Typography variant="h6">
              {selectedAccount.current_balance.toLocaleString('en-US', {
                style: 'currency',
                currency: 'USD',
              })}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Total Change
            </Typography>
            <Typography 
              variant="h6"
              sx={{
                color: selectedAccount.balance_change >= 0 ? 'success.main' : 'error.main',
              }}
            >
              {selectedAccount.balance_change >= 0 ? '+' : ''}
              {selectedAccount.balance_change.toLocaleString('en-US', {
                style: 'currency',
                currency: 'USD',
              })}
            </Typography>
          </Grid>
        </Grid>
        
        <Divider sx={{ my: 2 }} />
        
        <Typography variant="body2" color="text.secondary">
          Started with: {selectedAccount.starting_balance.toLocaleString('en-US', {
            style: 'currency',
            currency: 'USD',
          })}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Change: {selectedAccount.balance_change_percent.toFixed(2)}%
        </Typography>
      </CardContent>
    </Card>
  );
};

/**
 * Example 3: Account-Aware API Hook
 * 
 * This demonstrates how to create custom hooks that automatically
 * use the selected account context for API calls
 */
const useAccountOrders = () => {
  const { selectedAccount } = useAccountContext();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = useCallback(async () => {
    if (!selectedAccount) {
      setOrders([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/accounts/${selectedAccount.id}/orders`);
      if (!response.ok) throw new Error('Failed to fetch orders');
      
      const data = await response.json();
      setOrders(data.orders || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch orders');
    } finally {
      setLoading(false);
    }
  }, [selectedAccount]);

  return { orders, loading, error, refetch: fetchOrders };
};

/**
 * Example 4: Component using custom account-aware hook
 */
const OrderHistoryExample: React.FC = () => {
  const { selectedAccount } = useAccountContext();
  const { orders, loading, error, refetch } = useAccountOrders();

  // Automatically fetch orders when account changes
  React.useEffect(() => {
    refetch();
  }, [selectedAccount, refetch]);

  if (!selectedAccount) {
    return (
      <Alert severity="info">
        Select an account to view order history
      </Alert>
    );
  }

  if (loading) {
    return (
      <Box sx={{ p: 2 }}>
        <LinearProgress />
        <Typography variant="body2" sx={{ mt: 1 }}>
          Loading orders for {selectedAccount.owner}...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button size="small" onClick={refetch}>
          Retry
        </Button>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Order History"
        subheader={`${orders.length} orders for ${selectedAccount.owner}`}
        action={
          <Button size="small" onClick={refetch}>
            Refresh
          </Button>
        }
      />
      <CardContent>
        {orders.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No orders found for this account
          </Typography>
        ) : (
          <Typography variant="body2">
            {orders.length} orders loaded successfully
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

/**
 * Example 5: Complete component with error boundary pattern
 */
const TradingDashboardExample: React.FC = () => {
  const [error, setError] = useState<string | null>(null);

  if (error) {
    return (
      <Alert severity="error" onClose={() => setError(null)}>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Account Context Examples
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Example 1: Required Account Component
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Uses useRequireAccount() - will throw error if no account selected
            </Typography>
            <ErrorBoundary onError={setError}>
              <TradingFormExample />
            </ErrorBoundary>
          </Box>
        </Grid>

        <Grid item xs={12} md={6}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Example 2: Flexible Account Component
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Uses useAccountContext() - gracefully handles missing account
            </Typography>
            <PortfolioExample />
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Example 3: Account-Aware Hook Usage
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Custom hook that automatically uses selected account for API calls
            </Typography>
            <OrderHistoryExample />
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

/**
 * Simple Error Boundary for demonstration
 */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode; onError: (error: string) => void },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    this.props.onError(error.message);
  }

  render() {
    if (this.state.hasError) {
      return null; // Error will be shown by parent
    }

    return this.props.children;
  }
}

export default TradingDashboardExample;
export {
  TradingFormExample,
  PortfolioExample,
  OrderHistoryExample,
  useAccountOrders,
};