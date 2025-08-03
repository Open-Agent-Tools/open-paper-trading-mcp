import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Grid,
  Alert,
  CircularProgress,
  Chip,
  IconButton,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Refresh as RefreshIcon,
  ShowChart as ShowChartIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getStockPrice } from '../services/apiClient';
import { useComponentLoading } from '../contexts/LoadingContext';
import type { StockPriceData } from '../types';

interface StockQuoteProps {
  symbol: string;
  onLoadingChange?: (loading: boolean) => void;
  autoRefresh?: boolean;
  refreshInterval?: number; // in seconds
}

const StockQuote: React.FC<StockQuoteProps> = ({ 
  symbol, 
  onLoadingChange,
  autoRefresh = false,
  refreshInterval = 30
}) => {
  const theme = useTheme();
  const { loading, startLoading, stopLoading } = useComponentLoading('stock-quote');
  const [priceData, setPriceData] = useState<StockPriceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchStockPrice = async () => {
    if (!symbol) {
      setPriceData(null);
      return;
    }

    startLoading();
    setError(null);
    onLoadingChange?.(true);

    try {
      const response = await getStockPrice(symbol);
      if (response.success) {
        if (response.price_data.error) {
          // Handle API error response
          setError(response.price_data.error);
          setPriceData(null);
        } else {
          setPriceData(response.price_data);
          setLastUpdated(new Date());
        }
      } else {
        setError('Failed to load stock price');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stock price');
    } finally {
      stopLoading();
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchStockPrice();
  }, [symbol]);

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh || !symbol) return;

    const interval = setInterval(fetchStockPrice, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, symbol]);

  const formatPrice = (price: number): string => {
    return `$${price.toFixed(2)}`;
  };

  const formatChange = (change: number, changePercent: number): string => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)} (${sign}${changePercent.toFixed(2)}%)`;
  };

  const formatVolume = (volume: number): string => {
    if (volume >= 1e6) return `${(volume / 1e6).toFixed(1)}M`;
    if (volume >= 1e3) return `${(volume / 1e3).toFixed(1)}K`;
    return volume.toLocaleString();
  };

  if (loading && !priceData) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading price data...
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
                {symbol} Quote
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchStockPrice} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="warning">
            {error}. Price data may not be available for this symbol or the market data service may be temporarily unavailable.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!priceData) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Select a stock to view price information
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const isPositive = (priceData.change || 0) >= 0;
  const changeColor = isPositive ? theme.palette.success.main : theme.palette.error.main;
  const TrendIcon = isPositive ? TrendingUpIcon : TrendingDownIcon;

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <ShowChartIcon color="primary" />
            <Typography variant="h6">
              {symbol} Quote
            </Typography>
            {autoRefresh && (
              <Chip
                label="Live"
                size="small"
                color="success"
                sx={{ ml: 1 }}
              />
            )}
          </Box>
        }
        action={
          <IconButton onClick={fetchStockPrice} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
        subheader={
          lastUpdated && (
            <Typography variant="caption" color="text.secondary">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )
        }
      />
      
      <CardContent>
        <Grid container spacing={3}>
          {/* Current Price */}
          <Grid item xs={12} md={6}>
            <Box textAlign="center">
              <Typography variant="h3" sx={{ fontFamily: 'Roboto Mono, monospace', mb: 1 }}>
                {formatPrice(priceData.price || 0)}
              </Typography>
              
              {priceData.change !== undefined && priceData.change_percent !== undefined && (
                <Box display="flex" alignItems="center" justifyContent="center" gap={1}>
                  <TrendIcon sx={{ color: changeColor }} />
                  <Typography
                    variant="h6"
                    sx={{
                      color: changeColor,
                      fontFamily: 'Roboto Mono, monospace',
                    }}
                  >
                    {formatChange(priceData.change, priceData.change_percent)}
                  </Typography>
                </Box>
              )}
            </Box>
          </Grid>

          {/* Market Data */}
          <Grid item xs={12} md={6}>
            <Grid container spacing={2}>
              {priceData.open !== undefined && (
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Open
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatPrice(priceData.open)}
                  </Typography>
                </Grid>
              )}
              
              {priceData.high !== undefined && (
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    High
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatPrice(priceData.high)}
                  </Typography>
                </Grid>
              )}
              
              {priceData.low !== undefined && (
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Low
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatPrice(priceData.low)}
                  </Typography>
                </Grid>
              )}
              
              {priceData.volume !== undefined && (
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Volume
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatVolume(priceData.volume)}
                  </Typography>
                </Grid>
              )}
              
              {priceData.previous_close !== undefined && (
                <Grid item xs={12}>
                  <Typography variant="body2" color="text.secondary">
                    Previous Close
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatPrice(priceData.previous_close)}
                  </Typography>
                </Grid>
              )}
            </Grid>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default StockQuote;