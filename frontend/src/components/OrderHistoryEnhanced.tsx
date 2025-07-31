import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card, CardContent, CardHeader, Typography, Box, Alert, CircularProgress,
  IconButton, Chip, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Paper, Tabs, Tab, Tooltip, Badge, TextField, InputAdornment,
  FormControl, InputLabel, Select, MenuItem, Button, Grid, Divider,
  TableSortLabel, TablePagination, Accordion, AccordionSummary, AccordionDetails,
  Stack, useTheme
} from '@mui/material';
import {
  History as HistoryIcon, Refresh as RefreshIcon, TrendingUp as StockIcon,
  ShowChart as OptionsIcon, CheckCircle as FilledIcon, Cancel as CancelledIcon,
  Schedule as PendingIcon, Error as FailedIcon, Search as SearchIcon,
  FilterList as FilterIcon, Analytics as AnalyticsIcon, ExpandMore as ExpandMoreIcon,
  Download as DownloadIcon, Clear as ClearIcon
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { getStockOrders, getOptionsOrders } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';
import { FONTS } from '../theme';
import type { OrderHistoryItem, OrderStatus } from '../types';

interface OrderHistoryEnhancedProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  maxItems?: number;
}

interface FilterState {
  search: string;
  status: string;
  orderType: string;
  dateFrom: Date | null;
  dateTo: Date | null;
  symbol: string;
  priceMin: string;
  priceMax: string;
}

interface SortState {
  field: keyof OrderHistoryItem;
  direction: 'asc' | 'desc';
}

interface OrderAnalytics {
  totalOrders: number;
  filledOrders: number;
  cancelledOrders: number;
  pendingOrders: number;
  totalVolume: number;
  averageOrderSize: number;
  successRate: number;
  topSymbols: Array<{ symbol: string; count: number; volume: number }>;
  ordersByMonth: Array<{ month: string; count: number }>;
}

const OrderHistoryEnhanced: React.FC<OrderHistoryEnhancedProps> = ({
  autoRefresh = true,
  refreshInterval = 30,
  maxItems = 1000
}) => {
  const theme = useTheme();
  const [tabValue, setTabValue] = useState(0);
  const [stockOrders, setStockOrders] = useState<OrderHistoryItem[]>([]);
  const [optionsOrders, setOptionsOrders] = useState<OrderHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  
  const { selectedAccount } = useAccountContext();

  const [filters, setFilters] = useState<FilterState>({
    search: '',
    status: '',
    orderType: '',
    dateFrom: null,
    dateTo: null,
    symbol: '',
    priceMin: '',
    priceMax: ''
  });

  const [sort, setSort] = useState<SortState>({
    field: 'created_at',
    direction: 'desc'
  });

  const fetchOrderHistory = useCallback(async () => {
    if (!selectedAccount) {
      setStockOrders([]);
      setOptionsOrders([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [stockResponse, optionsResponse] = await Promise.all([
        getStockOrders(selectedAccount.id),
        getOptionsOrders(selectedAccount.id)
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
  }, [selectedAccount, maxItems]);

  useEffect(() => {
    fetchOrderHistory();
  }, [fetchOrderHistory]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchOrderHistory, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchOrderHistory]);

  // Filter and sort logic
  const filterOrders = useCallback((orders: OrderHistoryItem[]) => {
    return orders.filter(order => {
      // Search filter
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        if (!order.symbol.toLowerCase().includes(searchLower) &&
            !order.order_type.toLowerCase().includes(searchLower) &&
            !order.condition.toLowerCase().includes(searchLower)) {
          return false;
        }
      }

      // Status filter
      if (filters.status && order.status !== filters.status) {
        return false;
      }

      // Order type filter
      if (filters.orderType && order.order_type !== filters.orderType) {
        return false;
      }

      // Symbol filter
      if (filters.symbol && !order.symbol.toLowerCase().includes(filters.symbol.toLowerCase())) {
        return false;
      }

      // Date filters
      if (filters.dateFrom) {
        const orderDate = new Date(order.created_at);
        if (orderDate < filters.dateFrom) {
          return false;
        }
      }

      if (filters.dateTo) {
        const orderDate = new Date(order.created_at);
        if (orderDate > filters.dateTo) {
          return false;
        }
      }

      // Price filters
      const orderPrice = order.price || 0;
      if (filters.priceMin && orderPrice < parseFloat(filters.priceMin)) {
        return false;
      }

      if (filters.priceMax && orderPrice > parseFloat(filters.priceMax)) {
        return false;
      }

      return true;
    });
  }, [filters]);

  const sortOrders = useCallback((orders: OrderHistoryItem[]) => {
    return [...orders].sort((a, b) => {
      const aValue = a[sort.field];
      const bValue = b[sort.field];
      
      if (aValue === undefined || aValue === null) return 1;
      if (bValue === undefined || bValue === null) return -1;
      
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        const comparison = aValue.localeCompare(bValue);
        return sort.direction === 'asc' ? comparison : -comparison;
      }
      
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sort.direction === 'asc' ? aValue - bValue : bValue - aValue;
      }
      
      // Handle date strings
      if (sort.field === 'created_at' || sort.field === 'filled_at') {
        const dateA = new Date(aValue as string);
        const dateB = new Date(bValue as string);
        return sort.direction === 'asc' ? dateA.getTime() - dateB.getTime() : dateB.getTime() - dateA.getTime();
      }
      
      return 0;
    });
  }, [sort]);

  // Calculate analytics
  const calculateAnalytics = useCallback((orders: OrderHistoryItem[]): OrderAnalytics => {
    const totalOrders = orders.length;
    const filledOrders = orders.filter(o => o.status === 'filled').length;
    const cancelledOrders = orders.filter(o => o.status === 'cancelled').length;
    const pendingOrders = orders.filter(o => o.status === 'pending').length;
    
    const totalVolume = orders.reduce((sum, order) => {
      const price = order.average_filled_price || order.price || 0;
      return sum + (price * (order.filled_quantity || order.quantity));
    }, 0);
    
    const averageOrderSize = totalOrders > 0 ? totalVolume / totalOrders : 0;
    const successRate = totalOrders > 0 ? (filledOrders / totalOrders) * 100 : 0;
    
    // Calculate top symbols
    const symbolStats = new Map<string, { count: number; volume: number }>();
    orders.forEach(order => {
      const current = symbolStats.get(order.symbol) || { count: 0, volume: 0 };
      const price = order.average_filled_price || order.price || 0;
      const volume = price * (order.filled_quantity || order.quantity);
      
      symbolStats.set(order.symbol, {
        count: current.count + 1,
        volume: current.volume + volume
      });
    });
    
    const topSymbols = Array.from(symbolStats.entries())
      .map(([symbol, stats]) => ({ symbol, ...stats }))
      .sort((a, b) => b.volume - a.volume)
      .slice(0, 5);
    
    // Calculate orders by month
    const monthStats = new Map<string, number>();
    orders.forEach(order => {
      const date = new Date(order.created_at);
      const monthKey = date.toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
      monthStats.set(monthKey, (monthStats.get(monthKey) || 0) + 1);
    });
    
    const ordersByMonth = Array.from(monthStats.entries())
      .map(([month, count]) => ({ month, count }))
      .sort((a, b) => new Date(a.month).getTime() - new Date(b.month).getTime())
      .slice(-6); // Last 6 months
    
    return {
      totalOrders,
      filledOrders,
      cancelledOrders,
      pendingOrders,
      totalVolume,
      averageOrderSize,
      successRate,
      topSymbols,
      ordersByMonth
    };
  }, []);

  // Get current orders based on tab and filters
  const currentOrders = useMemo(() => {
    const orders = tabValue === 0 ? stockOrders : optionsOrders;
    const filtered = filterOrders(orders);
    return sortOrders(filtered);
  }, [tabValue, stockOrders, optionsOrders, filterOrders, sortOrders]);

  const paginatedOrders = useMemo(() => {
    const startIndex = page * rowsPerPage;
    return currentOrders.slice(startIndex, startIndex + rowsPerPage);
  }, [currentOrders, page, rowsPerPage]);

  const analytics = useMemo(() => {
    return calculateAnalytics(currentOrders);
  }, [currentOrders, calculateAnalytics]);

  const handleSort = (field: keyof OrderHistoryItem) => {
    setSort(prev => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const clearFilters = () => {
    setFilters({
      search: '',
      status: '',
      orderType: '',
      dateFrom: null,
      dateTo: null,
      symbol: '',
      priceMin: '',
      priceMax: ''
    });
    setPage(0);
  };

  const exportToCSV = () => {
    const headers = ['Symbol', 'Type', 'Condition', 'Quantity', 'Price', 'Status', 'Created', 'Filled'];
    const csvContent = [
      headers.join(','),
      ...currentOrders.map(order => [
        order.symbol,
        order.order_type,
        order.condition,
        order.quantity,
        order.price || '',
        order.status,
        order.created_at,
        order.filled_at || ''
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `order-history-${tabValue === 0 ? 'stocks' : 'options'}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const getStatusIcon = (status: OrderStatus) => {
    switch (status) {
      case 'filled': return <FilledIcon color="success" fontSize="small" />;
      case 'cancelled': return <CancelledIcon color="error" fontSize="small" />;
      case 'pending': return <PendingIcon color="warning" fontSize="small" />;
      case 'rejected': return <FailedIcon color="error" fontSize="small" />;
      default: return <PendingIcon color="action" fontSize="small" />;
    }
  };

  const getStatusChipColor = (status: OrderStatus) => {
    switch (status) {
      case 'filled': return 'success' as const;
      case 'cancelled': return 'error' as const;
      case 'pending': return 'warning' as const;
      case 'rejected': return 'error' as const;
      default: return 'default' as const;
    }
  };

  const formatDateTime = (dateString: string | undefined): string => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString('en-US', {
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
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <HistoryIcon color="primary" />
              <Typography variant="h6">Advanced Order History</Typography>
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
              <Button
                startIcon={<DownloadIcon />}
                onClick={exportToCSV}
                size="small"
                disabled={currentOrders.length === 0}
              >
                Export
              </Button>
              <IconButton onClick={() => setShowFilters(!showFilters)}>
                <FilterIcon color={showFilters ? 'primary' : 'inherit'} />
              </IconButton>
              <IconButton onClick={() => setShowAnalytics(!showAnalytics)}>
                <AnalyticsIcon color={showAnalytics ? 'primary' : 'inherit'} />
              </IconButton>
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

          {/* Analytics Panel */}
          <Accordion expanded={showAnalytics} onChange={() => setShowAnalytics(!showAnalytics)}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Order Analytics</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={3}>
                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h4" color="primary">{analytics.totalOrders}</Typography>
                      <Typography variant="body2">Total Orders</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h4" color="success.main">{analytics.successRate.toFixed(1)}%</Typography>
                      <Typography variant="body2">Success Rate</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h4" color="info.main">${analytics.totalVolume.toFixed(0)}</Typography>
                      <Typography variant="body2">Total Volume</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h4" color="warning.main">${analytics.averageOrderSize.toFixed(0)}</Typography>
                      <Typography variant="body2">Avg Order Size</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                
                {analytics.topSymbols.length > 0 && (
                  <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Top Symbols by Volume</Typography>
                    <Stack spacing={1}>
                      {analytics.topSymbols.map((item, index) => (
                        <Box key={item.symbol} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2">#{index + 1} {item.symbol}</Typography>
                          <Box sx={{ display: 'flex', gap: 2 }}>
                            <Typography variant="body2">{item.count} orders</Typography>
                            <Typography variant="body2" fontWeight="bold">${item.volume.toFixed(0)}</Typography>
                          </Box>
                        </Box>
                      ))}
                    </Stack>
                  </Grid>
                )}
              </Grid>
            </AccordionDetails>
          </Accordion>

          {/* Filters Panel */}
          <Accordion expanded={showFilters} onChange={() => setShowFilters(!showFilters)}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Filters & Search</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <TextField
                    fullWidth
                    label="Search"
                    value={filters.search}
                    onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon />
                        </InputAdornment>
                      ),
                    }}
                    placeholder="Symbol, order type, condition..."
                  />
                </Grid>
                <Grid item xs={12} md={2}>
                  <FormControl fullWidth>
                    <InputLabel>Status</InputLabel>
                    <Select
                      value={filters.status}
                      label="Status"
                      onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
                    >
                      <MenuItem value="">All</MenuItem>
                      <MenuItem value="filled">Filled</MenuItem>
                      <MenuItem value="pending">Pending</MenuItem>
                      <MenuItem value="cancelled">Cancelled</MenuItem>
                      <MenuItem value="rejected">Rejected</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={2}>
                  <FormControl fullWidth>
                    <InputLabel>Order Type</InputLabel>
                    <Select
                      value={filters.orderType}
                      label="Order Type"
                      onChange={(e) => setFilters(prev => ({ ...prev, orderType: e.target.value }))}
                    >
                      <MenuItem value="">All</MenuItem>
                      <MenuItem value="buy">Buy</MenuItem>
                      <MenuItem value="sell">Sell</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={2}>
                  <TextField
                    fullWidth
                    label="Symbol"
                    value={filters.symbol}
                    onChange={(e) => setFilters(prev => ({ ...prev, symbol: e.target.value }))}
                    placeholder="AAPL, MSFT..."
                  />
                </Grid>
                <Grid item xs={12} md={2}>
                  <Button
                    fullWidth
                    variant="outlined"
                    onClick={clearFilters}
                    startIcon={<ClearIcon />}
                  >
                    Clear
                  </Button>
                </Grid>
                
                <Grid item xs={12} md={3}>
                  <DatePicker
                    label="From Date"
                    value={filters.dateFrom}
                    onChange={(date) => setFilters(prev => ({ ...prev, dateFrom: date }))}
                    slotProps={{ textField: { fullWidth: true } }}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <DatePicker
                    label="To Date"
                    value={filters.dateTo}
                    onChange={(date) => setFilters(prev => ({ ...prev, dateTo: date }))}
                    slotProps={{ textField: { fullWidth: true } }}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <TextField
                    fullWidth
                    label="Min Price"
                    type="number"
                    value={filters.priceMin}
                    onChange={(e) => setFilters(prev => ({ ...prev, priceMin: e.target.value }))}
                    inputProps={{ min: 0, step: 0.01 }}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <TextField
                    fullWidth
                    label="Max Price"
                    type="number"
                    value={filters.priceMax}
                    onChange={(e) => setFilters(prev => ({ ...prev, priceMax: e.target.value }))}
                    inputProps={{ min: 0, step: 0.01 }}
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          <Divider sx={{ my: 2 }} />

          {/* Tabs */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
            <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
              <Tab
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    Stocks
                    <Badge badgeContent={filterOrders(stockOrders).length} color="primary" max={999} />
                  </Box>
                }
                icon={<StockIcon />}
                iconPosition="start"
              />
              <Tab
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    Options
                    <Badge badgeContent={filterOrders(optionsOrders).length} color="primary" max={999} />
                  </Box>
                }
                icon={<OptionsIcon />}
                iconPosition="start"
              />
            </Tabs>
          </Box>

          {/* Orders Table */}
          {currentOrders.length === 0 ? (
            <Box py={4} textAlign="center">
              <Typography variant="body2" color="text.secondary">
                No orders found matching the current filters
              </Typography>
            </Box>
          ) : (
            <>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'symbol'}
                          direction={sort.field === 'symbol' ? sort.direction : 'asc'}
                          onClick={() => handleSort('symbol')}
                        >
                          Symbol
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'order_type'}
                          direction={sort.field === 'order_type' ? sort.direction : 'asc'}
                          onClick={() => handleSort('order_type')}
                        >
                          Type
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'quantity'}
                          direction={sort.field === 'quantity' ? sort.direction : 'asc'}
                          onClick={() => handleSort('quantity')}
                        >
                          Quantity
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'price'}
                          direction={sort.field === 'price' ? sort.direction : 'asc'}
                          onClick={() => handleSort('price')}
                        >
                          Price
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'status'}
                          direction={sort.field === 'status' ? sort.direction : 'asc'}
                          onClick={() => handleSort('status')}
                        >
                          Status
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'created_at'}
                          direction={sort.field === 'created_at' ? sort.direction : 'asc'}
                          onClick={() => handleSort('created_at')}
                        >
                          Created
                        </TableSortLabel>
                      </TableCell>
                      <TableCell>
                        <TableSortLabel
                          active={sort.field === 'filled_at'}
                          direction={sort.field === 'filled_at' ? sort.direction : 'asc'}
                          onClick={() => handleSort('filled_at')}
                        >
                          Filled
                        </TableSortLabel>
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {paginatedOrders.map((order, index) => (
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

              <TablePagination
                component="div"
                count={currentOrders.length}
                page={page}
                onPageChange={(_, newPage) => setPage(newPage)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => {
                  setRowsPerPage(parseInt(e.target.value, 10));
                  setPage(0);
                }}
                rowsPerPageOptions={[10, 25, 50, 100]}
              />
            </>
          )}

          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
            Real-time order status updates • Auto-refresh every {refreshInterval}s • Showing {currentOrders.length} of {(tabValue === 0 ? stockOrders : optionsOrders).length} orders
          </Typography>
        </CardContent>
      </Card>
    </LocalizationProvider>
  );
};

export default OrderHistoryEnhanced;