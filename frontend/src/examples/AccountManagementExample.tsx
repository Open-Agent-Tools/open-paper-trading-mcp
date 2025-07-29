import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Paper,
  Grid,
  Card,
  CardContent,
  Divider,
  Alert,
  Chip,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TradingViewIcon from '@mui/icons-material/TrendingUp';
import SettingsIcon from '@mui/icons-material/Settings';

// Import all account management components
import {
  AccountCreationForm,
  AccountSelectionGrid,
  AccountDeletionDialog,
  AccountManagementDashboard,
} from '../components/account';

// Import the custom hook
import { useAccountManagement } from '../hooks/useAccountManagement';

// Import types
import type { AccountSummary } from '../types/account';

/**
 * Complete example showing how to integrate the account management system
 * into your application. This demonstrates all the components working together.
 */
const AccountManagementExample: React.FC = () => {
  const theme = useTheme();
  
  // Use the account management hook for state management
  const {
    accounts,
    selectedAccount,
    error,
    summary,
    loadAccounts,
    selectAccount,
    removeAccount,
    clearSelection,
    clearError,
  } = useAccountManagement();

  // Local state for UI components
  const [currentView, setCurrentView] = useState<'dashboard' | 'individual' | 'trading'>('dashboard');
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [accountToDelete, setAccountToDelete] = useState<AccountSummary | null>(null);

  // Handler for account selection
  const handleAccountSelected = (account: AccountSummary) => {
    selectAccount(account);
    
    // Example: Navigate to trading view or update global state
    console.log('Account selected for trading:', account);
    
    // You could navigate here:
    // navigate(`/trading/${account.id}`);
    
    // Or update global state:
    // dispatch(setActiveAccount(account));
    
    setCurrentView('trading');
  };

  // Handler for account creation
  const handleAccountCreated = async (accountId: string) => {
    console.log('New account created:', accountId);
    
    // Optionally select the newly created account
    const newAccount = accounts.find(acc => acc.id === accountId);
    if (newAccount) {
      selectAccount(newAccount);
    }
    
    // Refresh the accounts list
    await loadAccounts();
  };

  // Handler for account deletion
  const handleDeleteRequest = (account: AccountSummary) => {
    setAccountToDelete(account);
    setShowDeleteDialog(true);
  };

  const handleAccountDeleted = async (accountId: string) => {
    try {
      await removeAccount(accountId);
      setShowDeleteDialog(false);
      setAccountToDelete(null);
      
      // If we deleted the selected account, clear selection
      if (selectedAccount?.id === accountId) {
        clearSelection();
        setCurrentView('dashboard');
      }
    } catch (error) {
      console.error('Failed to delete account:', error);
    }
  };

  // Format currency helper
  const formatCurrency = (amount: number): string => {
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  // Render different views based on current state
  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <AccountManagementDashboard
            onAccountSelected={handleAccountSelected}
            initialTab={accounts.length === 0 ? 0 : 1}
          />
        );

      case 'individual':
        return (
          <Container maxWidth="lg">
            <Box sx={{ mb: 4 }}>
              <Button 
                onClick={() => setCurrentView('dashboard')}
                sx={{ mb: 2 }}
              >
                ← Back to Dashboard
              </Button>
            </Box>
            
            <Grid container spacing={4}>
              <Grid item xs={12} md={6}>
                <Paper elevation={3} sx={{ p: 3 }}>
                  <Typography variant="h5" gutterBottom>
                    Create New Account
                  </Typography>
                  <AccountCreationForm
                    onAccountCreated={handleAccountCreated}
                    onCancel={() => setCurrentView('dashboard')}
                  />
                </Paper>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Paper elevation={3} sx={{ p: 3 }}>
                  <Typography variant="h5" gutterBottom>
                    Account Selection
                  </Typography>
                  <AccountSelectionGrid
                    onAccountSelected={handleAccountSelected}
                    onAccountDeleted={(accountId: string) => {
                      const account = accounts.find(acc => acc.id === accountId);
                      if (account) {
                        handleDeleteRequest(account);
                      }
                    }}
                    selectedAccountId={selectedAccount?.id}
                  />
                </Paper>
              </Grid>
            </Grid>
          </Container>
        );

      case 'trading':
        return (
          <Container maxWidth="lg">
            <Box sx={{ mb: 4 }}>
              <Button 
                onClick={() => setCurrentView('dashboard')}
                sx={{ mb: 2 }}
              >
                ← Back to Account Management
              </Button>
            </Box>
            
            {selectedAccount && (
              <Alert severity="success" sx={{ mb: 3 }}>
                <Typography variant="body2">
                  <strong>Trading with Account:</strong> {selectedAccount.owner} ({selectedAccount.id})
                  <br />
                  <strong>Available Balance:</strong> {formatCurrency(selectedAccount.current_balance)}
                </Typography>
              </Alert>
            )}
            
            <Card elevation={4}>
              <CardContent sx={{ p: 4, textAlign: 'center' }}>
                <TradingViewIcon sx={{ fontSize: 80, color: theme.palette.primary.main, mb: 2 }} />
                <Typography variant="h4" gutterBottom>
                  Trading Dashboard
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                  This is where your trading interface would go.
                  You can now place orders, view positions, and manage your portfolio.
                </Typography>
                
                {selectedAccount && (
                  <Grid container spacing={2} justifyContent="center">
                    <Grid item>
                      <Chip
                        icon={<AccountBalanceIcon />}
                        label={`Balance: ${formatCurrency(selectedAccount.current_balance)}`}
                        color="primary"
                        variant="outlined"
                      />
                    </Grid>
                    <Grid item>
                      <Chip
                        label={`P&L: ${selectedAccount.balance_change >= 0 ? '+' : ''}${formatCurrency(selectedAccount.balance_change)}`}
                        color={selectedAccount.balance_change >= 0 ? 'success' : 'error'}
                        variant="outlined"
                      />
                    </Grid>
                  </Grid>
                )}
              </CardContent>
            </Card>
          </Container>
        );

      default:
        return null;
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: theme.palette.background.default }}>
      {/* Header */}
      <Box sx={{ backgroundColor: theme.palette.primary.main, color: 'white', py: 3 }}>
        <Container maxWidth="lg">
          <Grid container justifyContent="space-between" alignItems="center">
            <Grid item>
              <Typography variant="h4" component="h1">
                Open Paper Trading - Account Management Example
              </Typography>
              <Typography variant="body1" sx={{ opacity: 0.9 }}>
                Complete demonstration of account management components
              </Typography>
            </Grid>
            <Grid item>
              <Button
                color="inherit"
                variant="outlined"
                startIcon={<SettingsIcon />}
                onClick={() => setCurrentView(currentView === 'individual' ? 'dashboard' : 'individual')}
                sx={{ 
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                  '&:hover': { borderColor: 'white' }
                }}
              >
                {currentView === 'individual' ? 'Integrated View' : 'Individual Components'}
              </Button>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Summary Stats */}
      {summary && (
        <Box sx={{ backgroundColor: theme.palette.background.paper, py: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Container maxWidth="lg">
            <Grid container spacing={3} alignItems="center">
              <Grid item>
                <Typography variant="body2" color="text.secondary">
                  Total Accounts
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  {summary.total_count}
                </Typography>
              </Grid>
              <Grid item>
                <Typography variant="body2" color="text.secondary">
                  Total Portfolio Value
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  {formatCurrency(summary.total_current_balance)}
                </Typography>
              </Grid>
              <Grid item>
                <Typography variant="body2" color="text.secondary">
                  Total P&L
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    fontWeight: 600,
                    color: summary.total_balance_change >= 0 
                      ? theme.palette.success.main 
                      : theme.palette.error.main
                  }}
                >
                  {summary.total_balance_change >= 0 ? '+' : ''}{formatCurrency(summary.total_balance_change)}
                </Typography>
              </Grid>
              {selectedAccount && (
                <>
                  <Grid item>
                    <Divider orientation="vertical" flexItem />
                  </Grid>
                  <Grid item>
                    <Typography variant="body2" color="text.secondary">
                      Active Account
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>
                      {selectedAccount.owner} ({selectedAccount.id})
                    </Typography>
                  </Grid>
                </>
              )}
            </Grid>
          </Container>
        </Box>
      )}

      {/* Error Display */}
      {error && (
        <Container maxWidth="lg" sx={{ pt: 3 }}>
          <Alert 
            severity="error" 
            onClose={clearError}
            action={
              <Button color="inherit" size="small" onClick={loadAccounts}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </Container>
      )}

      {/* Main Content */}
      <Box sx={{ py: 4 }}>
        {renderCurrentView()}
      </Box>

      {/* Account Deletion Dialog */}
      <AccountDeletionDialog
        open={showDeleteDialog}
        account={accountToDelete}
        onClose={() => {
          setShowDeleteDialog(false);
          setAccountToDelete(null);
        }}
        onAccountDeleted={handleAccountDeleted}
      />

      {/* Footer */}
      <Box sx={{ 
        backgroundColor: theme.palette.grey[100], 
        py: 3, 
        mt: 6,
        borderTop: 1, 
        borderColor: 'divider' 
      }}>
        <Container maxWidth="lg">
          <Typography variant="body2" color="text.secondary" align="center">
            This example demonstrates the complete account management system with all components integrated.
            <br />
            In a real application, account selection would navigate to your trading interface.
          </Typography>
        </Container>
      </Box>
    </Box>
  );
};

export default AccountManagementExample;