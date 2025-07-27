import React, { useState, useEffect, useMemo } from 'react';
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
  Chip,
  IconButton,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  ShowChart as ShowChartIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getPriceHistory } from '../services/apiClient';
import { FONTS } from '../theme';
import type { PriceHistoryData } from '../types';

interface PriceHistoryChartProps {
  symbol: string;
  onLoadingChange?: (loading: boolean) => void;
}

const PriceHistoryChart: React.FC<PriceHistoryChartProps> = ({ 
  symbol, 
  onLoadingChange 
}) => {
  const theme = useTheme();
  const [historyData, setHistoryData] = useState<PriceHistoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<string>('week');

  const periodOptions = [
    { value: 'day', label: '1D' },
    { value: 'week', label: '1W' },
    { value: 'month', label: '1M' },
    { value: '3month', label: '3M' },
    { value: 'year', label: '1Y' },
    { value: '5year', label: '5Y' },
  ];

  const fetchPriceHistory = async () => {
    if (!symbol) {
      setHistoryData(null);
      return;
    }

    setLoading(true);
    setError(null);
    onLoadingChange?.(true);

    try {
      const response = await getPriceHistory(symbol, period);
      if (response.success) {
        setHistoryData(response.history);
      } else {
        setError('Failed to load price history');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load price history');
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchPriceHistory();
  }, [symbol, period]);

  // Calculate price change and trend
  const priceStats = useMemo(() => {
    if (!historyData?.points || historyData.points.length === 0) {
      return null;
    }

    const points = historyData.points;
    const startPrice = points[0]?.close || 0;
    const endPrice = points[points.length - 1]?.close || 0;
    const change = endPrice - startPrice;
    const changePercent = startPrice > 0 ? (change / startPrice) * 100 : 0;
    const high = Math.max(...points.map(p => p.high));
    const low = Math.min(...points.map(p => p.low));

    return {
      startPrice,
      endPrice,
      change,
      changePercent,
      high,
      low,
      isPositive: change >= 0,
    };
  }, [historyData]);

  // Simple ASCII-style chart visualization
  const renderSimpleChart = () => {
    if (!historyData?.points || historyData.points.length === 0) {
      return null;
    }

    const points = historyData.points;
    const prices = points.map(p => p.close);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    if (priceRange === 0) {
      return (
        <Box sx={{ p: 2, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            No price movement in selected period
          </Typography>
        </Box>
      );
    }

    // Create sparkline-style visualization
    const chartHeight = 80;
    const chartWidth = 300;
    const pointWidth = chartWidth / prices.length;

    return (
      <Box sx={{ p: 2 }}>
        <Box
          sx={{
            width: chartWidth,
            height: chartHeight,
            position: 'relative',
            margin: '0 auto',
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 1,
            backgroundColor: theme.palette.background.default,
          }}
        >
          <svg width={chartWidth} height={chartHeight}>
            {/* Grid lines */}
            {[0.25, 0.5, 0.75].map((ratio, i) => (
              <line
                key={i}
                x1="0"
                y1={chartHeight * ratio}
                x2={chartWidth}
                y2={chartHeight * ratio}
                stroke={theme.palette.divider}
                strokeWidth="0.5"
                opacity="0.5"
              />
            ))}
            
            {/* Price line */}
            <polyline
              fill="none"
              stroke={priceStats?.isPositive ? theme.palette.success.main : theme.palette.error.main}
              strokeWidth="2"
              points={prices.map((price, i) => {
                const x = i * pointWidth + pointWidth / 2;
                const y = chartHeight - ((price - minPrice) / priceRange) * chartHeight;
                return `${x},${y}`;
              }).join(' ')}
            />
            
            {/* Price points */}
            {prices.map((price, i) => {
              const x = i * pointWidth + pointWidth / 2;
              const y = chartHeight - ((price - minPrice) / priceRange) * chartHeight;
              return (
                <circle
                  key={i}
                  cx={x}
                  cy={y}
                  r="1.5"
                  fill={priceStats?.isPositive ? theme.palette.success.main : theme.palette.error.main}
                />
              );
            })}
          </svg>
        </Box>
        
        {/* Price labels */}
        <Box display="flex" justifyContent="space-between" mt={1}>
          <Typography variant="caption" color="text.secondary">
            ${minPrice.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            ${maxPrice.toFixed(2)}
          </Typography>
        </Box>
      </Box>
    );
  };

  if (loading && !historyData) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading price history...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <ShowChartIcon color="primary" />
              <Typography variant="h6">
                {symbol} Price History
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchPriceHistory} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="warning">
            {error}. Historical price data may not be available for this symbol.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!historyData) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Select a stock to view price history
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <ShowChartIcon color="primary" />
            <Typography variant="h6">
              {symbol} Price History
            </Typography>
            {priceStats && (
              <Chip
                label={priceStats.isPositive ? 'UP' : 'DOWN'}
                size="small"
                color={priceStats.isPositive ? 'success' : 'error'}
                sx={{ ml: 1 }}
              />
            )}
          </Box>
        }
        action={
          <Box display="flex" alignItems="center" gap={1}>
            <FormControl size="small" sx={{ minWidth: 80 }}>
              <Select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                displayEmpty
              >
                {periodOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <IconButton onClick={fetchPriceHistory} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Box>
        }
      />
      
      <CardContent>
        {priceStats && (
          <Box mb={2}>
            <Box display="flex" alignItems="center" gap={2} mb={1}>
              <Typography variant="h6" sx={{ fontFamily: FONTS.monospace }}>
                ${priceStats.endPrice.toFixed(2)}
              </Typography>
              <Box display="flex" alignItems="center" gap={1}>
                {priceStats.isPositive ? <TrendingUpIcon color="success" /> : <TrendingUpIcon color="error" sx={{ transform: 'rotate(180deg)' }} />}
                <Typography
                  variant="body1"
                  sx={{
                    color: priceStats.isPositive ? theme.palette.success.main : theme.palette.error.main,
                    fontFamily: FONTS.monospace,
                  }}
                >
                  {priceStats.change >= 0 ? '+' : ''}{priceStats.change.toFixed(2)} ({priceStats.changePercent.toFixed(2)}%)
                </Typography>
              </Box>
            </Box>
            
            <Box display="flex" gap={3}>
              <Typography variant="body2" color="text.secondary">
                High: <Box component="span" sx={{ fontFamily: FONTS.monospace }}>${priceStats.high.toFixed(2)}</Box>
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Low: <Box component="span" sx={{ fontFamily: FONTS.monospace }}>${priceStats.low.toFixed(2)}</Box>
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Points: {historyData.points.length}
              </Typography>
            </Box>
          </Box>
        )}
        
        {renderSimpleChart()}
        
        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
          Period: {periodOptions.find(p => p.value === period)?.label} • Data points: {historyData.points.length}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default PriceHistoryChart;