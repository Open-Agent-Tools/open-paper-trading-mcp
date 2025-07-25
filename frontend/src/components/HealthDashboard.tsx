import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Divider,
  Grid,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import StatusIndicator from './StatusIndicator';
import useHealthMonitor from '../hooks/useHealthMonitor';

interface HealthDashboardProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const HealthDashboard: React.FC<HealthDashboardProps> = ({
  autoRefresh = true,
  refreshInterval = 30000,
}) => {
  const [manualRefreshing, setManualRefreshing] = useState(false);
  
  const { health, loading, error, lastChecked, refresh } = useHealthMonitor({
    interval: autoRefresh ? refreshInterval : 0,
    enabled: autoRefresh,
  });

  const handleManualRefresh = async () => {
    setManualRefreshing(true);
    await refresh();
    setManualRefreshing(false);
  };

  const getOverallAlertSeverity = () => {
    if (!health) return 'info';
    
    switch (health.overall) {
      case 'healthy':
        return 'success';
      case 'degraded':
        return 'warning';
      case 'down':
        return 'error';
      default:
        return 'info';
    }
  };

  const getOverallMessage = () => {
    if (!health) return 'Health status is being checked...';
    
    switch (health.overall) {
      case 'healthy':
        return 'All systems are operating normally.';
      case 'degraded':
        return 'Some services are experiencing issues but core functionality remains available.';
      case 'down':
        return 'Multiple services are experiencing issues. Some functionality may be unavailable.';
      default:
        return 'System status is unknown.';
    }
  };

  const formatTimestamp = (timestamp?: number) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="h2">
            System Health Dashboard
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {lastChecked && (
              <Typography variant="caption" color="text.secondary">
                Last checked: {lastChecked.toLocaleTimeString()}
              </Typography>
            )}
            <Tooltip title="Refresh health status">
              <IconButton 
                onClick={handleManualRefresh} 
                disabled={loading || manualRefreshing}
                size="small"
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Error checking system health: {error}
          </Alert>
        )}

        <Alert severity={getOverallAlertSeverity()} sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <InfoIcon fontSize="small" />
            {getOverallMessage()}
          </Box>
        </Alert>

        {health && (
          <>
            <Typography variant="subtitle1" gutterBottom>
              Service Status
            </Typography>
            
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={12} md={4}>
                <Card variant="outlined">
                  <CardContent>
                    <StatusIndicator 
                      healthStatus={health.fastapi} 
                      variant="full"
                      showService={false}
                    />
                    {health.fastapi.statusCode && (
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        Status Code: {health.fastapi.statusCode}
                      </Typography>
                    )}
                    {health.fastapi.timestamp && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Checked: {formatTimestamp(health.fastapi.timestamp)}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card variant="outlined">
                  <CardContent>
                    <StatusIndicator 
                      healthStatus={health.mcp} 
                      variant="full"
                      showService={false}
                    />
                    {health.mcp.statusCode && (
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        Status Code: {health.mcp.statusCode}
                      </Typography>
                    )}
                    {health.mcp.response?.tools_count !== undefined && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Tools: {health.mcp.response.tools_count}
                      </Typography>
                    )}
                    {health.mcp.timestamp && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Checked: {formatTimestamp(health.mcp.timestamp)}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card variant="outlined">
                  <CardContent>
                    <StatusIndicator 
                      healthStatus={health.database} 
                      variant="full"
                      showService={false}
                    />
                    {health.database.statusCode && (
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        Status Code: {health.database.statusCode}
                      </Typography>
                    )}
                    {health.database.timestamp && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Checked: {formatTimestamp(health.database.timestamp)}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="subtitle2">
                Overall System Status
              </Typography>
              <Chip 
                label={health.overall.toUpperCase()} 
                color={getOverallAlertSeverity() as 'success' | 'warning' | 'error'}
                variant="filled"
              />
            </Box>
          </>
        )}

        {(loading && !health) && (
          <Box sx={{ textAlign: 'center', py: 3 }}>
            <Typography color="text.secondary">
              Checking system health...
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default HealthDashboard;