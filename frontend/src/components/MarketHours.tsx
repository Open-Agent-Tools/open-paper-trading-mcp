import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Schedule as ScheduleIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { getMarketHours } from '../services/apiClient';
import type { MarketHours } from '../types';

interface MarketHoursProps {
  compact?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number; // in seconds
}

const MarketHoursComponent: React.FC<MarketHoursProps> = ({ 
  compact = false,
  autoRefresh = true,
  refreshInterval = 60 
}) => {
  const [marketHours, setMarketHours] = useState<MarketHours | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchMarketHours = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await getMarketHours();
      if (response.success) {
        setMarketHours(response.market_hours);
        setLastUpdated(new Date());
      } else {
        setError('Failed to load market hours');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load market hours');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketHours();
  }, []);

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchMarketHours, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  const formatTime = (timeString: string): string => {
    try {
      const date = new Date(timeString);
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short'
      });
    } catch {
      return timeString;
    }
  };

  const getMarketStatus = () => {
    if (!marketHours) return { label: 'Unknown', color: 'default' as const };
    
    return marketHours.is_open 
      ? { label: 'Open', color: 'success' as const }
      : { label: 'Closed', color: 'error' as const };
  };

  const status = getMarketStatus();

  if (loading && !marketHours) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Loading market hours...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        <ScheduleIcon color="disabled" fontSize="small" />
        <Typography variant="body2" color="text.secondary">
          Market hours unavailable
        </Typography>
        <IconButton size="small" onClick={fetchMarketHours}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>
    );
  }

  if (!marketHours) {
    return null;
  }

  if (compact) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        <ScheduleIcon fontSize="small" color="action" />
        <Chip
          label={`Market ${status.label}`}
          size="small"
          color={status.color}
          variant="outlined"
        />
        <Tooltip 
          title={`Opens: ${formatTime(marketHours.opens_at)} | Closes: ${formatTime(marketHours.closes_at)}`}
        >
          <IconButton size="small" onClick={fetchMarketHours} disabled={loading}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={1}>
        <ScheduleIcon color="primary" />
        <Typography variant="h6">
          Market Hours
        </Typography>
        <Chip
          label={status.label}
          color={status.color}
          size="small"
        />
      </Box>
      
      <Box display="flex" gap={4} mb={2}>
        <Box>
          <Typography variant="body2" color="text.secondary">
            Opens At
          </Typography>
          <Typography variant="body1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
            {formatTime(marketHours.opens_at)}
          </Typography>
        </Box>
        
        <Box>
          <Typography variant="body2" color="text.secondary">
            Closes At
          </Typography>
          <Typography variant="body1" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
            {formatTime(marketHours.closes_at)}
          </Typography>
        </Box>
      </Box>
      
      <Box display="flex" alignItems="center" justifyContent="space-between">
        {lastUpdated && (
          <Typography variant="caption" color="text.secondary">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </Typography>
        )}
        <IconButton size="small" onClick={fetchMarketHours} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  );
};

export default MarketHoursComponent;