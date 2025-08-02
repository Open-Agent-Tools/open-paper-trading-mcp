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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tabs,
  Tab,
  Chip,
} from '@mui/material';
import {
  ShowChart as ShowChartIcon,
  Refresh as RefreshIcon,
  TrendingUp as CallIcon,
  TrendingDown as PutIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getOptionsChain, getOptionExpirations } from '../services/apiClient';
import type { OptionsChainData, OptionQuote } from '../types';

interface OptionsChainProps {
  symbol: string;
  onLoadingChange?: (loading: boolean) => void;
  onOptionSelect?: (option: OptionQuote) => void;
}

const OptionsChain: React.FC<OptionsChainProps> = ({ 
  symbol, 
  onLoadingChange,
  onOptionSelect
}) => {
  const theme = useTheme();
  const [chainData, setChainData] = useState<OptionsChainData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedExpiration, setSelectedExpiration] = useState<string>('');
  const [availableExpirations, setAvailableExpirations] = useState<string[]>([]);
  const [tabValue, setTabValue] = useState(0); // 0 = calls, 1 = puts

  const fetchExpirations = async () => {
    if (!symbol) return;

    // Reset expiration selection when symbol changes
    setSelectedExpiration('');
    setChainData(null);

    try {
      const response = await getOptionExpirations(symbol);
      if (response.success && response.expirations) {
        setAvailableExpirations(response.expirations);
        // Don't auto-select expiration - let user choose first
      }
    } catch (err) {
      // Silently handle - expirations are optional
    }
  };

  const fetchOptionsChain = async () => {
    if (!symbol) {
      setChainData(null);
      return;
    }

    // Don't fetch options chain if no expiration is selected
    if (!selectedExpiration) {
      setChainData(null);
      return;
    }

    setLoading(true);
    setError(null);
    onLoadingChange?.(true);

    try {
      const response = await getOptionsChain(symbol, selectedExpiration);
      if (response.success) {
        setChainData({
          underlying: response.underlying,
          expiration_filter: response.expiration_filter,
          chain: response.chain
        });
      } else {
        setError('Failed to load options chain');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load options chain');
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchExpirations();
  }, [symbol]);

  useEffect(() => {
    fetchOptionsChain();
  }, [symbol, selectedExpiration]);

  const formatExpiration = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  const formatVolatility = (iv: number): string => {
    return `${(iv * 100).toFixed(1)}%`;
  };

  const getMoneyness = (strike: number, currentPrice: number, isCall: boolean): string => {
    if (isCall) {
      if (strike < currentPrice) return 'ITM'; // In the money
      if (strike === currentPrice) return 'ATM'; // At the money
      return 'OTM'; // Out of the money
    } else {
      if (strike > currentPrice) return 'ITM';
      if (strike === currentPrice) return 'ATM';
      return 'OTM';
    }
  };

  const getMoneynessColor = (moneyness: string) => {
    switch (moneyness) {
      case 'ITM': return theme.palette.success.main;
      case 'ATM': return theme.palette.warning.main;
      case 'OTM': return theme.palette.text.secondary;
      default: return theme.palette.text.secondary;
    }
  };

  const renderOptionsTable = (options: OptionQuote[], type: 'calls' | 'puts') => {
    if (!options || options.length === 0) {
      return (
        <Box p={4} textAlign="center">
          <Typography variant="body2" color="text.secondary">
            No {type} available for selected expiration
          </Typography>
        </Box>
      );
    }

    // Assume current price is around the middle of available strikes
    const strikes = options.map(o => o.strike);
    const currentPrice = strikes[Math.floor(strikes.length / 2)] || 0;

    return (
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>Strike</TableCell>
              <TableCell align="right">Bid</TableCell>
              <TableCell align="right">Ask</TableCell>
              <TableCell align="right">Last</TableCell>
              <TableCell align="right">Volume</TableCell>
              <TableCell align="right">OI</TableCell>
              <TableCell align="right">IV</TableCell>
              <TableCell align="center">Type</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {options.map((option, index) => {
              const moneyness = getMoneyness(option.strike, currentPrice, type === 'calls');
              const midPrice = (option.bid + option.ask) / 2;
              
              return (
                <TableRow 
                  key={index}
                  hover
                  sx={{ 
                    cursor: onOptionSelect ? 'pointer' : 'default',
                    '&:hover': onOptionSelect ? { backgroundColor: theme.palette.action.hover } : {}
                  }}
                  onClick={() => onOptionSelect?.(option)}
                >
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography 
                        variant="body2" 
                        sx={{ 
                          fontFamily: 'Roboto Mono, monospace',
                          fontWeight: moneyness === 'ATM' ? 'bold' : 'normal',
                          color: getMoneynessColor(moneyness)
                        }}
                      >
                        ${option.strike.toFixed(2)}
                      </Typography>
                      <Chip
                        label={moneyness}
                        size="small"
                        variant="outlined"
                        sx={{ 
                          fontSize: '0.6rem',
                          height: 18,
                          color: getMoneynessColor(moneyness),
                          borderColor: getMoneynessColor(moneyness)
                        }}
                      />
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      ${option.bid.toFixed(2)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      ${option.ask.toFixed(2)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Box>
                      <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                        {option.price !== null ? `$${option.price.toFixed(2)}` : '-'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                        Mid: {!isNaN(midPrice) ? `$${midPrice.toFixed(2)}` : '-'}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {option.volume !== null ? option.volume.toLocaleString() : '-'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {option.open_interest !== null ? option.open_interest.toLocaleString() : '-'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatVolatility(option.implied_volatility)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    {type === 'calls' ? (
                      <CallIcon color="success" fontSize="small" />
                    ) : (
                      <PutIcon color="error" fontSize="small" />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  if (loading && !chainData) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading options chain...
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
                {symbol} Options Chain
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchOptionsChain} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="info">
            {error}. Options data may not be available for this symbol or require a subscription.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!chainData && symbol && availableExpirations.length > 0 && !selectedExpiration) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <ShowChartIcon color="primary" />
              <Typography variant="h6">
                {symbol} Options Chain
              </Typography>
            </Box>
          }
        />
        <CardContent>
          <Box textAlign="center" py={4}>
            <Typography variant="h6" gutterBottom>
              Select an Expiration Date
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Choose from {availableExpirations.length} available expiration dates to view options chain
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap" justifyContent="center">
              {availableExpirations.slice(0, 8).map((exp) => (
                <Chip
                  key={exp}
                  label={formatExpiration(exp)}
                  onClick={() => setSelectedExpiration(exp)}
                  variant="outlined"
                  color="primary"
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
            {availableExpirations.length > 8 && (
              <Typography variant="caption" color="text.secondary" mt={2} display="block">
                And {availableExpirations.length - 8} more dates...
              </Typography>
            )}
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (!chainData) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Select a stock to view options chain
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const currentOptions = tabValue === 0 ? chainData.chain.calls : chainData.chain.puts;
  const optionType = tabValue === 0 ? 'calls' : 'puts';

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <ShowChartIcon color="primary" />
            <Typography variant="h6">
              {symbol} Options Chain
            </Typography>
          </Box>
        }
        action={
          <Box display="flex" alignItems="center" gap={1}>
            {availableExpirations.length > 0 && (
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <Select
                  value={selectedExpiration}
                  onChange={(e) => setSelectedExpiration(e.target.value)}
                  displayEmpty
                >
                  {availableExpirations.map((exp) => (
                    <MenuItem key={exp} value={exp}>
                      {formatExpiration(exp)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
            <IconButton onClick={fetchOptionsChain} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Box>
        }
        subheader={
          <Typography variant="body2" color="text.secondary">
            {chainData.chain.calls_count} calls • {chainData.chain.puts_count} puts
            {selectedExpiration && ` • Expires ${formatExpiration(selectedExpiration)}`}
          </Typography>
        }
      />
      
      <CardContent>
        {/* Summary Stats */}
        <Box display="flex" gap={4} mb={3}>
          <Box textAlign="center">
            <Typography variant="h6" color="success.main">
              {chainData.chain.calls_count}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Calls
            </Typography>
          </Box>
          <Box textAlign="center">
            <Typography variant="h6" color="error.main">
              {chainData.chain.puts_count}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Puts
            </Typography>
          </Box>
        </Box>

        {/* Tabs for Calls/Puts */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
            <Tab 
              label={`Calls (${chainData.chain.calls_count})`} 
              icon={<CallIcon />}
              iconPosition="start"
            />
            <Tab 
              label={`Puts (${chainData.chain.puts_count})`} 
              icon={<PutIcon />}
              iconPosition="start"
            />
          </Tabs>
        </Box>

        {/* Options Table */}
        {renderOptionsTable(currentOptions, optionType)}

        {/* Legend */}
        <Box mt={2} display="flex" gap={2} flexWrap="wrap">
          <Typography variant="caption" color="text.secondary">
            ITM = In the Money • ATM = At the Money • OTM = Out of the Money
          </Typography>
        </Box>
        <Box display="flex" gap={2} flexWrap="wrap">
          <Typography variant="caption" color="text.secondary">
            OI = Open Interest • IV = Implied Volatility
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default OptionsChain;