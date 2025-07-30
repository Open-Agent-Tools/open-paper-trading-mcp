import React, { useState } from 'react';
import { Box, Grid, Stack, Tabs, Tab, Typography, Alert } from '@mui/material';
import PositionsTable from '../components/PositionsTable';
import CreateOrderForm from '../components/CreateOrderForm';
import PortfolioValue from '../components/PortfolioValue';
import CorporateEvents from '../components/CorporateEvents';
import OrderHistory from '../components/OrderHistory';
import AccountGuard from '../components/account/AccountGuard';
import ErrorBoundary from '../components/ErrorBoundary';
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
              Balance: {selectedAccount.current_balance != null && !isNaN(selectedAccount.current_balance) 
                ? selectedAccount.current_balance.toLocaleString('en-US', {
                    style: 'currency',
                    currency: 'USD',
                  })
                : '$0.00'
              }
            </Typography>
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} lg={8}>
            <Stack spacing={3}>
              <ErrorBoundary>
                <PositionsTable />
              </ErrorBoundary>
              
              {/* Additional Info Tabs */}
              <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
                  <Tab label="Recent Orders" />
                  <Tab label="Corporate Events" />
                </Tabs>
              </Box>

              {tabValue === 0 && (
                <ErrorBoundary>
                  <OrderHistory maxItems={10} />
                </ErrorBoundary>
              )}
              {tabValue === 1 && (
                <ErrorBoundary>
                  <CorporateEvents 
                    symbol="AAPL" // Would be dynamic based on selected position
                  />
                </ErrorBoundary>
              )}
            </Stack>
          </Grid>
          <Grid item xs={12} lg={4}>
            <Stack spacing={3}>
              <ErrorBoundary>
                <PortfolioValue />
              </ErrorBoundary>
              <ErrorBoundary>
                <CreateOrderForm />
              </ErrorBoundary>
            </Stack>
          </Grid>
        </Grid>
      </Box>
    </AccountGuard>
  );
};

export default Dashboard;
