import React, { useState } from 'react';
import { Box, Grid, Stack, Tabs, Tab, Typography, Alert } from '@mui/material';
import PositionsTable from '../components/PositionsTable';
import CreateOrderForm from '../components/CreateOrderForm';
import PortfolioValue from '../components/PortfolioValue';
import CorporateEvents from '../components/CorporateEvents';
import OrderHistory from '../components/OrderHistory';
import AccountGuard from '../components/account/AccountGuard';
import { useAccountContext } from '../contexts/AccountContext';

const Dashboard: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const { selectedAccount } = useAccountContext();

  return (
    <AccountGuard
      fallbackMessage="Please select a trading account to view your dashboard and portfolio."
      showAccountSelector={true}
    >
      <Box sx={{ flexGrow: 1 }}>
        {/* Account Context Example - Show selected account info */}
        {selectedAccount && (
          <Alert 
            severity="info" 
            sx={{ mb: 3 }}
          >
            <Typography variant="body2">
              <strong>Trading as:</strong> {selectedAccount.owner} (Account: {selectedAccount.id}) - 
              Balance: {selectedAccount.current_balance.toLocaleString('en-US', {
                style: 'currency',
                currency: 'USD',
              })}
            </Typography>
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} lg={8}>
            <Stack spacing={3}>
              <PositionsTable />
              
              {/* Additional Info Tabs */}
              <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
                  <Tab label="Recent Orders" />
                  <Tab label="Corporate Events" />
                </Tabs>
              </Box>

              {tabValue === 0 && <OrderHistory maxItems={10} />}
              {tabValue === 1 && (
                <CorporateEvents 
                  symbol="AAPL" // Would be dynamic based on selected position
                />
              )}
            </Stack>
          </Grid>
          <Grid item xs={12} lg={4}>
            <Stack spacing={3}>
              <PortfolioValue />
              <CreateOrderForm />
            </Stack>
          </Grid>
        </Grid>
      </Box>
    </AccountGuard>
  );
};

export default Dashboard;
