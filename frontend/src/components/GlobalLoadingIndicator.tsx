import React from 'react';
import {
  Backdrop,
  Box,
  CircularProgress,
  Typography,
  LinearProgress,
  Fade,
  Paper,
  Chip,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useLoading } from '../contexts/LoadingContext';

interface GlobalLoadingIndicatorProps {
  variant?: 'backdrop' | 'topbar' | 'compact';
  showDetails?: boolean;
}

const GlobalLoadingIndicator: React.FC<GlobalLoadingIndicatorProps> = ({
  variant = 'topbar',
  showDetails = false
}) => {
  const theme = useTheme();
  const { isAnyLoading, getLoadingKeys } = useLoading();
  const isLoading = isAnyLoading();
  const loadingKeys = getLoadingKeys();

  // Format loading key to human readable text
  const formatLoadingKey = (key: string): string => {
    const keyMap: { [key: string]: string } = {
      'stock-quote': 'Stock Quote',
      'options-chain': 'Options Chain',
      'price-history': 'Price History',
      'portfolio-data': 'Portfolio Data',
      'market-data': 'Market Data',
      'order-submission': 'Order Submission',
      'account-data': 'Account Data',
      'analyst-ratings': 'Analyst Ratings',
      'company-info': 'Company Info',
      'order-history': 'Order History',
      'positions': 'Positions',
      'account-balance': 'Account Balance',
      'stock-search': 'Stock Search',
      'options-search': 'Options Search',
      'bulk-operations': 'Bulk Operations',
      'order-modification': 'Order Modification'
    };
    
    return keyMap[key] || key.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  if (!isLoading) {
    return null;
  }

  if (variant === 'backdrop') {
    return (
      <Backdrop
        sx={{
          color: '#fff',
          zIndex: theme.zIndex.drawer + 1,
          backgroundColor: 'rgba(0, 0, 0, 0.7)'
        }}
        open={isLoading}
      >
        <Box textAlign="center">
          <CircularProgress color="inherit" size={60} />
          <Typography variant="h6" sx={{ mt: 2 }}>
            Loading...
          </Typography>
          {showDetails && loadingKeys.length > 0 && (
            <Box sx={{ mt: 2, maxWidth: 400 }}>
              {loadingKeys.map((key) => (
                <Chip
                  key={key}
                  label={formatLoadingKey(key)}
                  size="small"
                  sx={{ 
                    margin: 0.5,
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    color: 'white'
                  }}
                />
              ))}
            </Box>
          )}
        </Box>
      </Backdrop>
    );
  }

  if (variant === 'compact') {
    return (
      <Fade in={isLoading}>
        <Box
          sx={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            zIndex: theme.zIndex.fab
          }}
        >
          <Paper
            elevation={6}
            sx={{
              p: 2,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
              borderRadius: 2
            }}
          >
            <CircularProgress size={20} sx={{ color: 'inherit' }} />
            <Typography variant="body2">
              Loading {loadingKeys.length} item{loadingKeys.length !== 1 ? 's' : ''}...
            </Typography>
          </Paper>
        </Box>
      </Fade>
    );
  }

  // Default: topbar variant
  return (
    <Fade in={isLoading}>
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: theme.zIndex.appBar + 1,
          backgroundColor: theme.palette.primary.main,
          color: theme.palette.primary.contrastText
        }}
      >
        <LinearProgress
          sx={{
            height: 3,
            backgroundColor: 'rgba(255, 255, 255, 0.3)',
            '& .MuiLinearProgress-bar': {
              backgroundColor: theme.palette.primary.contrastText
            }
          }}
        />
        <Box
          sx={{
            px: 2,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            minHeight: 40
          }}
        >
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={16} sx={{ color: 'inherit' }} />
            <Typography variant="body2">
              Loading...
            </Typography>
          </Box>
          
          {showDetails && loadingKeys.length > 0 && (
            <Box display="flex" gap={0.5} flexWrap="wrap" sx={{ maxWidth: '60%' }}>
              {loadingKeys.slice(0, 3).map((key) => (
                <Chip
                  key={key}
                  label={formatLoadingKey(key)}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.7rem',
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    color: 'inherit',
                    '& .MuiChip-label': {
                      px: 1
                    }
                  }}
                />
              ))}
              {loadingKeys.length > 3 && (
                <Chip
                  label={`+${loadingKeys.length - 3} more`}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.7rem',
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    color: 'inherit',
                    '& .MuiChip-label': {
                      px: 1
                    }
                  }}
                />
              )}
            </Box>
          )}
        </Box>
      </Box>
    </Fade>
  );
};

export default GlobalLoadingIndicator;