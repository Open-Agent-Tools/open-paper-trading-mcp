import React from 'react';
import { Paper, Typography, Box } from '@mui/material';

const PortfolioValue: React.FC = () => {
  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="h6" gutterBottom>
        Portfolio Value
      </Typography>
      <Box
        sx={{
          height: 200,
          backgroundColor: 'grey.200',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 1,
        }}
      >
        <Typography color="text.secondary">[Data Graphic Placeholder]</Typography>
      </Box>
    </Paper>
  );
};

export default PortfolioValue;
