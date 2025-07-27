import React from 'react';
import { Container, Typography, Box } from '@mui/material';
import AccountsGrid from '../components/AccountsGrid';

const AccountsList: React.FC = () => {
  const handleSelectAccount = (accountId: string) => {
    // TODO: Implement account switching logic
    console.log('Selected account:', accountId);
    // This could navigate to the dashboard with the selected account
    // or set the account in global state/context
  };

  return (
    <Container maxWidth={false} sx={{ py: 4 }}>
      <Box mb={4}>
        <Typography variant="h3" component="h1" gutterBottom>
          Paper Trading Accounts
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor and manage all your paper trading simulation accounts. 
          Click on any account to view detailed portfolio information and trading activity.
        </Typography>
      </Box>
      
      <AccountsGrid 
        title="All Simulation Accounts"
        showSelectButton={true}
        onSelectAccount={handleSelectAccount}
      />
    </Container>
  );
};

export default AccountsList;