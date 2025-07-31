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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  useTheme,
} from '@mui/material';
import {
  Event as EventIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { useAccountContext } from '../contexts/AccountContext';
import { getPositions } from '../services/apiClient';
// import type { Position } from '../types';

interface ExpirationEvent {
  symbol: string;
  underlying: string;
  expiration: string;
  daysToExpiration: number;
  quantity: number;
  optionType: string;
  strike: number;
  currentValue: number;
  unrealizedPnL: number;
  status: 'expired' | 'expiring-today' | 'expiring-soon' | 'normal';
}

const OptionsExpirationCalendar: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [expirations, setExpirations] = useState<ExpirationEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculateExpirationStatus = (expirationDate: string): { daysToExpiration: number; status: ExpirationEvent['status'] } => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const expDate = new Date(expirationDate);
    expDate.setHours(0, 0, 0, 0);
    
    const diffTime = expDate.getTime() - today.getTime();
    const daysToExpiration = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    let status: ExpirationEvent['status'] = 'normal';
    if (daysToExpiration < 0) {
      status = 'expired';
    } else if (daysToExpiration === 0) {
      status = 'expiring-today';
    } else if (daysToExpiration <= 7) {
      status = 'expiring-soon';
    }
    
    return { daysToExpiration, status };
  };

  const fetchExpirationData = async () => {
    if (!selectedAccount) {
      setExpirations([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getPositions(selectedAccount.id);
      
      if (response.success) {
        const positions = response.positions || [];
        
        // Filter and process options positions
        const optionsPositions = positions.filter((p: any) => p.option_type && p.expiration_date);
        
        const expirationEvents: ExpirationEvent[] = optionsPositions.map((position: any) => {
          const { daysToExpiration, status } = calculateExpirationStatus(position.expiration_date!);
          
          return {
            symbol: position.symbol,
            underlying: position.underlying_symbol || position.symbol.split(' ')[0],
            expiration: position.expiration_date!,
            daysToExpiration,
            quantity: position.quantity,
            optionType: position.option_type!,
            strike: position.strike || 0,
            currentValue: position.market_value || 0,
            unrealizedPnL: position.unrealized_pnl || 0,
            status
          };
        });
        
        // Sort by days to expiration (soonest first)
        expirationEvents.sort((a, b) => a.daysToExpiration - b.daysToExpiration);
        
        setExpirations(expirationEvents);
      } else {
        setError('Failed to load position data');
      }
    } catch (err) {
      setError('Failed to load expiration data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpirationData();
  }, [selectedAccount]);

  const formatCurrency = (value: number) => {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    });
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  const getStatusColor = (status: ExpirationEvent['status']) => {
    switch (status) {
      case 'expired': return theme.palette.error.main;
      case 'expiring-today': return theme.palette.error.main;
      case 'expiring-soon': return theme.palette.warning.main;
      case 'normal': return theme.palette.success.main;
      default: return theme.palette.text.secondary;
    }
  };

  const getStatusLabel = (status: ExpirationEvent['status'], days: number) => {
    switch (status) {
      case 'expired': return 'EXPIRED';
      case 'expiring-today': return 'TODAY';
      case 'expiring-soon': return `${days}D`;
      case 'normal': return `${days}D`;
      default: return `${days}D`;
    }
  };

  const getStatusIcon = (status: ExpirationEvent['status']) => {
    switch (status) {
      case 'expired':
      case 'expiring-today':
        return <WarningIcon fontSize="small" />;
      case 'expiring-soon':
        return <ScheduleIcon fontSize="small" />;
      default:
        return <EventIcon fontSize="small" />;
    }
  };

  // Summary statistics
  const expiringToday = expirations.filter(e => e.status === 'expiring-today').length;
  const expiringSoon = expirations.filter(e => e.status === 'expiring-soon').length;
  const expired = expirations.filter(e => e.status === 'expired').length;
  const totalValue = expirations.reduce((sum, e) => sum + e.currentValue, 0);
  const totalPnL = expirations.reduce((sum, e) => sum + e.unrealizedPnL, 0);

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
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
              <EventIcon color="primary" />
              <Typography variant="h6">Options Expiration Calendar</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchExpirationData} disabled={loading}>
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
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
          <Typography color="text.secondary">Select an account to view expiration calendar</Typography>
        </CardContent>
      </Card>
    );
  }

  if (expirations.length === 0) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <EventIcon color="primary" />
              <Typography variant="h6">Options Expiration Calendar</Typography>
            </Box>
          }
        />
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
            <Typography color="text.secondary">No options positions found</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <EventIcon color="primary" />
            <Typography variant="h6">Options Expiration Calendar</Typography>
          </Box>
        }
        action={
          <IconButton onClick={fetchExpirationData} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
        subheader={
          <Typography variant="body2" color="text.secondary">
            {expirations.length} options positions • Total Value: {formatCurrency(totalValue)}
          </Typography>
        }
      />
      <CardContent>
        {/* Summary Statistics */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {expired > 0 && (
            <Grid item xs={6} sm={3}>
              <Box textAlign="center" p={1} border={1} borderColor="error.main" borderRadius={1}>
                <Typography variant="h6" color="error.main">
                  {expired}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Expired
                </Typography>
              </Box>
            </Grid>
          )}
          {expiringToday > 0 && (
            <Grid item xs={6} sm={3}>
              <Box textAlign="center" p={1} border={1} borderColor="error.main" borderRadius={1}>
                <Typography variant="h6" color="error.main">
                  {expiringToday}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Expiring Today
                </Typography>
              </Box>
            </Grid>
          )}
          {expiringSoon > 0 && (
            <Grid item xs={6} sm={3}>
              <Box textAlign="center" p={1} border={1} borderColor="warning.main" borderRadius={1}>
                <Typography variant="h6" color="warning.main">
                  {expiringSoon}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Expiring Soon
                </Typography>
              </Box>
            </Grid>
          )}
          <Grid item xs={6} sm={3}>
            <Box textAlign="center" p={1} border={1} borderColor="divider" borderRadius={1}>
              <Typography 
                variant="h6" 
                sx={{ color: totalPnL >= 0 ? theme.palette.success.main : theme.palette.error.main }}
              >
                {formatCurrency(totalPnL)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total P&L
              </Typography>
            </Box>
          </Grid>
        </Grid>

        {/* Expiration Table */}
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Strike</TableCell>
                <TableCell align="right">Quantity</TableCell>
                <TableCell>Expiration</TableCell>
                <TableCell align="right">Value</TableCell>
                <TableCell align="right">P&L</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {expirations.map((expiration, index) => (
                <TableRow 
                  key={index}
                  sx={{
                    backgroundColor: expiration.status === 'expiring-today' || expiration.status === 'expired'
                      ? theme.palette.error.light + '20'
                      : expiration.status === 'expiring-soon'
                      ? theme.palette.warning.light + '20'
                      : 'inherit'
                  }}
                >
                  <TableCell>
                    <Chip
                      icon={getStatusIcon(expiration.status)}
                      label={getStatusLabel(expiration.status, expiration.daysToExpiration)}
                      size="small"
                      sx={{
                        backgroundColor: getStatusColor(expiration.status),
                        color: 'white',
                        '& .MuiChip-icon': { color: 'white' }
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {expiration.underlying}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        color: expiration.optionType === 'call' 
                          ? theme.palette.success.main 
                          : theme.palette.error.main 
                      }}
                    >
                      {expiration.optionType.toUpperCase()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      ${expiration.strike.toFixed(2)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {expiration.quantity}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDate(expiration.expiration)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                      {formatCurrency(expiration.currentValue)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        fontFamily: 'Roboto Mono, monospace',
                        color: expiration.unrealizedPnL >= 0 
                          ? theme.palette.success.main 
                          : theme.palette.error.main 
                      }}
                    >
                      {formatCurrency(expiration.unrealizedPnL)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Legend */}
        <Box mt={2} display="flex" gap={2} flexWrap="wrap">
          <Typography variant="caption" color="text.secondary">
            Status indicators: Red = Expired/Today, Orange = 1-7 days, Green = 8+ days
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default OptionsExpirationCalendar;