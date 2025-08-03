import React from 'react';
import { Button, Box, Typography, Paper } from '@mui/material';
import { LoadingProvider, useComponentLoading } from '../contexts/LoadingContext';
import GlobalLoadingIndicator from '../components/GlobalLoadingIndicator';

const TestComponent: React.FC<{ name: string }> = ({ name }) => {
  const { loading, startLoading, stopLoading } = useComponentLoading(name);

  const simulateLoading = () => {
    startLoading();
    setTimeout(() => {
      stopLoading();
    }, 3000);
  };

  return (
    <Paper sx={{ p: 2, m: 1 }}>
      <Typography variant="h6">{name} Component</Typography>
      <Typography variant="body2" color={loading ? 'primary' : 'text.secondary'}>
        Status: {loading ? 'Loading...' : 'Idle'}
      </Typography>
      <Button 
        variant="contained" 
        onClick={simulateLoading}
        disabled={loading}
        sx={{ mt: 1 }}
      >
        Simulate Loading
      </Button>
    </Paper>
  );
};

const LoadingIndicatorTest: React.FC = () => {
  return (
    <LoadingProvider>
      <Box sx={{ p: 2 }}>
        <Typography variant="h4" gutterBottom>
          Global Loading Indicator Test
        </Typography>
        
        <GlobalLoadingIndicator variant="topbar" showDetails={true} />
        
        <Box sx={{ mt: 5 }}>
          <Typography variant="h6" gutterBottom>
            Test Components (Click buttons to simulate loading)
          </Typography>
          
          <Box display="flex" flexWrap="wrap">
            <TestComponent name="stock-quote" />
            <TestComponent name="options-chain" />
            <TestComponent name="price-history" />
            <TestComponent name="portfolio-data" />
            <TestComponent name="order-submission" />
            <TestComponent name="market-data" />
          </Box>
        </Box>
        
        <Box sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Alternative Loading Indicator Variants
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle1">Compact Variant:</Typography>
            <GlobalLoadingIndicator variant="compact" />
          </Box>
          
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle1">Backdrop Variant (uncomment to test):</Typography>
            {/* <GlobalLoadingIndicator variant="backdrop" showDetails={true} /> */}
          </Box>
        </Box>
      </Box>
    </LoadingProvider>
  );
};

export default LoadingIndicatorTest;