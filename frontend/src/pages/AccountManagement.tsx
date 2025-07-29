import React, { useState } from 'react';
import { 
  Box, 
  Container, 
  Typography, 
  Alert,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  Divider
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SecurityIcon from '@mui/icons-material/Security';
import SpeedIcon from '@mui/icons-material/Speed';
import BarChartIcon from '@mui/icons-material/BarChart';
import { AccountManagementDashboard } from '../components/account';
import { useAccountManagement } from '../hooks/useAccountManagement';
import type { AccountSummary } from '../types/account';

const AccountManagementPage: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount, summary, error } = useAccountManagement();
  const [showOverview, setShowOverview] = useState(true);

  const handleAccountSelected = (account: AccountSummary) => {
    // This could navigate to the trading dashboard or update global state
    console.log('Account selected:', account);
  };

  const formatCurrency = (amount: number): string => {
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  };

  const features = [
    {
      icon: <SecurityIcon fontSize="large" color="primary" />,
      title: 'Risk-Free Trading',
      description: 'Practice trading strategies with virtual money - no real financial risk.'
    },
    {
      icon: <SpeedIcon fontSize="large" color="primary" />,
      title: 'Real-Time Data',
      description: 'Access live market data and execute trades instantly in our simulated environment.'
    },
    {
      icon: <BarChartIcon fontSize="large" color="primary" />,
      title: 'Advanced Analytics',
      description: 'Track performance with detailed portfolio analytics and risk metrics.'
    },
    {
      icon: <TrendingUpIcon fontSize="large" color="primary" />,
      title: 'Portfolio Tracking',
      description: 'Monitor your virtual investments with comprehensive portfolio management tools.'
    }
  ];

  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: theme.palette.background.default }}>
      {/* Overview Section */}
      {showOverview && (
        <Box sx={{ backgroundColor: theme.palette.primary.main, color: 'white', py: 6 }}>
          <Container maxWidth="lg">
            <Grid container spacing={4} alignItems="center">
              <Grid item xs={12} md={8}>
                <Typography variant="h2" component="h1" gutterBottom sx={{ 
                  fontWeight: 300,
                  fontSize: { xs: '2.5rem', sm: '3rem', md: '3.5rem' }
                }}>
                  Paper Trading Platform
                </Typography>
                <Typography variant="h5" sx={{ mb: 3, opacity: 0.9 }}>
                  Master the markets with zero risk. Trade virtual funds using real market data.
                </Typography>
                
                {summary && (
                  <Grid container spacing={2} sx={{ mt: 2 }}>
                    <Grid item>
                      <Chip 
                        icon={<AccountBalanceIcon />}
                        label={`${summary.total_count} Active Accounts`}
                        variant="outlined"
                        sx={{ 
                          color: 'white', 
                          borderColor: 'rgba(255, 255, 255, 0.5)',
                          '& .MuiChip-icon': { color: 'white' }
                        }}
                      />
                    </Grid>
                    <Grid item>
                      <Chip 
                        icon={<TrendingUpIcon />}
                        label={`${formatCurrency(summary.total_current_balance)} Total Portfolio`}
                        variant="outlined"
                        sx={{ 
                          color: 'white', 
                          borderColor: 'rgba(255, 255, 255, 0.5)',
                          '& .MuiChip-icon': { color: 'white' }
                        }}
                      />
                    </Grid>
                  </Grid>
                )}
              </Grid>
              
              <Grid item xs={12} md={4} sx={{ textAlign: 'center' }}>
                <AccountBalanceIcon sx={{ fontSize: 120, opacity: 0.7 }} />
              </Grid>
            </Grid>
          </Container>
        </Box>
      )}

      {/* Features Section */}
      {showOverview && (
        <Container maxWidth="lg" sx={{ py: 6 }}>
          <Typography variant="h3" component="h2" align="center" gutterBottom sx={{ 
            color: theme.palette.primary.main,
            fontWeight: 500,
            mb: 4
          }}>
            Why Choose Paper Trading?
          </Typography>
          
          <Grid container spacing={4}>
            {features.map((feature, index) => (
              <Grid item xs={12} sm={6} md={3} key={index}>
                <Card elevation={2} sx={{ 
                  height: '100%', 
                  textAlign: 'center',
                  transition: 'transform 0.2s ease-in-out',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    elevation: 4
                  }
                }}>
                  <CardContent sx={{ p: 3 }}>
                    <Box sx={{ mb: 2 }}>
                      {feature.icon}
                    </Box>
                    <Typography variant="h6" component="h3" gutterBottom sx={{ fontWeight: 600 }}>
                      {feature.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {feature.description}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
          
          <Box sx={{ textAlign: 'center', mt: 6 }}>
            <Button
              variant="contained"
              size="large"
              onClick={() => setShowOverview(false)}
              sx={{ 
                px: 4,
                py: 1.5,
                fontSize: '1.1rem',
                fontWeight: 600
              }}
            >
              Get Started Now
            </Button>
          </Box>
        </Container>
      )}

      {/* Divider */}
      {showOverview && <Divider />}

      {/* Error Alert */}
      {error && (
        <Container maxWidth="lg" sx={{ pt: 3 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        </Container>
      )}

      {/* Selected Account Alert */}
      {selectedAccount && (
        <Container maxWidth="lg" sx={{ pt: showOverview ? 3 : 0 }}>
          <Alert 
            severity="success" 
            sx={{ mb: 2 }}
            action={
              <Button color="inherit" size="small">
                Go to Trading
              </Button>
            }
          >
            <Typography variant="body2">
              <strong>Active Account:</strong> {selectedAccount.owner} ({selectedAccount.id}) - 
              Balance: {formatCurrency(selectedAccount.current_balance)}
            </Typography>
          </Alert>
        </Container>
      )}

      {/* Main Account Management Dashboard */}
      <AccountManagementDashboard
        onAccountSelected={handleAccountSelected}
        initialTab={summary?.total_count === 0 ? 0 : 1}
      />

      {/* Footer */}
      <Box sx={{ 
        backgroundColor: theme.palette.grey[100], 
        py: 4, 
        mt: 6,
        borderTop: `1px solid ${theme.palette.divider}`
      }}>
        <Container maxWidth="lg">
          <Typography variant="body2" color="text.secondary" align="center">
            © 2025 Open Paper Trading Platform. Practice trading with virtual funds using real market data.
            All trading activity is simulated and involves no real money.
          </Typography>
        </Container>
      </Box>
    </Box>
  );
};

export default AccountManagementPage;