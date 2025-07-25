import React from 'react';
import { Box, Typography, Tooltip, CircularProgress } from '@mui/material';
import StatusIndicator from './StatusIndicator';
import useHealthMonitor from '../hooks/useHealthMonitor';

interface SystemHealthIndicatorProps {
  compact?: boolean;
  showDetails?: boolean;
  variant?: 'full' | 'summary' | 'minimal';
  refreshInterval?: number;
}

const SystemHealthIndicator: React.FC<SystemHealthIndicatorProps> = ({
  compact = false,
  showDetails = false,
  variant = 'summary',
  refreshInterval = 30000, // 30 seconds
}) => {
  const { health, loading, error, lastChecked } = useHealthMonitor({
    interval: refreshInterval,
    enabled: true,
  });

  const getOverallStatusColor = (overall?: string) => {
    switch (overall) {
      case 'healthy':
        return '#006b3c'; // --success from style guide
      case 'degraded':
        return '#b45309'; // --warning from style guide
      case 'down':
        return '#dc3545'; // --error from style guide
      default:
        return '#6c757d'; // --neutral-dark from style guide
    }
  };

  const getServiceStatusColor = (status?: string) => {
    switch (status) {
      case 'healthy':
        return '#006b3c'; // --success from style guide
      case 'unhealthy':
        return '#b45309'; // --warning from style guide
      case 'error':
        return '#dc3545'; // --error from style guide
      case 'degraded':
        return '#b45309'; // --warning from style guide
      case 'down':
        return '#dc3545'; // --error from style guide
      default:
        return '#6c757d'; // --neutral-dark from style guide
    }
  };

  const getOverallStatusText = (overall?: string) => {
    switch (overall) {
      case 'healthy':
        return 'All Systems Online';
      case 'degraded':
        return 'Some Issues Detected';
      case 'down':
        return 'System Issues';
      default:
        return 'Status Unknown';
    }
  };

  const getOverallStatusSimple = (status?: string) => {
    switch (status) {
      case 'healthy':
        return 'Online';
      case 'unhealthy':
        return 'Offline';
      case 'error':
        return 'Offline';
      case 'degraded':
        return 'Degraded';
      case 'down':
        return 'Offline';
      default:
        return 'Unknown';
    }
  };


  if (loading && !health) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={12} />
        <Typography variant="body2" color="text.secondary">
          Checking system status...
        </Typography>
      </Box>
    );
  }

  if (error && !health) {
    return (
      <Typography variant="body2" color="error">
        Unable to check system status
      </Typography>
    );
  }

  if (!health) {
    return (
      <Typography variant="body2" color="text.secondary">
        System status unavailable
      </Typography>
    );
  }

  if (variant === 'minimal') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: getOverallStatusColor(health.overall),
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {getOverallStatusText(health.overall)}
        </Typography>
      </Box>
    );
  }

  if (variant === 'summary') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            API -
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ color: getServiceStatusColor(health.fastapi.status), fontWeight: 500 }}
          >
            {getOverallStatusSimple(health.fastapi.status)}
          </Typography>
        </Box>
        
        <Typography variant="body2" color="text.secondary">
          |
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            MCP -
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ color: getServiceStatusColor(health.mcp.status), fontWeight: 500 }}
          >
            {getOverallStatusSimple(health.mcp.status)}
          </Typography>
        </Box>
        
        <Typography variant="body2" color="text.secondary">
          |
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Database -
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ color: getServiceStatusColor(health.database.status), fontWeight: 500 }}
          >
            {getOverallStatusSimple(health.database.status)}
          </Typography>
        </Box>

        {showDetails && (
          <Tooltip
            title={
              <Box>
                <Typography variant="caption">Service Details:</Typography>
                <br />
                <Typography variant="caption">FastAPI: {health.fastapi.status}</Typography>
                <br />
                <Typography variant="caption">MCP: {health.mcp.status}</Typography>
                <br />
                <Typography variant="caption">Database: {health.database.status}</Typography>
                {lastChecked && (
                  <>
                    <br />
                    <Typography variant="caption">
                      Last checked: {lastChecked.toLocaleTimeString()}
                    </Typography>
                  </>
                )}
              </Box>
            }
          >
            <Typography 
              variant="body2" 
              color="text.secondary"
              sx={{ cursor: 'help', textDecoration: 'underline dotted' }}
            >
              Details
            </Typography>
          </Tooltip>
        )}
      </Box>
    );
  }

  // Full variant
  return (
    <Box sx={{ display: 'flex', flexDirection: compact ? 'row' : 'column', gap: 1 }}>
      <Typography variant="h6" gutterBottom={!compact}>
        System Status
      </Typography>
      
      <Box sx={{ display: 'flex', flexDirection: compact ? 'row' : 'column', gap: compact ? 2 : 1 }}>
        <StatusIndicator 
          healthStatus={health.fastapi} 
          variant="dot" 
          showService={true}
        />
        <StatusIndicator 
          healthStatus={health.mcp} 
          variant="dot" 
          showService={true}
        />
        <StatusIndicator 
          healthStatus={health.database} 
          variant="dot" 
          showService={true}
        />
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: compact ? 0 : 1 }}>
        <Typography variant="body2" color="text.secondary">
          Overall:
        </Typography>
        <Typography 
          variant="body2" 
          sx={{ color: getOverallStatusColor(health.overall), fontWeight: 500 }}
        >
          {getOverallStatusText(health.overall)}
        </Typography>
      </Box>

      {lastChecked && (
        <Typography variant="caption" color="text.secondary">
          Last updated: {lastChecked.toLocaleTimeString()}
        </Typography>
      )}
    </Box>
  );
};

export default SystemHealthIndicator;