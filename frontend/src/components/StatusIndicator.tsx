import React from 'react';
import { Box, Typography, Chip } from '@mui/material';
import type { HealthStatus } from '../types';

interface StatusIndicatorProps {
  healthStatus: HealthStatus;
  showService?: boolean;
  size?: 'small' | 'medium';
  variant?: 'chip' | 'dot' | 'text' | 'full';
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ 
  healthStatus, 
  showService = true,
  size = 'small',
  variant = 'chip'
}) => {
  const { service, status, error } = healthStatus;

  // Colors aligned with style guide
  const getStatusColor = () => {
    switch (status) {
      case 'healthy':
        return 'success'; // --success: #006b3c
      case 'unhealthy':
        return 'warning'; // --warning: #b45309
      case 'error':
        return 'error'; // --error: #dc3545
      default:
        return 'default'; // --neutral-dark: #6c757d
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'healthy':
        return 'Online';
      case 'unhealthy':
        return 'Degraded';
      case 'error':
        return 'Offline';
      default:
        return 'Unknown';
    }
  };

  const getStatusDotColor = () => {
    switch (status) {
      case 'healthy':
        return '#006b3c'; // --success
      case 'unhealthy':
        return '#b45309'; // --warning  
      case 'error':
        return '#dc3545'; // --error
      default:
        return '#6c757d'; // --neutral-dark
    }
  };

  if (variant === 'dot') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {showService && (
          <Typography variant="body2" color="text.secondary">
            {service}:
          </Typography>
        )}
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: getStatusDotColor(),
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {getStatusText()}
        </Typography>
      </Box>
    );
  }

  if (variant === 'text') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {showService && (
          <Typography variant="body2" color="text.secondary">
            {service}:
          </Typography>
        )}
        <Typography 
          variant="body2" 
          sx={{ color: getStatusDotColor(), fontWeight: 500 }}
          title={error || undefined}
        >
          {getStatusText()}
        </Typography>
      </Box>
    );
  }

  if (variant === 'full') {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="h6" component="h3">
            {service}
          </Typography>
          <Chip 
            label={getStatusText()} 
            color={getStatusColor()} 
            size="small"
          />
        </Box>
        {error && (
          <Typography variant="body2" color="error" sx={{ fontSize: '0.75rem' }}>
            Error: {error}
          </Typography>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {showService && (
        <Typography variant="body2" color="text.secondary">
          {service}:
        </Typography>
      )}
      <Chip 
        label={getStatusText()} 
        color={getStatusColor()} 
        size={size}
        title={error || undefined}
      />
    </Box>
  );
};

export default StatusIndicator;
