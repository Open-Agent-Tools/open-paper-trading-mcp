import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Alert,
  CircularProgress,
  IconButton,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tabs,
  Tab,
  Tooltip,
  Badge,
} from '@mui/material';
import {
  History as HistoryIcon,
  Refresh as RefreshIcon,
  TrendingUp as StockIcon,
  ShowChart as OptionsIcon,
  CheckCircle as FilledIcon,
  Cancel as CancelledIcon,
  Schedule as PendingIcon,
  Error as FailedIcon,
} from '@mui/icons-material';
import { getStockOrders, getOptionsOrders } from '../services/apiClient';
import { FONTS } from '../theme';
import type { OrderHistoryItem, OrderStatus } from '../types';

interface OrderHistoryProps {
  autoRefresh?: boolean;
  refreshInterval?: number; // in seconds
  maxItems?: number;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index}>
      {value === index && <Box>{children}</Box>}
    </div>
  );
};

const OrderHistory: React.FC<OrderHistoryProps> = ({ 
  autoRefresh = true,
  refreshInterval = 30,
  maxItems = 100
}) => {
  const [tabValue, setTabValue] = useState(0);
  const [stockOrders, setStockOrders] = useState<OrderHistoryItem[]>([]);
  const [optionsOrders, setOptionsOrders] = useState<OrderHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchOrderHistory = async () => {
    setLoading(true);
    setError(null);

    try {
      const [stockResponse, optionsResponse] = await Promise.all([
        getStockOrders(),
        getOptionsOrders()
      ]);

      if (stockResponse.success) {
        setStockOrders(stockResponse.orders.slice(0, maxItems));
      }

      if (optionsResponse.success) {
        setOptionsOrders(optionsResponse.orders.slice(0, maxItems));
      }

      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load order history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrderHistory();
  }, []);

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchOrderHistory, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  const getStatusIcon = (status: OrderStatus) => {
    switch (status) {
      case 'filled':
        return <FilledIcon color="success" fontSize="small" />;
      case 'cancelled':
        return <CancelledIcon color="error" fontSize="small" />;
      case 'pending':
        return <PendingIcon color="warning" fontSize="small" />;
      case 'rejected':
        return <FailedIcon color="error" fontSize="small" />;
      default:
        return <PendingIcon color="action" fontSize="small" />;
    }
  };

  const getStatusChipColor = (status: OrderStatus) => {
    switch (status) {
      case 'filled':
        return 'success' as const;
      case 'cancelled':
        return 'error' as const;
      case 'pending':
        return 'warning' as const;
      case 'rejected':
        return 'error' as const;
      default:
        return 'default' as const;
    }
  };

  const formatDateTime = (dateString: string | undefined): string => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  const formatPrice = (price: number | undefined): string => {
    if (price === undefined || price === null) return 'N/A';
    return `$${price.toFixed(2)}`;
  };

  const formatQuantity = (quantity: number, filledQuantity?: number): string => {
    if (filledQuantity !== undefined && filledQuantity !== quantity) {
      return `${filledQuantity}/${quantity}`;
    }
    return quantity.toString();
  };

  const renderOrdersTable = (orders: OrderHistoryItem[], type: 'stocks' | 'options') => {
    if (orders.length === 0) {
      return (
        <Box py={4} textAlign="center">
          <Typography variant="body2" color="text.secondary">
            No {type} order history found
          </Typography>
        </Box>
      );
    }

    return (
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Quantity</TableCell>
              <TableCell>Price</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Filled</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orders.map((order, index) => (
              <TableRow key={order.id || index} hover>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: FONTS.monospace, fontWeight: 500 }}>
                    {order.symbol}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Chip
                      label={order.order_type}
                      size="small"
                      color={order.order_type === 'buy' ? 'success' : 'error'}
                      variant="outlined"
                    />
                    <Typography variant="caption" color="text.secondary">
                      {order.condition}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                    {formatQuantity(order.quantity, order.filled_quantity)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                      {formatPrice(order.price)}
                    </Typography>
                    {order.average_filled_price && order.average_filled_price !== order.price && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: FONTS.monospace }}>
                        Avg: {formatPrice(order.average_filled_price)}
                      </Typography>
                    )}
                  </Box>
                </TableCell>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={1}>
                    {getStatusIcon(order.status)}
                    <Chip
                      label={order.status}
                      size="small"
                      color={getStatusChipColor(order.status)}
                      variant="filled"
                    />
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                    {formatDateTime(order.created_at)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                    {order.status === 'filled' ? formatDateTime(order.filled_at) : '-'}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  const getTabLabel = (label: string, count: number) => (
    <Box display="flex" alignItems="center" gap={1}>
      {label}
      <Badge badgeContent={count} color="primary" max={99} />
    </Box>
  );

  if (loading && stockOrders.length === 0 && optionsOrders.length === 0) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading order history...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <HistoryIcon color="primary" />
            <Typography variant="h6">
              Order History
            </Typography>
          </Box>
        }
        action={
          <Box display="flex" alignItems="center" gap={1}>
            {lastUpdated && (
              <Tooltip title={`Last updated: ${lastUpdated.toLocaleTimeString()}`}>
                <Typography variant="caption" color="text.secondary">
                  {lastUpdated.toLocaleTimeString()}
                </Typography>
              </Tooltip>
            )}
            <IconButton onClick={fetchOrderHistory} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Box>
        }
      />
      
      <CardContent>
        {error && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
            <Tab 
              label={getTabLabel('Stocks', stockOrders.length)} 
              icon={<StockIcon />} 
              iconPosition="start"
            />
            <Tab 
              label={getTabLabel('Options', optionsOrders.length)} 
              icon={<OptionsIcon />} 
              iconPosition="start"
            />
          </Tabs>
        </Box>

        <TabPanel value={tabValue} index={0}>
          {renderOrdersTable(stockOrders, 'stocks')}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {renderOrdersTable(optionsOrders, 'options')}
        </TabPanel>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
          Real-time order status updates • Auto-refresh every {refreshInterval}s
        </Typography>
      </CardContent>
    </Card>
  );
};

export default OrderHistory;