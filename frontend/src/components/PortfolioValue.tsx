import React, { useEffect, useState } from 'react';
import { Paper, Typography, Box, CircularProgress, Alert, Grid, Chip } from '@mui/material';
import { TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';
import { getPortfolioSummary } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';
import { useComponentLoading } from '../contexts/LoadingContext';
import type { PortfolioSummary } from '../types';

const PortfolioValue: React.FC = () => {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const { loading, startLoading, stopLoading } = useComponentLoading('portfolio-data');
  const [error, setError] = useState<string | null>(null);
  const { selectedAccount, isInitialized } = useAccountContext();


  useEffect(() => {
    const fetchPortfolio = async () => {
      // Wait for account context to be initialized
      if (!isInitialized) {
        return;
      }

      if (!selectedAccount) {
        setPortfolio(null);
        setError(null);
        stopLoading();
        return;
      }

      try {
        startLoading();
        setError(null);
        
        const response = await getPortfolioSummary(selectedAccount.id);
        
        if (response.success && response.summary) {
          setPortfolio(response.summary);
        } else {
          setError(response.message || 'Failed to fetch portfolio data');
          setPortfolio(null);
        }
      } catch (err) {
        console.error('Portfolio fetch error:', err);
        
        // Provide more specific error messages
        let errorMessage = 'Failed to fetch portfolio data';
        if (err instanceof Error) {
          if (err.message.includes('Network error')) {
            errorMessage = 'Unable to connect to server. Please check your connection.';
          } else if (err.message.includes('timeout')) {
            errorMessage = 'Request timed out. Please try again.';
          } else if (err.message.includes('404')) {
            errorMessage = 'Portfolio endpoint not found.';
          } else if (err.message.includes('500')) {
            errorMessage = 'Server error. Please try again later.';
          } else {
            errorMessage = err.message;
          }
        }
        
        setError(errorMessage);
        setPortfolio(null);
      } finally {
        stopLoading();
      }
    };

    fetchPortfolio();
  }, [selectedAccount, isInitialized, startLoading, stopLoading]);

  const formatCurrency = (amount: number | null | undefined) => {
    if (amount == null || isNaN(amount)) {
      return '$0.00';
    }
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    });
  };

  const formatPercent = (percent: number | null | undefined) => {
    if (percent == null || isNaN(percent)) {
      return '0.00%';
    }
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  };

  const getTrendIcon = (value: number | null | undefined) => {
    if (value == null || isNaN(value)) return <TrendingFlat color="disabled" />;
    if (value > 0) return <TrendingUp color="success" />;
    if (value < 0) return <TrendingDown color="error" />;
    return <TrendingFlat color="disabled" />;
  };

  const getTrendColor = (value: number | null | undefined) => {
    if (value == null || isNaN(value)) return 'text.secondary';
    if (value > 0) return 'success.main';
    if (value < 0) return 'error.main';
    return 'text.secondary';
  };

  if (loading) {
    return (
      <Paper sx={{ p: 2, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ p: 2, height: '100%' }}>
        <Typography variant="h6" gutterBottom>
          Portfolio Value
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  if (!portfolio) {
    return (
      <Paper sx={{ p: 2, height: '100%' }}>
        <Typography variant="h6" gutterBottom>
          Portfolio Value
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography color="text.secondary">
            {!selectedAccount ? 'Please select an account to view portfolio data' : 'No portfolio data available'}
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="h6" gutterBottom>
        Portfolio Value
      </Typography>
      
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Box sx={{ textAlign: 'center', mb: 2 }}>
            <Typography variant="h4" component="div" fontWeight="bold">
              {formatCurrency(portfolio.total_value)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Total Portfolio Value
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 2 }}>
            {getTrendIcon(portfolio.daily_pnl)}
            <Typography
              variant="h6"
              sx={{ color: getTrendColor(portfolio.daily_pnl) }}
            >
              {formatCurrency(portfolio.daily_pnl)}
            </Typography>
            <Chip
              label={formatPercent(portfolio.daily_pnl_percent)}
              size="small"
              color={(portfolio.daily_pnl != null && portfolio.daily_pnl >= 0) ? 'success' : 'error'}
              variant="outlined"
            />
          </Box>
        </Grid>

        <Grid item xs={6}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Cash Balance
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {formatCurrency(portfolio.cash_balance)}
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Invested Value
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {formatCurrency(portfolio.invested_value)}
            </Typography>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default PortfolioValue;
