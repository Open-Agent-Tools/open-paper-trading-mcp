import React from 'react';
import { Paper } from '@mui/material';
import SystemHealthIndicator from './SystemHealthIndicator';

const Footer: React.FC = () => {
  return (
    <Paper
      component="footer"
      square
      variant="outlined"
      sx={{
        py: 2,
        px: 5,
        mt: 'auto',
        backgroundColor: 'background.default',
        textAlign: 'center',
      }}
    >
      <SystemHealthIndicator 
        variant="summary" 
        showDetails={true}
        refreshInterval={30000}
      />
    </Paper>
  );
};

export default Footer;
