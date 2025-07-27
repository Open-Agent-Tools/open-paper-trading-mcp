import React, { useState } from 'react';
import {
  Container,
  Typography,
  Box,
  Card,
  CardContent,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { SwapHoriz as SwapIcon } from '@mui/icons-material';
import AccountInfo from '../components/AccountInfo';
import AccountsGrid from '../components/AccountsGrid';

const Account: React.FC = () => {
  const [switchDialogOpen, setSwitchDialogOpen] = useState(false);

  const handleSwitchAccount = (accountId: string) => {
    // TODO: Implement account switching logic
    console.log('Switching to account:', accountId);
    setSwitchDialogOpen(false);
    // This would update the global state/context with the new account
    // and potentially navigate back to dashboard
  };

  const handleOpenSwitchDialog = () => {
    setSwitchDialogOpen(true);
  };

  const handleCloseSwitchDialog = () => {
    setSwitchDialogOpen(false);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box mb={4} display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h3" component="h1" gutterBottom>
            Account Information
          </Typography>
          <Typography variant="body1" color="text.secondary">
            View your current account details and trading information.
          </Typography>
        </Box>
        
        <Button
          variant="outlined"
          startIcon={<SwapIcon />}
          onClick={handleOpenSwitchDialog}
          sx={{
            borderColor: 'primary.main',
            color: 'primary.main',
            '&:hover': {
              backgroundColor: 'primary.light',
              color: 'primary.contrastText',
            },
          }}
        >
          Switch Account
        </Button>
      </Box>

      <Card>
        <CardContent>
          <AccountInfo />
        </CardContent>
      </Card>

      {/* Switch Account Dialog */}
      <Dialog 
        open={switchDialogOpen} 
        onClose={handleCloseSwitchDialog}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Typography variant="h5">Switch Account</Typography>
          <Typography variant="body2" color="text.secondary">
            Select a different account to view and manage
          </Typography>
        </DialogTitle>
        <DialogContent>
          <AccountsGrid 
            title="Available Accounts"
            showSelectButton={true}
            onSelectAccount={handleSwitchAccount}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseSwitchDialog}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default Account;
