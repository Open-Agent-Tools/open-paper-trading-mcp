import React from 'react';
import { Box, Typography, Chip } from '@mui/material';

interface StatusIndicatorProps {
  serviceName: string;
  status: 'healthy' | 'unhealthy' | 'pending';
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ serviceName, status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'unhealthy':
        return 'error';
      default:
        return 'warning';
    }
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="body2">{serviceName}:</Typography>
      <Chip label={status} color={getStatusColor()} size="small" />
    </Box>
  );
};

export default StatusIndicator;
