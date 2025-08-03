import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  // Alert,
  // CircularProgress,
  IconButton,
  Grid,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  useTheme,
} from '@mui/material';
import {
  AccountTree as SpreadIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  PlayArrow as ExecuteIcon,
  TrendingUp as CallIcon,
  TrendingDown as PutIcon,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { useAccountContext } from '../contexts/AccountContext';
import { useComponentLoading } from '../contexts/LoadingContext';
import { getOptionsChain, getStockPrice } from '../services/apiClient';
import type { OptionQuote } from '../types';

interface SpreadLeg {
  id: string;
  action: 'buy' | 'sell';
  optionType: 'call' | 'put';
  strike: number;
  expiration: string;
  quantity: number;
  premium: number;
  optionSymbol?: string;
}

interface SpreadPayoffPoint {
  price: number;
  profit: number;
}

const SpreadBuilder: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const { loading, startLoading, stopLoading } = useComponentLoading('spread-builder');
  const [underlying, setUnderlying] = useState<string>('AAPL');
  const [underlyingPrice, setUnderlyingPrice] = useState<number>(150);
  const [legs, setLegs] = useState<SpreadLeg[]>([]);
  const [availableOptions, setAvailableOptions] = useState<OptionQuote[]>([]);
  const [payoffData, setPayoffData] = useState<SpreadPayoffPoint[]>([]);
  const [, setError] = useState<string | null>(null);
  const [showAddLegDialog, setShowAddLegDialog] = useState(false);
  const [newLeg, setNewLeg] = useState<Partial<SpreadLeg>>({ action: 'buy', optionType: 'call', quantity: 1 });

  // Pre-defined spread strategies
  const spreadStrategies = [
    // Vertical Spreads
    {
      name: 'Bull Call Spread',
      description: 'Buy lower strike call, sell higher strike call (bullish)',
      category: 'Directional',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'call' as const, strike: strike - 5, quantity: 1 },
        { action: 'sell' as const, optionType: 'call' as const, strike: strike + 5, quantity: 1 }
      ]
    },
    {
      name: 'Bear Call Spread',
      description: 'Sell lower strike call, buy higher strike call (bearish)',
      category: 'Directional',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'call' as const, strike: strike - 5, quantity: 1 },
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 5, quantity: 1 }
      ]
    },
    {
      name: 'Bull Put Spread',
      description: 'Sell higher strike put, buy lower strike put (bullish)',
      category: 'Directional',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'put' as const, strike: strike + 5, quantity: 1 },
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 5, quantity: 1 }
      ]
    },
    {
      name: 'Bear Put Spread',
      description: 'Buy higher strike put, sell lower strike put (bearish)',
      category: 'Directional',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'put' as const, strike: strike + 5, quantity: 1 },
        { action: 'sell' as const, optionType: 'put' as const, strike: strike - 5, quantity: 1 }
      ]
    },
    
    // Iron Condors & Butterflies
    {
      name: 'Iron Condor',
      description: 'Sell OTM put spread and OTM call spread (neutral)',
      category: 'Neutral',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'put' as const, strike: strike - 10, quantity: 1 },
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 15, quantity: 1 },
        { action: 'sell' as const, optionType: 'call' as const, strike: strike + 10, quantity: 1 },
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 15, quantity: 1 }
      ]
    },
    {
      name: 'Iron Butterfly',
      description: 'Sell ATM call and put, buy OTM call and put (neutral)',
      category: 'Neutral',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 10, quantity: 1 },
        { action: 'sell' as const, optionType: 'put' as const, strike: strike, quantity: 1 },
        { action: 'sell' as const, optionType: 'call' as const, strike: strike, quantity: 1 },
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 10, quantity: 1 }
      ]
    },
    {
      name: 'Long Call Butterfly',
      description: 'Buy 1 low call, sell 2 mid calls, buy 1 high call (neutral)',
      category: 'Neutral',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'call' as const, strike: strike - 10, quantity: 1 },
        { action: 'sell' as const, optionType: 'call' as const, strike: strike, quantity: 2 },
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 10, quantity: 1 }
      ]
    },
    {
      name: 'Long Put Butterfly',
      description: 'Buy 1 high put, sell 2 mid puts, buy 1 low put (neutral)',
      category: 'Neutral',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'put' as const, strike: strike + 10, quantity: 1 },
        { action: 'sell' as const, optionType: 'put' as const, strike: strike, quantity: 2 },
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 10, quantity: 1 }
      ]
    },
    
    // Straddles & Strangles
    {
      name: 'Long Straddle',
      description: 'Buy call and put at same strike (high volatility)',
      category: 'Volatility',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'call' as const, strike, quantity: 1 },
        { action: 'buy' as const, optionType: 'put' as const, strike, quantity: 1 }
      ]
    },
    {
      name: 'Short Straddle',
      description: 'Sell call and put at same strike (low volatility)',
      category: 'Volatility',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'call' as const, strike, quantity: 1 },
        { action: 'sell' as const, optionType: 'put' as const, strike, quantity: 1 }
      ]
    },
    {
      name: 'Long Strangle',
      description: 'Buy OTM call and put (high volatility)',
      category: 'Volatility',
      legs: (strike: number) => [
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 5, quantity: 1 },
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 5, quantity: 1 }
      ]
    },
    {
      name: 'Short Strangle',
      description: 'Sell OTM call and put (low volatility)',
      category: 'Volatility',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'call' as const, strike: strike + 5, quantity: 1 },
        { action: 'sell' as const, optionType: 'put' as const, strike: strike - 5, quantity: 1 }
      ]
    },
    
    // Advanced Strategies
    {
      name: 'Jade Lizard',
      description: 'Sell call spread and sell put (high prob, bullish bias)',
      category: 'Advanced',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'put' as const, strike: strike - 10, quantity: 1 },
        { action: 'sell' as const, optionType: 'call' as const, strike: strike + 5, quantity: 1 },
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 15, quantity: 1 }
      ]
    },
    {
      name: 'Reverse Jade Lizard',
      description: 'Sell put spread and sell call (high prob, bearish bias)',
      category: 'Advanced',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'call' as const, strike: strike + 10, quantity: 1 },
        { action: 'sell' as const, optionType: 'put' as const, strike: strike - 5, quantity: 1 },
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 15, quantity: 1 }
      ]
    },
    {
      name: 'Big Lizard',
      description: 'Iron condor with unbalanced wings (directional bias)',
      category: 'Advanced',
      legs: (strike: number) => [
        { action: 'sell' as const, optionType: 'put' as const, strike: strike - 5, quantity: 1 },
        { action: 'buy' as const, optionType: 'put' as const, strike: strike - 15, quantity: 1 },
        { action: 'sell' as const, optionType: 'call' as const, strike: strike + 10, quantity: 1 },
        { action: 'buy' as const, optionType: 'call' as const, strike: strike + 20, quantity: 1 }
      ]
    }
  ];

  const fetchUnderlyingPrice = async () => {
    try {
      const priceResponse = await getStockPrice(underlying);
      if (priceResponse.success && priceResponse.price_data.price) {
        setUnderlyingPrice(priceResponse.price_data.price);
      }
    } catch (err) {
      console.warn('Could not fetch underlying price:', err);
    }
  };

  const fetchOptionsChain = async () => {
    if (!underlying) return;

    startLoading();
    try {
      const response = await getOptionsChain(underlying);
      if (response.success) {
        const allOptions = [...response.chain.calls, ...response.chain.puts];
        setAvailableOptions(allOptions);
      }
    } catch (err) {
      setError('Failed to fetch options chain');
    } finally {
      stopLoading();
    }
  };

  const calculateSpreadPayoff = (): SpreadPayoffPoint[] => {
    if (legs.length === 0) return [];

    const points: SpreadPayoffPoint[] = [];
    const strikes = legs.map(leg => leg.strike);
    const minStrike = Math.min(...strikes);
    const maxStrike = Math.max(...strikes);
    const range = Math.max(maxStrike - minStrike, 20);
    const minPrice = minStrike - range * 0.5;
    const maxPrice = maxStrike + range * 0.5;
    const stepSize = (maxPrice - minPrice) / 100;

    for (let price = minPrice; price <= maxPrice; price += stepSize) {
      let totalProfit = 0;

      legs.forEach(leg => {
        let intrinsicValue = 0;
        if (leg.optionType === 'call') {
          intrinsicValue = Math.max(0, price - leg.strike);
        } else {
          intrinsicValue = Math.max(0, leg.strike - price);
        }

        const legProfit = leg.action === 'buy' 
          ? (intrinsicValue - leg.premium) * leg.quantity
          : (leg.premium - intrinsicValue) * leg.quantity;

        totalProfit += legProfit;
      });

      points.push({
        price: Math.round(price * 100) / 100,
        profit: Math.round(totalProfit * 100) / 100
      });
    }

    return points;
  };

  // Calculate strategy risk metrics
  const calculateRiskMetrics = () => {
    if (legs.length === 0 || payoffData.length === 0) return null;

    const profits = payoffData.map(p => p.profit);
    const maxProfit = Math.max(...profits);
    const maxLoss = Math.min(...profits);
    
    // Find breakeven points (where profit crosses zero)
    const breakevenPoints: number[] = [];
    for (let i = 1; i < payoffData.length; i++) {
      const prev = payoffData[i - 1];
      const curr = payoffData[i];
      if ((prev.profit <= 0 && curr.profit > 0) || (prev.profit > 0 && curr.profit <= 0)) {
        // Linear interpolation to find exact breakeven
        const ratio = Math.abs(prev.profit) / (Math.abs(prev.profit) + Math.abs(curr.profit));
        const breakevenPrice = prev.price + ratio * (curr.price - prev.price);
        breakevenPoints.push(Math.round(breakevenPrice * 100) / 100);
      }
    }

    // Profit probability (rough estimate based on current price)
    const currentPricePoint = payoffData.find(p => Math.abs(p.price - underlyingPrice) < 1);
    const currentProfit = currentPricePoint?.profit || 0;
    
    // Win probability (simplified - assumes price movement follows normal distribution)
    const profitablePoints = payoffData.filter(p => p.profit > 0).length;
    const winProbability = (profitablePoints / payoffData.length) * 100;

    return {
      maxProfit: maxProfit === Infinity ? 'Unlimited' : formatCurrency(maxProfit),
      maxLoss: maxLoss === -Infinity ? 'Unlimited' : formatCurrency(Math.abs(maxLoss)),
      breakevenPoints,
      currentProfit,
      winProbability: Math.round(winProbability),
      riskRewardRatio: maxLoss !== 0 ? Math.round((maxProfit / Math.abs(maxLoss)) * 100) / 100 : 'N/A'
    };
  };

  const addLeg = () => {
    if (!newLeg.strike || !newLeg.expiration || !newLeg.premium) return;

    const leg: SpreadLeg = {
      id: Date.now().toString(),
      action: newLeg.action || 'buy',
      optionType: newLeg.optionType || 'call',
      strike: newLeg.strike,
      expiration: newLeg.expiration,
      quantity: newLeg.quantity || 1,
      premium: newLeg.premium
    };

    setLegs(prev => [...prev, leg]);
    setNewLeg({ action: 'buy', optionType: 'call', quantity: 1 });
    setShowAddLegDialog(false);
  };

  const removeLeg = (legId: string) => {
    setLegs(prev => prev.filter(leg => leg.id !== legId));
  };

  const applyStrategy = (strategyIndex: number) => {
    const strategy = spreadStrategies[strategyIndex];
    const strategyLegs = strategy.legs(underlyingPrice);
    
    // Find nearest expiration date from available options
    const nearestExpiration = availableOptions.length > 0 
      ? availableOptions[0].expiration 
      : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    const newLegs: SpreadLeg[] = strategyLegs.map((legTemplate, index) => {
      // Find matching option or use default premium
      const matchingOption = availableOptions.find(opt => 
        (opt.symbol.toLowerCase().includes(legTemplate.optionType)) &&
        Math.abs(opt.strike - legTemplate.strike) < 1
      );

      return {
        id: `${Date.now()}-${index}`,
        action: legTemplate.action,
        optionType: legTemplate.optionType,
        strike: legTemplate.strike,
        expiration: nearestExpiration,
        quantity: legTemplate.quantity,
        premium: matchingOption?.price || 2.5
      };
    });

    setLegs(newLegs);
  };

  const executeSpread = async () => {
    if (!selectedAccount || legs.length === 0) return;

    try {
      // In a real implementation, this would create a multi-leg order
      // For now, we'll show an alert about the spread execution
      const totalCost = legs.reduce((sum, leg) => {
        const legCost = leg.action === 'buy' 
          ? leg.premium * leg.quantity
          : -leg.premium * leg.quantity;
        return sum + legCost;
      }, 0);

      alert(`Spread execution would cost: ${totalCost.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}\n\nIn a real implementation, this would submit the multi-leg order to the broker.`);
    } catch (err) {
      setError('Failed to execute spread');
    }
  };

  useEffect(() => {
    fetchUnderlyingPrice();
    fetchOptionsChain();
  }, [underlying]);

  useEffect(() => {
    const payoff = calculateSpreadPayoff();
    setPayoffData(payoff);
  }, [legs]);

  const netCredit = legs.reduce((sum, leg) => {
    const legCost = leg.action === 'buy' ? -leg.premium : leg.premium;
    return sum + legCost * leg.quantity;
  }, 0);

  const riskMetrics = calculateRiskMetrics();

  const formatCurrency = (value: number) => {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    });
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

  return (
    <>
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <SpreadIcon color="primary" />
              <Typography variant="h6">Options Spread Builder</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchOptionsChain} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
          subheader={
            <Typography variant="body2" color="text.secondary">
              Build and analyze multi-leg options strategies
            </Typography>
          }
        />
        <CardContent>
          <Grid container spacing={3}>
            {/* Controls */}
            <Grid item xs={12}>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Underlying Symbol"
                    value={underlying}
                    onChange={(e) => setUnderlying(e.target.value.toUpperCase())}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Current Stock Price"
                    type="number"
                    value={underlyingPrice}
                    onChange={(e) => setUnderlyingPrice(Number(e.target.value))}
                    InputProps={{ inputProps: { step: 0.01 } }}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<AddIcon />}
                    onClick={() => setShowAddLegDialog(true)}
                  >
                    Add Leg
                  </Button>
                </Grid>
              </Grid>
            </Grid>

            {/* Strategy Templates */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Options Strategy Templates
              </Typography>
              
              {/* Group strategies by category */}
              {['Directional', 'Neutral', 'Volatility', 'Advanced'].map(category => {
                const categoryStrategies = spreadStrategies.filter(s => s.category === category);
                if (categoryStrategies.length === 0) return null;
                
                return (
                  <Box key={category} sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {category} Strategies
                    </Typography>
                    <Box display="flex" gap={1} flexWrap="wrap">
                      {categoryStrategies.map((strategy) => {
                        const globalIndex = spreadStrategies.indexOf(strategy);
                        return (
                          <Chip
                            key={strategy.name}
                            label={strategy.name}
                            variant="outlined"
                            onClick={() => applyStrategy(globalIndex)}
                            sx={{ 
                              cursor: 'pointer',
                              '&:hover': { backgroundColor: theme.palette.action.hover }
                            }}
                          />
                        );
                      })}
                    </Box>
                  </Box>
                );
              })}
            </Grid>

            {/* Spread Legs */}
            <Grid item xs={12}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="subtitle1">
                  Spread Legs ({legs.length})
                </Typography>
                {legs.length > 0 && (
                  <Box display="flex" alignItems="center" gap={2}>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        color: netCredit >= 0 ? theme.palette.success.main : theme.palette.error.main,
                        fontFamily: 'Roboto Mono, monospace' 
                      }}
                    >
                      Net {netCredit >= 0 ? 'Credit' : 'Debit'}: {formatCurrency(Math.abs(netCredit))}
                    </Typography>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<ExecuteIcon />}
                      onClick={executeSpread}
                      disabled={!selectedAccount}
                    >
                      Execute Spread
                    </Button>
                  </Box>
                )}
              </Box>
              
              {legs.length > 0 ? (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Action</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell align="right">Strike</TableCell>
                        <TableCell align="right">Quantity</TableCell>
                        <TableCell align="right">Premium</TableCell>
                        <TableCell>Expiration</TableCell>
                        <TableCell align="right">Cost</TableCell>
                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {legs.map((leg) => {
                        const legCost = (leg.action === 'buy' ? -leg.premium : leg.premium) * leg.quantity;
                        return (
                          <TableRow key={leg.id}>
                            <TableCell>
                              <Chip 
                                label={leg.action.toUpperCase()} 
                                size="small"
                                color={leg.action === 'buy' ? 'primary' : 'secondary'}
                              />
                            </TableCell>
                            <TableCell>
                              <Box display="flex" alignItems="center" gap={1}>
                                {leg.optionType === 'call' ? (
                                  <CallIcon color="success" fontSize="small" />
                                ) : (
                                  <PutIcon color="error" fontSize="small" />
                                )}
                                <Typography variant="body2">
                                  {leg.optionType.toUpperCase()}
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                                ${leg.strike.toFixed(2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                                {leg.quantity}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                                ${leg.premium.toFixed(2)}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2">
                                {new Date(leg.expiration).toLocaleDateString()}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  fontFamily: 'Roboto Mono, monospace',
                                  color: legCost >= 0 ? theme.palette.success.main : theme.palette.error.main
                                }}
                              >
                                {formatCurrency(legCost)}
                              </Typography>
                            </TableCell>
                            <TableCell align="center">
                              <IconButton 
                                size="small" 
                                onClick={() => removeLeg(leg.id)}
                                color="error"
                              >
                                <RemoveIcon />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Box display="flex" justifyContent="center" alignItems="center" minHeight={100}>
                  <Typography color="text.secondary">Add legs to build your spread strategy</Typography>
                </Box>
              )}
            </Grid>

            {/* Risk Analysis */}
            {riskMetrics && (
              <Grid item xs={12}>
                <Typography variant="subtitle1" gutterBottom>
                  Strategy Risk Analysis
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={3}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        Max Profit
                      </Typography>
                      <Typography variant="h6" color="success.main" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                        {riskMetrics.maxProfit}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        Max Loss
                      </Typography>
                      <Typography variant="h6" color="error.main" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                        {riskMetrics.maxLoss}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        Win Probability
                      </Typography>
                      <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                        {riskMetrics.winProbability}%
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        Risk/Reward
                      </Typography>
                      <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                        {riskMetrics.riskRewardRatio}
                      </Typography>
                    </Paper>
                  </Grid>
                  
                  {riskMetrics.breakevenPoints.length > 0 && (
                    <Grid item xs={12}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Breakeven Points
                        </Typography>
                        <Box display="flex" gap={1} flexWrap="wrap">
                          {riskMetrics.breakevenPoints.map((point, index) => (
                            <Chip
                              key={index}
                              label={formatCurrency(point)}
                              size="small"
                              variant="outlined"
                              sx={{ fontFamily: 'Roboto Mono, monospace' }}
                            />
                          ))}
                        </Box>
                      </Paper>
                    </Grid>
                  )}
                </Grid>
              </Grid>
            )}

            {/* Payoff Diagram */}
            {payoffData.length > 0 && (
              <Grid item xs={12}>
                <Typography variant="subtitle1" gutterBottom>
                  Profit/Loss Diagram
                </Typography>
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
                      <ReferenceLine x={underlyingPrice} stroke={theme.palette.primary.main} strokeDasharray="3 3" />
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
              </Grid>
            )}
          </Grid>
        </CardContent>
      </Card>

      {/* Add Leg Dialog */}
      <Dialog open={showAddLegDialog} onClose={() => setShowAddLegDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Option Leg</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Action</InputLabel>
                <Select
                  value={newLeg.action || 'buy'}
                  label="Action"
                  onChange={(e) => setNewLeg(prev => ({ ...prev, action: e.target.value as 'buy' | 'sell' }))}
                >
                  <MenuItem value="buy">Buy</MenuItem>
                  <MenuItem value="sell">Sell</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Option Type</InputLabel>
                <Select
                  value={newLeg.optionType || 'call'}
                  label="Option Type"
                  onChange={(e) => setNewLeg(prev => ({ ...prev, optionType: e.target.value as 'call' | 'put' }))}
                >
                  <MenuItem value="call">Call</MenuItem>
                  <MenuItem value="put">Put</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                label="Strike Price"
                type="number"
                value={newLeg.strike || ''}
                onChange={(e) => setNewLeg(prev => ({ ...prev, strike: Number(e.target.value) }))}
                InputProps={{ inputProps: { step: 0.5 } }}
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                label="Quantity"
                type="number"
                value={newLeg.quantity || 1}
                onChange={(e) => setNewLeg(prev => ({ ...prev, quantity: Number(e.target.value) }))}
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                label="Premium"
                type="number"
                value={newLeg.premium || ''}
                onChange={(e) => setNewLeg(prev => ({ ...prev, premium: Number(e.target.value) }))}
                InputProps={{ inputProps: { step: 0.01 } }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                size="small"
                label="Expiration Date"
                type="date"
                value={newLeg.expiration || ''}
                onChange={(e) => setNewLeg(prev => ({ ...prev, expiration: e.target.value }))}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAddLegDialog(false)}>Cancel</Button>
          <Button 
            onClick={addLeg} 
            variant="contained"
            disabled={!newLeg.strike || !newLeg.expiration || !newLeg.premium}
          >
            Add Leg
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SpreadBuilder;