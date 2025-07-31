import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, CardContent, Typography, Box, Chip, LinearProgress, IconButton,
  Collapse, Alert, Button, Grid, Divider, Tooltip
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Schedule as ScheduleIcon,
  TrendingUp as TrendingUpIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import type { Order } from '../types';
import { getOrders, getStockPrice } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';

interface OrderExecutionMonitorProps {
  refreshInterval?: number; // milliseconds
  showOnlyActive?: boolean;
  maxOrdersToShow?: number;
}

interface OrderWithExecution extends Order {
  priceProgress?: number;
  executionProbability?: 'high' | 'medium' | 'low';
  timeToFill?: string;
  currentPrice?: number;
}

const OrderExecutionMonitor: React.FC<OrderExecutionMonitorProps> = ({
  refreshInterval = 10000, // 10 seconds
  showOnlyActive = true,
  maxOrdersToShow = 10
}) => {
  const [orders, setOrders] = useState<OrderWithExecution[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedOrders, setExpandedOrders] = useState<Set<string>>(new Set());
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  
  const { selectedAccount } = useAccountContext();

  const fetchOrdersWithExecution = useCallback(async () => {
    if (!selectedAccount) return;

    setLoading(true);
    setError(null);

    try {
      const response = await getOrders(selectedAccount.id);
      if (response.success && response.orders) {
        let ordersToProcess = response.orders;

        // Filter to active orders if requested
        if (showOnlyActive) {
          ordersToProcess = ordersToProcess.filter((order: Order) => 
            ['pending', 'triggered', 'partially_filled'].includes(order.status)
          );
        }

        // Limit number of orders
        ordersToProcess = ordersToProcess.slice(0, maxOrdersToShow);

        // Enhance orders with execution data
        const enhancedOrders = await Promise.all(
          ordersToProcess.map(async (order: Order): Promise<OrderWithExecution> => {
            try {
              // Get current price for analysis
              const priceResponse = await getStockPrice(order.symbol);
              const currentPrice = priceResponse.success ? priceResponse.price_data?.price : null;

              return {
                ...order,
                currentPrice: currentPrice ?? undefined,
                ...calculateExecutionMetrics(order, currentPrice)
              };
            } catch (error) {
              return order;
            }
          })
        );

        setOrders(enhancedOrders);
        setLastUpdate(new Date());
      } else {
        setError(response.message || 'Failed to fetch orders');
      }
    } catch (error) {
      setError('Failed to fetch order data');
      console.error('Order fetch error:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedAccount, showOnlyActive, maxOrdersToShow]);

  const calculateExecutionMetrics = (order: Order, currentPrice: number | null | undefined) => {
    if (!currentPrice) return {};

    const metrics: Partial<OrderWithExecution> = {};

    // Calculate price progress for limit orders
    if (order.condition === 'limit' && order.price) {
      if (order.order_type === 'buy') {
        // For buy limit orders, closer to or below limit price is better
        metrics.priceProgress = Math.max(0, Math.min(100, 
          ((order.price - currentPrice) / order.price) * 100
        ));
      } else {
        // For sell limit orders, closer to or above limit price is better
        metrics.priceProgress = Math.max(0, Math.min(100, 
          ((currentPrice - order.price) / order.price) * 100
        ));
      }
    }

    // Calculate execution probability based on order type and current conditions
    if (order.condition === 'market') {
      metrics.executionProbability = 'high';
      metrics.timeToFill = 'Immediate';
    } else if (order.condition === 'limit' && order.price) {
      const priceDiff = Math.abs(currentPrice - order.price) / order.price;
      if (priceDiff < 0.01) { // Within 1%
        metrics.executionProbability = 'high';
        metrics.timeToFill = '< 1 minute';
      } else if (priceDiff < 0.05) { // Within 5%
        metrics.executionProbability = 'medium';
        metrics.timeToFill = '5-30 minutes';
      } else {
        metrics.executionProbability = 'low';
        metrics.timeToFill = 'Unknown';
      }
    } else if (order.condition === 'stop' && order.stop_price) {
      const priceDiff = Math.abs(currentPrice - order.stop_price) / order.stop_price;
      if (priceDiff < 0.02) { // Within 2%
        metrics.executionProbability = 'medium';
        metrics.timeToFill = 'When triggered';
      } else {
        metrics.executionProbability = 'low';
        metrics.timeToFill = 'When price moves';
      }
    }

    return metrics;
  };

  // Auto-refresh effect
  useEffect(() => {
    fetchOrdersWithExecution();
    
    const interval = setInterval(fetchOrdersWithExecution, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchOrdersWithExecution, refreshInterval]);

  const toggleOrderExpansion = (orderId: string) => {
    const newExpanded = new Set(expandedOrders);
    if (newExpanded.has(orderId)) {
      newExpanded.delete(orderId);
    } else {
      newExpanded.add(orderId);
    }
    setExpandedOrders(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'filled':
        return <CheckCircleIcon color="success" />;
      case 'cancelled':
      case 'rejected':
        return <CancelIcon color="error" />;
      case 'pending':
      case 'triggered':
        return <ScheduleIcon color="warning" />;
      default:
        return <TrendingUpIcon color="info" />;
    }
  };

  const getExecutionProbabilityColor = (probability?: string) => {
    switch (probability) {
      case 'high': return 'success';
      case 'medium': return 'warning';
      case 'low': return 'error';
      default: return 'default';
    }
  };

  if (error) {
    return (
      <Alert 
        severity="error" 
        action={
          <Button color="inherit" size="small" onClick={fetchOrdersWithExecution}>
            Retry
          </Button>
        }
      >
        {error}
      </Alert>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Order Execution Monitor
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {lastUpdate && (
              <Typography variant="caption" color="text.secondary">
                Last update: {lastUpdate.toLocaleTimeString()}
              </Typography>
            )}
            <Tooltip title="Refresh now">
              <IconButton onClick={fetchOrdersWithExecution} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {loading && orders.length === 0 && <LinearProgress sx={{ mb: 2 }} />}

        {orders.length === 0 && !loading ? (
          <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 3 }}>
            {showOnlyActive ? 'No active orders to monitor' : 'No orders found'}
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {orders.map((order) => (
              <Card key={order.id} variant="outlined">
                <CardContent sx={{ pb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      {getStatusIcon(order.status)}
                      <Box>
                        <Typography variant="subtitle1" fontWeight="bold">
                          {order.order_type.toUpperCase()} {order.quantity} {order.symbol}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {order.condition.toUpperCase()} 
                          {order.price && ` @ $${order.price.toFixed(2)}`}
                          {order.stop_price && ` (Stop: $${order.stop_price.toFixed(2)})`}
                        </Typography>
                      </Box>
                    </Box>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip 
                        label={order.status.toUpperCase()} 
                        color={order.status === 'filled' ? 'success' : 
                               order.status === 'cancelled' ? 'error' : 'warning'}
                        size="small"
                      />
                      {order.executionProbability && (
                        <Chip
                          label={`${order.executionProbability.toUpperCase()} PROB`}
                          color={getExecutionProbabilityColor(order.executionProbability)}
                          size="small"
                          variant="outlined"
                        />
                      )}
                      <IconButton 
                        onClick={() => toggleOrderExpansion(order.id)}
                        size="small"
                      >
                        {expandedOrders.has(order.id) ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                      </IconButton>
                    </Box>
                  </Box>

                  <Collapse in={expandedOrders.has(order.id)} timeout="auto">
                    <Divider sx={{ my: 2 }} />
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Current Market Price
                        </Typography>
                        <Typography variant="h6">
                          {order.currentPrice ? `$${order.currentPrice.toFixed(2)}` : 'Loading...'}
                        </Typography>
                      </Grid>
                      
                      {order.timeToFill && (
                        <Grid item xs={12} sm={6}>
                          <Typography variant="body2" color="text.secondary" gutterBottom>
                            Estimated Fill Time
                          </Typography>
                          <Typography variant="h6">
                            {order.timeToFill}
                          </Typography>
                        </Grid>
                      )}

                      {order.priceProgress !== undefined && (
                        <Grid item xs={12}>
                          <Typography variant="body2" color="text.secondary" gutterBottom>
                            Price Progress to Execution
                          </Typography>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress 
                              variant="determinate" 
                              value={order.priceProgress} 
                              sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                              color={order.priceProgress > 75 ? 'success' : 
                                     order.priceProgress > 25 ? 'warning' : 'error'}
                            />
                            <Typography variant="body2" fontWeight="bold">
                              {order.priceProgress.toFixed(1)}%
                            </Typography>
                          </Box>
                        </Grid>
                      )}

                      <Grid item xs={12}>
                        <Typography variant="body2" color="text.secondary">
                          Created: {order.created_at ? new Date(order.created_at).toLocaleString() : 'N/A'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Collapse>
                </CardContent>
              </Card>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default OrderExecutionMonitor;