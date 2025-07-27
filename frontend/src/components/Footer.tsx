import React from 'react';
import { Paper } from '@mui/material';
import SystemHealthIndicator from './SystemHealthIndicator';

const Footer: React.FC = () => {
  return (
    <Paper
      component="footer"
      square
      elevation={0}
      sx={{
        py: 1.5,
        px: 3,
        backgroundColor: 'background.default',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 56,
        borderTop: 'none',
      }}
    >
      <SystemHealthIndicator 
        variant="summary" 
        showDetails={true}
        refreshInterval={15000}
      />
    </Paper>
  );
};

export default Footer;
