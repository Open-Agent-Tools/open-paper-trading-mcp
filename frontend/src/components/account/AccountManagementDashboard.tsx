import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Paper,
  Tabs,
  Tab,
  Fab,
  Alert,
  Snackbar,
  Breadcrumbs,
  Link,
  useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AddIcon from '@mui/icons-material/Add';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import GridViewIcon from '@mui/icons-material/GridView';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import HomeIcon from '@mui/icons-material/Home';

import AccountCreationForm from './AccountCreationForm';
import AccountSelectionGrid from './AccountSelectionGrid';
import AccountDeletionDialog from './AccountDeletionDialog';
import { useAccountContext } from '../../contexts/AccountContext';
import type { AccountSummary } from '../../types/account';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`account-tabpanel-${index}`}
      aria-labelledby={`account-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `account-tab-${index}`,
    'aria-controls': `account-tabpanel-${index}`,
  };
}

interface AccountManagementDashboardProps {
  onAccountSelected?: (account: AccountSummary) => void;
  initialTab?: number;
}

const AccountManagementDashboard: React.FC<AccountManagementDashboardProps> = ({
  onAccountSelected,
  initialTab = 1, // Default to account selection
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // Use account context
  const { 
    selectedAccount, 
    selectAccount, 
    refreshAccounts,
    clearAccount 
  } = useAccountContext();
  
  const [activeTab, setActiveTab] = useState(initialTab);
  const [accountToDelete, setAccountToDelete] = useState<AccountSummary | null>(null);
  
  // Snackbar state
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info' | 'warning';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleAccountCreated = async (accountId: string) => {
    setSnackbar({
      open: true,
      message: `Account created successfully! ID: ${accountId}`,
      severity: 'success',
    });
    
    // Switch to selection tab and refresh accounts via context
    setActiveTab(1);
    await refreshAccounts();
  };

  const handleAccountSelected = (account: AccountSummary) => {
    // Use context to select account
    selectAccount(account);
    setSnackbar({
      open: true,
      message: `Selected account: ${account.owner} (${account.id})`,
      severity: 'info',
    });
    
    // Notify parent component
    onAccountSelected?.(account);
  };

  const handleAccountDeleted = async (accountId: string) => {
    setSnackbar({
      open: true,
      message: `Account ${accountId} has been deleted successfully`,
      severity: 'warning',
    });
    
    // Refresh accounts via context (will handle clearing selection if needed)
    await refreshAccounts();
  };

  // Removed unused handleDeleteClick function

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  return (
    <>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        {/* Breadcrumb Navigation */}
        <Breadcrumbs 
          separator={<NavigateNextIcon fontSize="small" />}
          sx={{ mb: 2 }}
        >
          <Link
            color="inherit"
            href="/"
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              textDecoration: 'none',
              '&:hover': { textDecoration: 'underline' }
            }}
          >
            <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />
            Dashboard
          </Link>
          <Typography color="text.primary" sx={{ display: 'flex', alignItems: 'center' }}>
            <AccountBalanceIcon sx={{ mr: 0.5 }} fontSize="inherit" />
            Account Management
          </Typography>
        </Breadcrumbs>

        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Typography 
            variant="h3" 
            component="h1" 
            gutterBottom 
            sx={{ 
              color: theme.palette.primary.main,
              fontWeight: 500,
              fontSize: { xs: '2rem', sm: '2.5rem', md: '3rem' }
            }}
          >
            Account Management
          </Typography>
          <Typography 
            variant="h6" 
            color="text.secondary"
            sx={{ maxWidth: 600 }}
          >
            Create, select, and manage your paper trading accounts. Each account 
            operates independently with its own virtual portfolio and transaction history.
          </Typography>
        </Box>

        {/* Selected Account Info */}
        {selectedAccount && (
          <Alert 
            severity="info" 
            sx={{ mb: 3 }}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => clearAccount()}
              >
                Clear
              </Button>
            }
          >
            <Typography variant="body2">
              <strong>Active Account:</strong> {selectedAccount.owner} ({selectedAccount.id}) - 
              Balance: {selectedAccount.current_balance.toLocaleString('en-US', {
                style: 'currency',
                currency: 'USD',
              })}
            </Typography>
          </Alert>
        )}

        {/* Main Content */}
        <Paper elevation={3} sx={{ borderRadius: 2 }}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs 
              value={activeTab} 
              onChange={handleTabChange} 
              aria-label="account management tabs"
              variant={isMobile ? "scrollable" : "standard"}
              scrollButtons={isMobile ? "auto" : false}
            >
              <Tab 
                label="Create Account" 
                icon={<PersonAddIcon />} 
                iconPosition="start"
                {...a11yProps(0)} 
              />
              <Tab 
                label="Select Account" 
                icon={<GridViewIcon />} 
                iconPosition="start"
                {...a11yProps(1)} 
              />
            </Tabs>
          </Box>

          <TabPanel value={activeTab} index={0}>
            <AccountCreationForm
              onAccountCreated={handleAccountCreated}
              onCancel={() => setActiveTab(1)}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={1}>
            <AccountSelectionGrid
              onAccountSelected={handleAccountSelected}
              onAccountDeleted={handleAccountDeleted}
              selectedAccountId={selectedAccount?.id}
            />
          </TabPanel>
        </Paper>

        {/* Floating Action Button - Mobile Only */}
        {isMobile && activeTab === 1 && (
          <Fab
            color="primary"
            aria-label="create account"
            sx={{ 
              position: 'fixed', 
              bottom: 16, 
              right: 16,
              zIndex: theme.zIndex.fab,
            }}
            onClick={() => setActiveTab(0)}
          >
            <AddIcon />
          </Fab>
        )}
      </Container>

      {/* Account Deletion Dialog */}
      <AccountDeletionDialog
        open={Boolean(accountToDelete)}
        account={accountToDelete}
        onClose={() => setAccountToDelete(null)}
        onAccountDeleted={handleAccountDeleted}
      />

      {/* Success/Error Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default AccountManagementDashboard;