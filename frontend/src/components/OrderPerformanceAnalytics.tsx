import React, { useState, useEffect, useMemo } from 'react';
import {
  Card, CardContent, CardHeader, Typography, Box, Grid, Alert, CircularProgress,
  // Tabs, Tab, 
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, LinearProgress, IconButton, FormControl, InputLabel, Select, MenuItem
} from '@mui/material';
import {
  Analytics as AnalyticsIcon,
  TrendingUp as GainIcon,
  TrendingDown as LossIcon,
  // Timeline as TimelineIcon,
  Speed as SpeedIcon,
  // Target as AccuracyIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import { getStockOrders, getOptionsOrders } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';
import type { OrderHistoryItem } from '../types';

interface PerformanceMetrics {
  totalOrders: number;
  fillRate: number;
  avgFillTime: number; // in minutes
  profitLoss: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  sharpeRatio: number;
  maxDrawdown: number;
  totalCommissions: number;
  slippage: number;
}

interface OrderStats {
  date: string;
  orders: number;
  fillRate: number;
  volume: number;
}

interface SymbolPerformance {
  symbol: string;
  orders: number;
  fillRate: number;
  profitLoss: number;
  winRate: number;
}

const OrderPerformanceAnalytics: React.FC = () => {
  // const [tabValue, setTabValue] = useState(0);
  const [stockOrders, setStockOrders] = useState<OrderHistoryItem[]>([]);
  const [optionsOrders, setOptionsOrders] = useState<OrderHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState('30d');
  
  const { selectedAccount } = useAccountContext();

  const fetchOrderData = async () => {
    if (!selectedAccount) return;

    setLoading(true);
    setError(null);

    try {
      const [stockResponse, optionsResponse] = await Promise.all([
        getStockOrders(selectedAccount.id),
        getOptionsOrders(selectedAccount.id)
      ]);

      if (stockResponse.success) {
        setStockOrders(stockResponse.orders || []);
      }

      if (optionsResponse.success) {
        setOptionsOrders(optionsResponse.orders || []);
      }
    } catch (err) {
      setError('Failed to load order analytics data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrderData();
  }, [selectedAccount]);

  // Filter orders by time range
  const filteredOrders = useMemo(() => {
    const allOrders = [...stockOrders, ...optionsOrders];
    const now = new Date();
    const cutoffDate = new Date();
    
    switch (timeRange) {
      case '7d':
        cutoffDate.setDate(now.getDate() - 7);
        break;
      case '30d':
        cutoffDate.setDate(now.getDate() - 30);
        break;
      case '90d':
        cutoffDate.setDate(now.getDate() - 90);
        break;
      case '1y':
        cutoffDate.setFullYear(now.getFullYear() - 1);
        break;
      default:
        cutoffDate.setDate(now.getDate() - 30);
    }

    return allOrders.filter(order => {
      const orderDate = order.created_at ? new Date(order.created_at) : new Date();
      return orderDate >= cutoffDate;
    });
  }, [stockOrders, optionsOrders, timeRange]);

  // Calculate performance metrics
  const metrics = useMemo((): PerformanceMetrics => {
    const totalOrders = filteredOrders.length;
    const filledOrders = filteredOrders.filter(o => o.status === 'filled');
    const fillRate = totalOrders > 0 ? (filledOrders.length / totalOrders) * 100 : 0;

    // Calculate average fill time for filled orders
    const fillTimes = filledOrders
      .filter(o => o.filled_at && o.created_at)
      .map(o => {
        const created = new Date(o.created_at!);
        const filled = new Date(o.filled_at!);
        return (filled.getTime() - created.getTime()) / (1000 * 60); // minutes
      });
    const avgFillTime = fillTimes.length > 0 ? fillTimes.reduce((a, b) => a + b, 0) / fillTimes.length : 0;

    // Calculate P&L (simplified - would need current prices in real implementation)
    const pnlOrders = filledOrders.filter(o => o.average_filled_price && o.price);
    let totalPnL = 0;
    let wins = 0;
    let totalWinAmount = 0;
    let totalLossAmount = 0;

    pnlOrders.forEach(order => {
      if (order.average_filled_price && order.price) {
        const pnl = (order.average_filled_price - order.price) * (order.filled_quantity || order.quantity);
        const adjustedPnL = order.order_type === 'sell' ? -pnl : pnl;
        
        totalPnL += adjustedPnL;
        if (adjustedPnL > 0) {
          wins++;
          totalWinAmount += adjustedPnL;
        } else if (adjustedPnL < 0) {
          totalLossAmount += Math.abs(adjustedPnL);
        }
      }
    });

    const winRate = pnlOrders.length > 0 ? (wins / pnlOrders.length) * 100 : 0;
    const avgWin = wins > 0 ? totalWinAmount / wins : 0;
    const avgLoss = (pnlOrders.length - wins) > 0 ? totalLossAmount / (pnlOrders.length - wins) : 0;

    // Simplified Sharpe ratio calculation
    const sharpeRatio = avgLoss > 0 ? avgWin / avgLoss : 0;

    return {
      totalOrders,
      fillRate,
      avgFillTime,
      profitLoss: totalPnL,
      winRate,
      avgWin,
      avgLoss,
      sharpeRatio,
      maxDrawdown: 0, // Would need historical balance data
      totalCommissions: 0, // Would need commission data
      slippage: 0 // Would need more detailed execution data
    };
  }, [filteredOrders]);

  // Order statistics by date
  const orderStats = useMemo((): OrderStats[] => {
    const statsMap = new Map<string, { orders: number; filled: number; volume: number }>();
    
    filteredOrders.forEach(order => {
      const date = (order.created_at ? new Date(order.created_at) : new Date()).toLocaleDateString();
      const current = statsMap.get(date) || { orders: 0, filled: 0, volume: 0 };
      
      current.orders++;
      if (order.status === 'filled') {
        current.filled++;
        const price = order.average_filled_price || order.price || 0;
        current.volume += price * (order.filled_quantity || order.quantity);
      }
      
      statsMap.set(date, current);
    });

    return Array.from(statsMap.entries())
      .map(([date, stats]) => ({
        date,
        orders: stats.orders,
        fillRate: stats.orders > 0 ? (stats.filled / stats.orders) * 100 : 0,
        volume: stats.volume
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .slice(-30); // Last 30 days
  }, [filteredOrders]);

  // Symbol performance
  const symbolPerformance = useMemo((): SymbolPerformance[] => {
    const symbolMap = new Map<string, { orders: OrderHistoryItem[]; filled: OrderHistoryItem[] }>();
    
    filteredOrders.forEach(order => {
      const current = symbolMap.get(order.symbol) || { orders: [], filled: [] };
      current.orders.push(order);
      if (order.status === 'filled') {
        current.filled.push(order);
      }
      symbolMap.set(order.symbol, current);
    });

    return Array.from(symbolMap.entries())
      .map(([symbol, data]) => {
        const fillRate = data.orders.length > 0 ? (data.filled.length / data.orders.length) * 100 : 0;
        
        // Calculate simple P&L for this symbol
        let symbolPnL = 0;
        let wins = 0;
        
        data.filled.forEach(order => {
          if (order.average_filled_price && order.price) {
            const pnl = (order.average_filled_price - order.price) * (order.filled_quantity || order.quantity);
            const adjustedPnL = order.order_type === 'sell' ? -pnl : pnl;
            symbolPnL += adjustedPnL;
            if (adjustedPnL > 0) wins++;
          }
        });

        const winRate = data.filled.length > 0 ? (wins / data.filled.length) * 100 : 0;

        return {
          symbol,
          orders: data.orders.length,
          fillRate,
          profitLoss: symbolPnL,
          winRate
        };
      })
      .sort((a, b) => b.orders - a.orders)
      .slice(0, 10); // Top 10 symbols
  }, [filteredOrders]);

  const statusDistribution = useMemo(() => {
    const distribution = filteredOrders.reduce((acc, order) => {
      acc[order.status] = (acc[order.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return Object.entries(distribution).map(([status, count]) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count,
      percentage: ((count / filteredOrders.length) * 100).toFixed(1)
    }));
  }, [filteredOrders]);

  const COLORS = ['#00C49F', '#FFBB28', '#FF8042', '#0088FE', '#FF6B6B'];

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading analytics...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <IconButton onClick={fetchOrderData}>
          <RefreshIcon />
        </IconButton>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      {/* Header Controls */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Order Performance Analytics</Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={timeRange}
              label="Time Range"
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <MenuItem value="7d">Last 7 days</MenuItem>
              <MenuItem value="30d">Last 30 days</MenuItem>
              <MenuItem value="90d">Last 90 days</MenuItem>
              <MenuItem value="1y">Last year</MenuItem>
            </Select>
          </FormControl>
          <IconButton onClick={fetchOrderData}>
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Key Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AnalyticsIcon color="primary" />
                <Typography variant="h4">{metrics.totalOrders}</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">Total Orders</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SpeedIcon color="success" />
                <Typography variant="h4">{metrics.fillRate.toFixed(1)}%</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">Fill Rate</Typography>
              <LinearProgress 
                variant="determinate" 
                value={metrics.fillRate} 
                sx={{ mt: 1 }}
                color="success"
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SpeedIcon color="info" />
                <Typography variant="h4">{metrics.avgFillTime.toFixed(1)}m</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">Avg Fill Time</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {metrics.profitLoss >= 0 ? <GainIcon color="success" /> : <LossIcon color="error" />}
                <Typography 
                  variant="h4" 
                  color={metrics.profitLoss >= 0 ? 'success.main' : 'error.main'}
                >
                  ${metrics.profitLoss.toFixed(2)}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">P&L</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts Section */}
      <Grid container spacing={3}>
        {/* Order Status Distribution */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Order Status Distribution" />
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={statusDistribution}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                    label={({ name, percentage }) => `${name} (${percentage}%)`}
                  >
                    {statusDistribution.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Daily Order Volume */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Daily Order Activity" />
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={orderStats.slice(-10)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="orders" fill="#8884d8" name="Orders" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Fill Rate Trend */}
        <Grid item xs={12}>
          <Card>
            <CardHeader title="Fill Rate Trend" />
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={orderStats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} />
                  <Tooltip formatter={(value, name) => [`${value}%`, name]} />
                  <Legend />
                  <Line 
                    type="monotone" 
                    dataKey="fillRate" 
                    stroke="#00C49F" 
                    strokeWidth={2}
                    name="Fill Rate (%)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Symbol Performance Table */}
        <Grid item xs={12}>
          <Card>
            <CardHeader title="Top Symbols by Order Count" />
            <CardContent>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell align="right">Orders</TableCell>
                      <TableCell align="right">Fill Rate</TableCell>
                      <TableCell align="right">Win Rate</TableCell>
                      <TableCell align="right">P&L</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {symbolPerformance.map((symbol) => (
                      <TableRow key={symbol.symbol}>
                        <TableCell>
                          <Typography variant="body2" fontWeight="bold">
                            {symbol.symbol}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">{symbol.orders}</TableCell>
                        <TableCell align="right">
                          <Chip 
                            label={`${symbol.fillRate.toFixed(1)}%`}
                            size="small"
                            color={symbol.fillRate > 80 ? 'success' : 'default'}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Chip 
                            label={`${symbol.winRate.toFixed(1)}%`}
                            size="small"
                            color={symbol.winRate > 50 ? 'success' : 'error'}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography 
                            variant="body2" 
                            color={symbol.profitLoss >= 0 ? 'success.main' : 'error.main'}
                            fontWeight="bold"
                          >
                            ${symbol.profitLoss.toFixed(2)}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default OrderPerformanceAnalytics;