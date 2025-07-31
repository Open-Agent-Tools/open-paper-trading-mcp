import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  FormControl,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  IconButton,
  useTheme,
} from '@mui/material';
import {
  ShowChart as ShowChartIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAccountContext } from '../contexts/AccountContext';
import { getPortfolioSummary } from '../services/apiClient';

interface PerformanceDataPoint {
  date: string;
  value: number;
  pnl: number;
  pnlPercent: number;
}

interface PerformanceChartProps {
  height?: number;
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ height = 300 }) => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [performanceData, setPerformanceData] = useState<PerformanceDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<string>('1M');

  const fetchPerformanceData = async () => {
    if (!selectedAccount) {
      setPerformanceData([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // For now, we'll generate sample data based on current portfolio summary
      // In a real implementation, this would fetch historical performance data
      const summary = await getPortfolioSummary(selectedAccount.id);
      
      if (summary.success && summary.summary) {
        // Generate sample historical data points
        const points: PerformanceDataPoint[] = [];
        const currentValue = summary.summary.total_value || 100000;
        const currentPnL = summary.summary.total_pnl || 0;
        const daysBack = period === '1D' ? 1 : period === '1W' ? 7 : period === '1M' ? 30 : period === '3M' ? 90 : 365;
        
        for (let i = daysBack; i >= 0; i--) {
          const date = new Date();
          date.setDate(date.getDate() - i);
          
          // Simulate historical performance with some randomness but trending toward current values
          const progressRatio = (daysBack - i) / daysBack;
          const baseValue = currentValue - currentPnL;
          const historicalPnL = currentPnL * progressRatio + (Math.random() - 0.5) * currentPnL * 0.1;
          const historicalValue = baseValue + historicalPnL;
          
          points.push({
            date: date.toISOString().split('T')[0],
            value: Math.max(historicalValue, baseValue * 0.8), // Ensure reasonable bounds
            pnl: historicalPnL,
            pnlPercent: (historicalPnL / baseValue) * 100
          });
        }
        
        setPerformanceData(points);
      }
    } catch (err) {
      setError('Failed to load performance data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPerformanceData();
  }, [selectedAccount, period]);

  const formatCurrency = (value: number) => {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Box
          sx={{
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 1,
            p: 1.5,
            boxShadow: theme.shadows[3]
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
            {new Date(label).toLocaleDateString()}
          </Typography>
          <Typography variant="body2" color="primary">
            Portfolio Value: {formatCurrency(data.value)}
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ color: data.pnl >= 0 ? theme.palette.success.main : theme.palette.error.main }}
          >
            P&L: {formatCurrency(data.pnl)} ({formatPercent(data.pnlPercent)})
          </Typography>
        </Box>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card sx={{ height }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card sx={{ height }}>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <ShowChartIcon color="primary" />
              <Typography variant="h6">Portfolio Performance</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchPerformanceData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!selectedAccount) {
    return (
      <Card sx={{ height }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Typography color="text.secondary">Select an account to view performance</Typography>
        </CardContent>
      </Card>
    );
  }

  const currentData = performanceData[performanceData.length - 1];
  const isPositive = currentData && currentData.pnl >= 0;

  return (
    <Card sx={{ height }}>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <ShowChartIcon color="primary" />
            <Typography variant="h6">Portfolio Performance</Typography>
          </Box>
        }
        action={
          <Box display="flex" alignItems="center" gap={1}>
            <FormControl size="small" sx={{ minWidth: 80 }}>
              <Select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
              >
                <MenuItem value="1D">1D</MenuItem>
                <MenuItem value="1W">1W</MenuItem>
                <MenuItem value="1M">1M</MenuItem>
                <MenuItem value="3M">3M</MenuItem>
                <MenuItem value="1Y">1Y</MenuItem>
              </Select>
            </FormControl>
            <IconButton onClick={fetchPerformanceData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Box>
        }
        subheader={
          currentData && (
            <Box display="flex" gap={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Current: {formatCurrency(currentData.value)}
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ color: isPositive ? theme.palette.success.main : theme.palette.error.main }}
              >
                {formatCurrency(currentData.pnl)} ({formatPercent(currentData.pnlPercent)})
              </Typography>
            </Box>
          )
        }
      />
      <CardContent>
        {performanceData.length > 0 ? (
          <ResponsiveContainer width="100%" height={height - 120}>
            <LineChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
              <XAxis 
                dataKey="date" 
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => new Date(value).toLocaleDateString()}
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                tickFormatter={formatCurrency}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke={theme.palette.primary.main}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: theme.palette.primary.main, strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <Box display="flex" justifyContent="center" alignItems="center" height={height - 120}>
            <Typography color="text.secondary">No performance data available</Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default PerformanceChart;