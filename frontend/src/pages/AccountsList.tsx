import React, { useState } from 'react';
import { Container, Typography, Box, Button } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import AccountsGrid from '../components/AccountsGrid';
import CreateAccountModal from '../components/CreateAccountModal';
import { useAccountContext } from '../contexts/AccountContext';

const AccountsList: React.FC = () => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const navigate = useNavigate();
  const { availableAccounts, selectAccount, refreshAccounts } = useAccountContext();

  const handleSelectAccount = (accountId: string) => {
    // Find the account in the available accounts and select it
    const account = availableAccounts.find(acc => acc.id === accountId);
    if (account) {
      selectAccount(account);
      // Navigate to dashboard after selecting account
      navigate('/dashboard');
    } else {
      console.error('Account not found:', accountId);
    }
  };

  const handleCreateAccount = () => {
    setIsCreateModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsCreateModalOpen(false);
  };

  const handleAccountCreated = async () => {
    // Trigger a refresh of the accounts grid and context
    setRefreshTrigger(prev => prev + 1);
    await refreshAccounts();
  };

  return (
    <Container maxWidth={false} sx={{ py: 4 }}>
      <Box mb={4}>
        <Typography variant="h3" component="h1" gutterBottom>
          Paper Trading Accounts
        </Typography>
        <Box 
          display="flex" 
          flexDirection={{ xs: 'column', md: 'row' }}
          justifyContent="space-between" 
          alignItems={{ xs: 'stretch', md: 'center' }}
          gap={2}
          mb={2}
        >
          <Typography variant="body1" color="text.secondary">
            Monitor and manage all your paper trading simulation accounts. 
            Click on any account to view detailed portfolio information and trading activity.
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateAccount}
            sx={{
              minWidth: 160,
              alignSelf: { xs: 'flex-start', md: 'auto' },
              backgroundColor: 'primary.main',
              '&:hover': {
                backgroundColor: 'primary.dark',
              },
            }}
          >
            Create Account
          </Button>
        </Box>
      </Box>
      
      <AccountsGrid 
        title="All Simulation Accounts"
        showSelectButton={true}
        onSelectAccount={handleSelectAccount}
        refreshTrigger={refreshTrigger}
      />

      <CreateAccountModal
        open={isCreateModalOpen}
        onClose={handleCloseModal}
        onAccountCreated={handleAccountCreated}
      />
    </Container>
  );
};

export default AccountsList;