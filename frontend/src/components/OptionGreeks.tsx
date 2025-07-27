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
  Grid,
  Chip,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Functions as GreeksIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getOptionGreeks } from '../services/apiClient';
import { FONTS } from '../theme';
import type { OptionGreeks } from '../types';

interface OptionGreeksProps {
  optionSymbol: string;
  underlyingPrice?: number;
  onLoadingChange?: (loading: boolean) => void;
}

interface GreekCardProps {
  name: string;
  value: number;
  description: string;
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning';
  showProgress?: boolean;
  progressMax?: number;
}

const GreekCard: React.FC<GreekCardProps> = ({ 
  name, 
  value, 
  description, 
  color = 'primary',
  showProgress = false,
  progressMax = 1
}) => {
  const theme = useTheme();
  
  const formatValue = (val: number): string => {
    if (Math.abs(val) < 0.001) {
      return val.toExponential(2);
    }
    return val.toFixed(4);
  };

  const getProgressValue = (): number => {
    if (!showProgress) return 0;
    return Math.abs(value) / progressMax * 100;
  };

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="h6" color={`${color}.main`}>
            {name}
          </Typography>
          <Tooltip title={description}>
            <InfoIcon fontSize="small" color="action" />
          </Tooltip>
        </Box>
        
        <Typography 
          variant="h4" 
          sx={{ 
            fontFamily: FONTS.monospace,
            color: value >= 0 ? theme.palette.success.main : theme.palette.error.main,
            mb: 1
          }}
        >
          {value >= 0 ? '+' : ''}{formatValue(value)}
        </Typography>

        {showProgress && (
          <Box sx={{ mt: 1 }}>
            <LinearProgress
              variant="determinate"
              value={getProgressValue()}
              color={color}
              sx={{ height: 4, borderRadius: 2 }}
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              {Math.abs(value) < progressMax ? 'Low' : 'High'} {name.toLowerCase()}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

const OptionGreeksComponent: React.FC<OptionGreeksProps> = ({ 
  optionSymbol, 
  underlyingPrice,
  onLoadingChange 
}) => {
  const [greeksData, setGreeksData] = useState<OptionGreeks | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOptionGreeks = async () => {
    if (!optionSymbol) {
      setGreeksData(null);
      return;
    }

    setLoading(true);
    setError(null);
    onLoadingChange?.(true);

    try {
      const response = await getOptionGreeks(optionSymbol, underlyingPrice);
      if (response.success) {
        setGreeksData(response.greeks);
      } else {
        setError('Failed to load option Greeks');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load option Greeks');
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchOptionGreeks();
  }, [optionSymbol, underlyingPrice]);

  const getOptionType = (): string => {
    // Extract option type from option symbol (simplified)
    if (optionSymbol.includes('C')) return 'Call';
    if (optionSymbol.includes('P')) return 'Put';
    return 'Option';
  };

  if (loading && !greeksData) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading option Greeks...
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
              <GreeksIcon color="primary" />
              <Typography variant="h6">
                Option Greeks
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchOptionGreeks} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="warning">
            {error}. Greeks data may not be available for this option.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!greeksData) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Select an option to view Greeks
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
            <GreeksIcon color="primary" />
            <Typography variant="h6">
              Option Greeks
            </Typography>
            <Chip
              label={getOptionType()}
              size="small"
              color="primary"
              variant="outlined"
            />
          </Box>
        }
        subheader={
          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: FONTS.monospace }}>
            {optionSymbol}
          </Typography>
        }
        action={
          <IconButton onClick={fetchOptionGreeks} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
      />
      
      <CardContent>
        <Grid container spacing={2}>
          {/* First Order Greeks */}
          <Grid item xs={12} sm={6} md={3}>
            <GreekCard
              name="Delta"
              value={greeksData.delta}
              description="Price sensitivity to underlying price changes. Shows how much the option price changes for $1 move in the underlying."
              color="primary"
              showProgress
              progressMax={1}
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <GreekCard
              name="Gamma"
              value={greeksData.gamma}
              description="Rate of change of delta. Shows how much delta changes for $1 move in the underlying."
              color="secondary"
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <GreekCard
              name="Theta"
              value={greeksData.theta}
              description="Time decay. Shows how much the option price decreases per day as time passes."
              color="error"
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <GreekCard
              name="Vega"
              value={greeksData.vega}
              description="Volatility sensitivity. Shows how much the option price changes for 1% change in implied volatility."
              color="warning"
            />
          </Grid>

          {/* Additional Greeks if available */}
          {greeksData.rho !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <GreekCard
                name="Rho"
                value={greeksData.rho}
                description="Interest rate sensitivity. Shows how much the option price changes for 1% change in interest rates."
                color="success"
              />
            </Grid>
          )}

          {greeksData.iv !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <Card variant="outlined">
                <CardContent sx={{ p: 2 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h6" color="info.main">
                      Implied Vol
                    </Typography>
                    <Tooltip title="Implied Volatility - the market's expectation of future price movement">
                      <InfoIcon fontSize="small" color="action" />
                    </Tooltip>
                  </Box>
                  
                  <Typography 
                    variant="h4" 
                    sx={{ 
                      fontFamily: FONTS.monospace,
                      color: 'info.main',
                      mb: 1
                    }}
                  >
                    {(greeksData.iv * 100).toFixed(1)}%
                  </Typography>

                  <LinearProgress
                    variant="determinate"
                    value={Math.min(greeksData.iv * 100, 100)}
                    color="info"
                    sx={{ height: 4, borderRadius: 2 }}
                  />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    {greeksData.iv < 0.2 ? 'Low' : greeksData.iv > 0.5 ? 'High' : 'Moderate'} volatility
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>

        <Box mt={3} p={2} sx={{ backgroundColor: 'background.default', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Greeks Interpretation:</strong> Delta shows directional exposure, Gamma measures delta stability, 
            Theta indicates daily decay, and Vega shows volatility risk. Values update with real market data.
          </Typography>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
          Live data from Robinhood • Greeks calculated using Black-Scholes model
        </Typography>
      </CardContent>
    </Card>
  );
};

export default OptionGreeksComponent;