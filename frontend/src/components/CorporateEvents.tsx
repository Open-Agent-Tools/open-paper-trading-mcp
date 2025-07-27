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
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import {
  Event as EventIcon,
  Refresh as RefreshIcon,
  TrendingUp as DividendIcon,
  Business as EarningsIcon,
  CompareArrows as SplitIcon,
} from '@mui/icons-material';
import { getStockEvents } from '../services/apiClient';
import { FONTS } from '../theme';
import type { StockEventsData, CorporateEvent } from '../types';

interface CorporateEventsProps {
  symbol: string;
  onLoadingChange?: (loading: boolean) => void;
}

const CorporateEvents: React.FC<CorporateEventsProps> = ({ 
  symbol, 
  onLoadingChange 
}) => {
  const [eventsData, setEventsData] = useState<StockEventsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStockEvents = async () => {
    if (!symbol) {
      setEventsData(null);
      return;
    }

    setLoading(true);
    setError(null);
    onLoadingChange?.(true);

    try {
      const response = await getStockEvents(symbol);
      if (response.success) {
        setEventsData(response.events);
      } else {
        setError('Failed to load corporate events');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load corporate events');
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchStockEvents();
  }, [symbol]);

  const getEventIcon = (eventType: string) => {
    switch (eventType.toLowerCase()) {
      case 'dividend':
        return <DividendIcon color="success" />;
      case 'earnings':
        return <EarningsIcon color="primary" />;
      case 'split':
        return <SplitIcon color="info" />;
      default:
        return <EventIcon color="action" />;
    }
  };

  const getEventChipColor = (eventType: string) => {
    switch (eventType.toLowerCase()) {
      case 'dividend':
        return 'success' as const;
      case 'earnings':
        return 'primary' as const;
      case 'split':
        return 'info' as const;
      default:
        return 'default' as const;
    }
  };

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  const formatAmount = (amount: number | null | undefined): string => {
    if (amount === null || amount === undefined) {
      return 'N/A';
    }
    return `$${amount.toFixed(2)}`;
  };

  if (loading && !eventsData) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading corporate events...
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
              <EventIcon color="primary" />
              <Typography variant="h6">
                {symbol} Corporate Events
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchStockEvents} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="warning">
            {error}. Corporate events data may not be available for this symbol.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!eventsData || !eventsData.events || eventsData.events.length === 0) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <EventIcon color="primary" />
              <Typography variant="h6">
                {symbol} Corporate Events
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchStockEvents} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            No upcoming corporate events found for {symbol}
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
            <EventIcon color="primary" />
            <Typography variant="h6">
              {symbol} Corporate Events
            </Typography>
            <Chip
              label={`${eventsData.events.length} events`}
              size="small"
              color="primary"
              variant="outlined"
            />
          </Box>
        }
        action={
          <IconButton onClick={fetchStockEvents} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
      />
      
      <CardContent>
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Amount</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Description</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {eventsData.events.map((event: CorporateEvent, index: number) => (
                <TableRow key={index} hover>
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={1}>
                      {getEventIcon(event.type)}
                      <Chip
                        label={event.type}
                        size="small"
                        color={getEventChipColor(event.type)}
                        variant="outlined"
                      />
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                      {formatDate(event.date)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                      {formatAmount(event.amount)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label="Scheduled"
                      size="small"
                      color="default"
                      variant="filled"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {event.description || 'No description available'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
          Corporate events for owned positions • {eventsData.events.length} total events
        </Typography>
      </CardContent>
    </Card>
  );
};

export default CorporateEvents;