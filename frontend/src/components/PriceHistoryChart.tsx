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
import { getPriceHistory } from '../services/apiClient';
import { useComponentLoading } from '../contexts/LoadingContext';
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
  const { loading, startLoading, stopLoading } = useComponentLoading('price-history');
  const [historyData, setHistoryData] = useState<PriceHistoryData | null>(null);
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

    startLoading();
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
      stopLoading();
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchPriceHistory();
  }, [symbol, period]);

  // Calculate price change and trend
  const priceStats = useMemo(() => {
    // Handle both possible response structures
    const points = historyData?.points || historyData?.data_points;
    if (!points || points.length === 0) {
      return null;
    }
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

  // Enhanced chart visualization
  const renderChart = () => {
    // Handle both possible response structures
    const points = historyData?.points || historyData?.data_points;
    if (!points || points.length === 0) {
      return null;
    }

    const prices = points.map(p => p.close);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    if (priceRange === 0) {
      return (
        <Box sx={{ minHeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            No price movement in selected period
          </Typography>
        </Box>
      );
    }

    // Chart dimensions - fill container width, minimum 600px height
    const chartHeight = 600;
    const chartPadding = { top: 40, right: 80, bottom: 60, left: 80 };
    const plotHeight = chartHeight - chartPadding.top - chartPadding.bottom;
    
    // Calculate price axis ticks
    const priceStep = priceRange / 8; // 8 price levels
    const priceTicks = Array.from({ length: 9 }, (_, i) => minPrice + (i * priceStep));
    
    // Calculate time axis ticks (show every few points)
    const timeStep = Math.max(1, Math.floor(points.length / 8)); // ~8 time labels
    const timeTicks = points.filter((_, i) => i % timeStep === 0 || i === points.length - 1);

    return (
      <Box sx={{ width: '100%', minHeight: chartHeight, position: 'relative' }}>
        <svg 
          width="100%" 
          height={chartHeight}
          viewBox={`0 0 800 ${chartHeight}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: chartHeight }}
        >
          <defs>
            <linearGradient id="priceGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={priceStats?.isPositive ? '#1f7a4f' : '#dc3545'} stopOpacity="0.2" />
              <stop offset="100%" stopColor={priceStats?.isPositive ? '#1f7a4f' : '#dc3545'} stopOpacity="0.03" />
            </linearGradient>
          </defs>
          
          {/* Chart background */}
          <rect 
            x={chartPadding.left} 
            y={chartPadding.top} 
            width={800 - chartPadding.left - chartPadding.right} 
            height={plotHeight}
            fill="#ffffff"
            stroke="#dee2e6"
            strokeWidth="1"
          />
          
          {/* Horizontal grid lines and price labels */}
          {priceTicks.map((price, i) => {
            const y = chartPadding.top + plotHeight - ((price - minPrice) / priceRange) * plotHeight;
            return (
              <g key={i}>
                <line
                  x1={chartPadding.left}
                  y1={y}
                  x2={800 - chartPadding.right}
                  y2={y}
                  stroke="#e9ecef"
                  strokeWidth="0.5"
                  opacity="0.8"
                />
                <text
                  x={chartPadding.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="12"
                  fontFamily="'Roboto Mono', monospace"
                  fill="#6c757d"
                >
                  ${price.toFixed(2)}
                </text>
              </g>
            );
          })}
          
          {/* Vertical grid lines and time labels */}
          {timeTicks.map((point, i) => {
            const originalIndex = points.indexOf(point);
            const x = chartPadding.left + (originalIndex / (points.length - 1)) * (800 - chartPadding.left - chartPadding.right);
            const date = new Date(point.date || point.timestamp || '');
            
            // Show time for 1-day period, date for others
            const timeLabel = period === 'day' 
              ? date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true })
              : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
            
            return (
              <g key={i}>
                <line
                  x1={x}
                  y1={chartPadding.top}
                  x2={x}
                  y2={chartPadding.top + plotHeight}
                  stroke="#e9ecef"
                  strokeWidth="0.5"
                  opacity="0.8"
                />
                <text
                  x={x}
                  y={chartHeight - chartPadding.bottom + 20}
                  textAnchor="middle"
                  fontSize="12"
                  fontFamily="'Roboto', sans-serif"
                  fill="#6c757d"
                >
                  {timeLabel}
                </text>
              </g>
            );
          })}
          
          {/* Price area fill */}
          <path
            d={`M ${chartPadding.left} ${chartPadding.top + plotHeight} ${prices.map((price, i) => {
              const x = chartPadding.left + (i / (prices.length - 1)) * (800 - chartPadding.left - chartPadding.right);
              const y = chartPadding.top + plotHeight - ((price - minPrice) / priceRange) * plotHeight;
              return `L ${x} ${y}`;
            }).join(' ')} L ${chartPadding.left + (800 - chartPadding.left - chartPadding.right)} ${chartPadding.top + plotHeight} Z`}
            fill="url(#priceGradient)"
          />
          
          {/* Price line */}
          <polyline
            fill="none"
            stroke={priceStats?.isPositive ? '#1f7a4f' : '#dc3545'}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={prices.map((price, i) => {
              const x = chartPadding.left + (i / (prices.length - 1)) * (800 - chartPadding.left - chartPadding.right);
              const y = chartPadding.top + plotHeight - ((price - minPrice) / priceRange) * plotHeight;
              return `${x},${y}`;
            }).join(' ')}
          />
          
          {/* Y-axis label */}
          <text
            x={25}
            y={chartHeight / 2}
            textAnchor="middle"
            fontSize="13"
            fontFamily="'Roboto', sans-serif"
            fontWeight="500"
            fill="#495057"
            transform={`rotate(-90 25 ${chartHeight / 2})`}
          >
            Price ($)
          </text>
          
          {/* X-axis label */}
          <text
            x={400}
            y={chartHeight - 10}
            textAnchor="middle"
            fontSize="13"
            fontFamily="'Roboto', sans-serif"
            fontWeight="500"
            fill="#495057"
          >
            Time
          </text>
        </svg>
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
                sx={{ 
                  ml: 1,
                  backgroundColor: priceStats.isPositive ? '#d4edda' : '#f8d7da',
                  color: priceStats.isPositive ? '#1f7a4f' : '#dc3545',
                  fontWeight: 500,
                  fontSize: '0.75rem'
                }}
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
                {priceStats.isPositive ? 
                  <TrendingUpIcon sx={{ color: '#1f7a4f' }} /> : 
                  <TrendingUpIcon sx={{ color: '#dc3545', transform: 'rotate(180deg)' }} />
                }
                <Typography
                  variant="body1"
                  sx={{
                    color: priceStats.isPositive ? '#1f7a4f' : '#dc3545',
                    fontFamily: FONTS.monospace,
                    fontWeight: 500,
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
            </Box>
          </Box>
        )}
        
        {renderChart()}
      </CardContent>
    </Card>
  );
};

export default PriceHistoryChart;