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
  IconButton,
  Chip,
  Divider,
  useTheme,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { useAccountContext } from '../contexts/AccountContext';
import { getPortfolioSummary, getPositions } from '../services/apiClient';
import type { Position } from '../types';

interface RiskMetric {
  label: string;
  value: string | number;
  status: 'good' | 'moderate' | 'high';
  description: string;
}

const RiskMetrics: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [metrics, setMetrics] = useState<RiskMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculateRiskMetrics = (positions: Position[], portfolioValue: number): RiskMetric[] => {
    if (!positions.length) return [];

    // Portfolio concentration risk
    const topPositionValue = Math.max(...positions.map(p => p.market_value || 0));
    const concentrationRatio = (topPositionValue / portfolioValue) * 100;
    
    // Asset diversification
    const assetTypes = new Set(positions.map(p => p.asset_type || 'stock'));
    const diversificationScore = assetTypes.size;
    
    // Options exposure
    const optionsPositions = positions.filter(p => p.option_type);
    const optionsExposure = (optionsPositions.length / positions.length) * 100;
    
    // Unrealized P&L variance (as a proxy for volatility)
    const pnlValues = positions.map(p => p.unrealized_pnl || 0).filter(pnl => pnl !== 0);
    const avgPnL = pnlValues.length > 0 ? pnlValues.reduce((a, b) => a + b, 0) / pnlValues.length : 0;
    const variance = pnlValues.length > 0 ? 
      pnlValues.reduce((sum, pnl) => sum + Math.pow(pnl - avgPnL, 2), 0) / pnlValues.length : 0;
    const volatilityScore = Math.sqrt(variance) / portfolioValue * 100;
    
    // Simulated Sharpe ratio (would need historical returns in real implementation)
    const totalReturn = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const returnPercent = (totalReturn / (portfolioValue - totalReturn)) * 100;
    const estimatedSharpe = returnPercent > 0 ? Math.min(returnPercent / Math.max(volatilityScore, 1), 3) : 0;
    
    // Maximum drawdown estimation based on current positions
    const worstPosition = Math.min(...positions.map(p => p.unrealized_pnl_percent || 0));
    const maxDrawdown = Math.abs(worstPosition);

    return [
      {
        label: 'Portfolio Concentration',
        value: `${concentrationRatio.toFixed(1)}%`,
        status: concentrationRatio > 30 ? 'high' : concentrationRatio > 15 ? 'moderate' : 'good',
        description: 'Percentage of portfolio in largest position'
      },
      {
        label: 'Asset Diversification',
        value: diversificationScore,
        status: diversificationScore < 3 ? 'high' : diversificationScore < 5 ? 'moderate' : 'good',
        description: 'Number of different asset types held'
      },
      {
        label: 'Options Exposure',
        value: `${optionsExposure.toFixed(1)}%`,
        status: optionsExposure > 50 ? 'high' : optionsExposure > 25 ? 'moderate' : 'good',
        description: 'Percentage of positions that are options'
      },
      {
        label: 'Portfolio Volatility',
        value: `${volatilityScore.toFixed(1)}%`,
        status: volatilityScore > 20 ? 'high' : volatilityScore > 10 ? 'moderate' : 'good',
        description: 'Estimated portfolio volatility'
      },
      {
        label: 'Estimated Sharpe Ratio',
        value: estimatedSharpe.toFixed(2),
        status: estimatedSharpe < 0.5 ? 'high' : estimatedSharpe < 1.0 ? 'moderate' : 'good',
        description: 'Risk-adjusted return measure'
      },
      {
        label: 'Max Position Drawdown',
        value: `${maxDrawdown.toFixed(1)}%`,
        status: maxDrawdown > 30 ? 'high' : maxDrawdown > 15 ? 'moderate' : 'good',
        description: 'Largest unrealized loss in any position'
      }
    ];
  };

  const fetchRiskMetrics = async () => {
    if (!selectedAccount) {
      setMetrics([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [summaryResponse, positionsResponse] = await Promise.all([
        getPortfolioSummary(selectedAccount.id),
        getPositions(selectedAccount.id)
      ]);

      if (summaryResponse.success && positionsResponse.success) {
        const portfolioValue = summaryResponse.summary?.total_value || 0;
        const positions = positionsResponse.positions || [];
        
        const calculatedMetrics = calculateRiskMetrics(positions, portfolioValue);
        setMetrics(calculatedMetrics);
      } else {
        setError('Failed to load portfolio data for risk analysis');
      }
    } catch (err) {
      setError('Failed to calculate risk metrics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRiskMetrics();
  }, [selectedAccount]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good': return theme.palette.success.main;
      case 'moderate': return theme.palette.warning.main;
      case 'high': return theme.palette.error.main;
      default: return theme.palette.text.secondary;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good': return <TrendingUpIcon fontSize="small" />;
      case 'moderate': return <SecurityIcon fontSize="small" />;
      case 'high': return <TrendingDownIcon fontSize="small" />;
      default: return null;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
          <CircularProgress />
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
              <SecurityIcon color="primary" />
              <Typography variant="h6">Risk Metrics</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchRiskMetrics} disabled={loading}>
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
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
          <Typography color="text.secondary">Select an account to view risk metrics</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <SecurityIcon color="primary" />
            <Typography variant="h6">Risk Metrics</Typography>
          </Box>
        }
        action={
          <IconButton onClick={fetchRiskMetrics} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
        subheader={
          <Typography variant="body2" color="text.secondary">
            Portfolio risk analysis and diversification metrics
          </Typography>
        }
      />
      <CardContent>
        {metrics.length > 0 ? (
          <Grid container spacing={2}>
            {metrics.map((metric, index) => (
              <Grid item xs={12} sm={6} key={metric.label}>
                <Box
                  sx={{
                    p: 2,
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 1,
                    backgroundColor: theme.palette.background.default,
                  }}
                >
                  <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                    <Typography variant="subtitle2" color="text.secondary">
                      {metric.label}
                    </Typography>
                    <Chip
                      icon={getStatusIcon(metric.status) || undefined}
                      label={metric.status.toUpperCase()}
                      size="small"
                      sx={{
                        backgroundColor: getStatusColor(metric.status),
                        color: 'white',
                        '& .MuiChip-icon': { color: 'white' }
                      }}
                    />
                  </Box>
                  <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace', mb: 1 }}>
                    {metric.value}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {metric.description}
                  </Typography>
                </Box>
                {index < metrics.length - 1 && index % 2 === 1 && (
                  <Grid item xs={12} key={`divider-${index}`}>
                    <Divider sx={{ my: 1 }} />
                  </Grid>
                )}
              </Grid>
            ))}
          </Grid>
        ) : (
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
            <Typography color="text.secondary">No positions available for risk analysis</Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default RiskMetrics;