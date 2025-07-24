import React from 'react';
import { Paper, Typography, Box } from '@mui/material';

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
      <Typography variant="body2" color="text.secondary">
        API Status: <Box component="span" sx={{ color: 'success.main' }}>●</Box> Online | Market: Open
      </Typography>
    </Paper>
  );
};

export default Footer;
