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
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  // Chip,
  useTheme,
} from '@mui/material';
import {
  Analytics as AnalyticsIcon,
  Refresh as RefreshIcon,
  TrendingUp as CallIcon,
  TrendingDown as PutIcon,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { getOptionGreeks } from '../services/apiClient';
import type { OptionGreeks } from '../types';

interface PayoffPoint {
  price: number;
  profit: number;
  delta: number;
}

interface OptionsAnalyticsProps {
  optionSymbol?: string;
  strike?: number;
  optionType?: 'call' | 'put';
  expiration?: string;
  premium?: number;
}

const OptionsAnalytics: React.FC<OptionsAnalyticsProps> = ({
  optionSymbol,
  strike = 100,
  optionType = 'call',
  // expiration,
  premium = 5
}) => {
  const theme = useTheme();
  const [greeks, setGreeks] = useState<OptionGreeks | null>(null);
  const [payoffData, setPayoffData] = useState<PayoffPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number>(strike);
  const [analysisStrike, setAnalysisStrike] = useState<number>(strike);
  const [analysisType, setAnalysisType] = useState<'call' | 'put'>(optionType);
  const [analysisPremium, setAnalysisPremium] = useState<number>(premium);

  const calculatePayoffDiagram = (
    strikePrice: number,
    type: 'call' | 'put',
    optionPremium: number,
    _underlyingPrice: number
  ): PayoffPoint[] => {
    const points: PayoffPoint[] = [];
    const priceRange = strikePrice * 0.4; // ±40% of strike
    const minPrice = strikePrice - priceRange;
    const maxPrice = strikePrice + priceRange;
    const stepSize = (maxPrice - minPrice) / 100;

    for (let price = minPrice; price <= maxPrice; price += stepSize) {
      let intrinsicValue = 0;
      let delta = 0;

      if (type === 'call') {
        intrinsicValue = Math.max(0, price - strikePrice);
        delta = price > strikePrice ? 1 : 0; // Simplified delta at expiration
      } else {
        intrinsicValue = Math.max(0, strikePrice - price);
        delta = price < strikePrice ? -1 : 0; // Simplified delta at expiration
      }

      const profit = intrinsicValue - optionPremium;

      points.push({
        price: Math.round(price * 100) / 100,
        profit: Math.round(profit * 100) / 100,
        delta
      });
    }

    return points;
  };

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);

    try {
      // Calculate payoff diagram
      const payoff = calculatePayoffDiagram(analysisStrike, analysisType, analysisPremium, currentPrice);
      setPayoffData(payoff);

      // Fetch Greeks if option symbol is provided
      if (optionSymbol) {
        try {
          const greeksResponse = await getOptionGreeks(optionSymbol, currentPrice);
          if (greeksResponse.success) {
            setGreeks(greeksResponse.greeks);
          }
        } catch (err) {
          // Greeks are optional, continue without them
          console.warn('Could not fetch Greeks:', err);
        }
      }
    } catch (err) {
      setError('Failed to calculate options analytics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [analysisStrike, analysisType, analysisPremium, currentPrice, optionSymbol]);

  useEffect(() => {
    setAnalysisStrike(strike);
    setAnalysisType(optionType);
    setAnalysisPremium(premium);
  }, [strike, optionType, premium]);

  const formatCurrency = (value: number) => {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    });
  };

  const formatGreek = (value: number | undefined, decimals: number = 4) => {
    if (value === undefined || value === null) return 'N/A';
    return value.toFixed(decimals);
  };

  const breakEvenPrice = analysisType === 'call' 
    ? analysisStrike + analysisPremium 
    : analysisStrike - analysisPremium;

  const maxProfit = analysisType === 'call' ? 'Unlimited' : formatCurrency(analysisStrike - analysisPremium);
  const maxLoss = formatCurrency(analysisPremium);

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
            Stock Price: {formatCurrency(label)}
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ color: data.profit >= 0 ? theme.palette.success.main : theme.palette.error.main }}
          >
            Profit/Loss: {formatCurrency(data.profit)}
          </Typography>
        </Box>
      );
    }
    return null;
  };

  if (loading && !payoffData.length) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
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
              <AnalyticsIcon color="primary" />
              <Typography variant="h6">Options Analytics</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchAnalytics} disabled={loading}>
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

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <AnalyticsIcon color="primary" />
            <Typography variant="h6">Options Analytics</Typography>
            {analysisType === 'call' ? (
              <CallIcon color="success" />
            ) : (
              <PutIcon color="error" />
            )}
          </Box>
        }
        action={
          <IconButton onClick={fetchAnalytics} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
        subheader={
          <Typography variant="body2" color="text.secondary">
            Profit/Loss analysis and option Greeks
          </Typography>
        }
      />
      <CardContent>
        <Grid container spacing={3}>
          {/* Controls */}
          <Grid item xs={12}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <TextField
                  fullWidth
                  size="small"
                  label="Strike Price"
                  type="number"
                  value={analysisStrike}
                  onChange={(e) => setAnalysisStrike(Number(e.target.value))}
                  InputProps={{ inputProps: { step: 0.5, min: 0 } }}
                />
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Option Type</InputLabel>
                  <Select
                    value={analysisType}
                    label="Option Type"
                    onChange={(e) => setAnalysisType(e.target.value as 'call' | 'put')}
                  >
                    <MenuItem value="call">Call</MenuItem>
                    <MenuItem value="put">Put</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <TextField
                  fullWidth
                  size="small"
                  label="Premium Paid"
                  type="number"
                  value={analysisPremium}
                  onChange={(e) => setAnalysisPremium(Number(e.target.value))}
                  InputProps={{ inputProps: { step: 0.01, min: 0 } }}
                />
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <TextField
                  fullWidth
                  size="small"
                  label="Current Stock Price"
                  type="number"
                  value={currentPrice}
                  onChange={(e) => setCurrentPrice(Number(e.target.value))}
                  InputProps={{ inputProps: { step: 0.01, min: 0 } }}
                />
              </Grid>
            </Grid>
          </Grid>

          {/* Key Metrics */}
          <Grid item xs={12}>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="text.secondary">
                    Break-even
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatCurrency(breakEvenPrice)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="text.secondary">
                    Max Profit
                  </Typography>
                  <Typography variant="h6" color="success.main" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {maxProfit}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="text.secondary">
                    Max Loss
                  </Typography>
                  <Typography variant="h6" color="error.main" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {maxLoss}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="text.secondary">
                    Current P&L
                  </Typography>
                  <Typography 
                    variant="h6" 
                    sx={{ 
                      fontFamily: 'Roboto Mono, monospace',
                      color: (payoffData.find(p => Math.abs(p.price - currentPrice) < 0.5)?.profit ?? 0) >= 0 
                        ? theme.palette.success.main 
                        : theme.palette.error.main
                    }}
                  >
                    {formatCurrency(
                      payoffData.find(p => Math.abs(p.price - currentPrice) < 0.5)?.profit || 0
                    )}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Grid>

          {/* Payoff Diagram */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              Profit/Loss Diagram (at Expiration)
            </Typography>
            {payoffData.length > 0 ? (
              <Box sx={{ width: '100%', height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={payoffData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                    <XAxis 
                      dataKey="price" 
                      tick={{ fontSize: 12 }}
                      tickFormatter={(value) => `$${value}`}
                    />
                    <YAxis 
                      tick={{ fontSize: 12 }}
                      tickFormatter={(value) => `$${value}`}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={0} stroke={theme.palette.text.secondary} strokeDasharray="5 5" />
                    <ReferenceLine x={currentPrice} stroke={theme.palette.primary.main} strokeDasharray="3 3" />
                    <ReferenceLine x={breakEvenPrice} stroke={theme.palette.warning.main} strokeDasharray="3 3" />
                    <Line 
                      type="monotone" 
                      dataKey="profit" 
                      stroke={theme.palette.primary.main}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Box display="flex" justifyContent="center" alignItems="center" height={300}>
                <Typography color="text.secondary">No payoff data available</Typography>
              </Box>
            )}
          </Grid>

          {/* Greeks */}
          {greeks && (
            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Option Greeks
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6} sm={2.4}>
                  <Box textAlign="center" p={1} border={1} borderColor="divider" borderRadius={1}>
                    <Typography variant="body2" color="text.secondary">
                      Delta
                    </Typography>
                    <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatGreek(greeks.delta)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={2.4}>
                  <Box textAlign="center" p={1} border={1} borderColor="divider" borderRadius={1}>
                    <Typography variant="body2" color="text.secondary">
                      Gamma
                    </Typography>
                    <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatGreek(greeks.gamma)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={2.4}>
                  <Box textAlign="center" p={1} border={1} borderColor="divider" borderRadius={1}>
                    <Typography variant="body2" color="text.secondary">
                      Theta
                    </Typography>
                    <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatGreek(greeks.theta)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={2.4}>
                  <Box textAlign="center" p={1} border={1} borderColor="divider" borderRadius={1}>
                    <Typography variant="body2" color="text.secondary">
                      Vega
                    </Typography>
                    <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatGreek(greeks.vega)}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={2.4}>
                  <Box textAlign="center" p={1} border={1} borderColor="divider" borderRadius={1}>
                    <Typography variant="body2" color="text.secondary">
                      Rho
                    </Typography>
                    <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatGreek(greeks.rho)}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
              
              <Box mt={2}>
                <Typography variant="caption" color="text.secondary">
                  Greeks help measure option sensitivity: Delta (price), Gamma (delta change), 
                  Theta (time decay), Vega (volatility), Rho (interest rates)
                </Typography>
              </Box>
            </Grid>
          )}
        </Grid>
      </CardContent>
    </Card>
  );
};

export default OptionsAnalytics;