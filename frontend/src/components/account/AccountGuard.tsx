import React from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Paper,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  CardActions,
  useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import {
  AccountBalance as AccountIcon,
  Warning as WarningIcon,
  Add as AddIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAccountContext } from '../../contexts/AccountContext';
import AccountSelector from './AccountSelector';

interface AccountGuardProps {
  children: React.ReactNode;
  fallbackMessage?: string;
  showAccountSelector?: boolean;
  redirectTo?: string;
  requireAccount?: boolean;
}

const AccountGuard: React.FC<AccountGuardProps> = ({
  children,
  fallbackMessage,
  showAccountSelector = true,
  redirectTo = '/',
  requireAccount = true,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  const {
    selectedAccount,
    availableAccounts,
    isLoading,
    isInitialized,
    error,
    refreshAccounts,
  } = useAccountContext();

  // Show loading spinner while initializing
  if (!isInitialized || isLoading) {
    return (
      <Container maxWidth="sm" sx={{ py: 8 }}>
        <Paper
          elevation={3}
          sx={{
            p: 4,
            textAlign: 'center',
            borderRadius: 2,
          }}
        >
          <CircularProgress size={48} sx={{ mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Loading Account Information
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Please wait while we retrieve your account data...
          </Typography>
        </Paper>
      </Container>
    );
  }

  // Show error state if there's an error and no accounts
  if (error && availableAccounts.length === 0) {
    return (
      <Container maxWidth="sm" sx={{ py: 8 }}>
        <Paper
          elevation={3}
          sx={{
            p: 4,
            textAlign: 'center',
            borderRadius: 2,
          }}
        >
          <WarningIcon sx={{ fontSize: 48, color: 'error.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom color="error">
            Unable to Load Accounts
          </Typography>
          <Alert severity="error" sx={{ mb: 3, textAlign: 'left' }}>
            {error}
          </Alert>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={refreshAccounts}
              disabled={isLoading}
            >
              Retry
            </Button>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => navigate(redirectTo)}
            >
              Create Account
            </Button>
          </Box>
        </Paper>
      </Container>
    );
  }

  // Show "no accounts" state if no accounts are available
  if (availableAccounts.length === 0) {
    return (
      <Container maxWidth="md" sx={{ py: 8 }}>
        <Paper
          elevation={3}
          sx={{
            p: 4,
            textAlign: 'center',
            borderRadius: 2,
          }}
        >
          <AccountIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h4" gutterBottom>
            Welcome to Open Paper Trading
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 500, mx: 'auto' }}>
            To get started with paper trading, you'll need to create your first trading account. 
            Each account operates independently with its own virtual portfolio and transaction history.
          </Typography>
          
          <Card sx={{ maxWidth: 400, mx: 'auto', mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Get Started
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Create your first paper trading account with a virtual starting balance to begin trading.
              </Typography>
            </CardContent>
            <CardActions sx={{ justifyContent: 'center', pb: 2 }}>
              <Button
                variant="contained"
                size="large"
                startIcon={<AddIcon />}
                onClick={() => navigate(redirectTo)}
                sx={{ minWidth: 200 }}
              >
                Create First Account
              </Button>
            </CardActions>
          </Card>
          
          <Typography variant="caption" color="text.secondary">
            You can create multiple accounts to test different trading strategies
          </Typography>
        </Paper>
      </Container>
    );
  }

  // Show account selection state if no account is selected but accounts exist
  if (requireAccount && !selectedAccount) {
    return (
      <Container maxWidth="md" sx={{ py: 8 }}>
        <Paper
          elevation={3}
          sx={{
            p: 4,
            textAlign: 'center',
            borderRadius: 2,
          }}
        >
          <AccountIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Select an Account
          </Typography>
          
          {error && (
            <Alert severity="warning" sx={{ mb: 3, textAlign: 'left' }}>
              {error}
            </Alert>
          )}
          
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            {fallbackMessage || 
              'Please select a trading account to continue. You can switch between accounts at any time.'}
          </Typography>
          
          <Box sx={{ mb: 4 }}>
            {showAccountSelector && (
              <AccountSelector 
                variant={isMobile ? 'chip' : 'button'}
                showBalance={true}
                showCreateOption={true}
              />
            )}
          </Box>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Available Accounts: {availableAccounts.length}
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => navigate(redirectTo)}
            >
              Create New Account
            </Button>
            <Button
              variant="text"
              startIcon={<RefreshIcon />}
              onClick={refreshAccounts}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </Box>
        </Paper>
      </Container>
    );
  }

  // Account is selected or not required - render children
  return <>{children}</>;
};

export default AccountGuard;