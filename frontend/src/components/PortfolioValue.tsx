import React, { useEffect, useState } from 'react';
import { Paper, Typography, Box, CircularProgress, Alert, Grid, Chip } from '@mui/material';
import { TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';
import { getPortfolioSummary } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';

interface PortfolioSummary {
  total_market_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_percent: number;
  total_positions: number;
}

const PortfolioValue: React.FC = () => {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { selectedAccount } = useAccountContext();

  useEffect(() => {
    const fetchPortfolio = async () => {
      if (!selectedAccount) {
        setPortfolio(null);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await getPortfolioSummary(selectedAccount.id);
        setPortfolio(data.summary || null);
      } catch (err) {
        setError('Failed to fetch portfolio data.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchPortfolio();
  }, [selectedAccount]);

  const formatCurrency = (amount: number) => {
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    });
  };

  const formatPercent = (percent: number) => {
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  };

  const getTrendIcon = (value: number) => {
    if (value > 0) return <TrendingUp color="success" />;
    if (value < 0) return <TrendingDown color="error" />;
    return <TrendingFlat color="disabled" />;
  };

  const getTrendColor = (value: number) => {
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
          <Typography color="text.secondary">No portfolio data available</Typography>
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
              {formatCurrency(portfolio.total_market_value)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Total Market Value
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 2 }}>
            {getTrendIcon(portfolio.total_unrealized_pnl)}
            <Typography
              variant="h6"
              sx={{ color: getTrendColor(portfolio.total_unrealized_pnl) }}
            >
              {formatCurrency(portfolio.total_unrealized_pnl)}
            </Typography>
            <Chip
              label={formatPercent(portfolio.total_unrealized_pnl_percent)}
              size="small"
              color={portfolio.total_unrealized_pnl >= 0 ? 'success' : 'error'}
              variant="outlined"
            />
          </Box>
        </Grid>

        <Grid item xs={6}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Cost Basis
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {formatCurrency(portfolio.total_cost_basis)}
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Positions
            </Typography>
            <Typography variant="body1" fontWeight="medium">
              {portfolio.total_positions}
            </Typography>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default PortfolioValue;
