import React from 'react';
import { Box, Grid, Stack } from '@mui/material';
import OrdersTable from '../components/OrdersTable';
import CreateOrderForm from '../components/CreateOrderForm';
import OrderHistory from '../components/OrderHistory';
import AccountGuard from '../components/account/AccountGuard';

const Orders: React.FC = () => {
  return (
    <AccountGuard
      fallbackMessage="Please select a trading account to view and manage your orders."
      showAccountSelector={true}
    >
      <Box sx={{ flexGrow: 1 }}>
        <Grid container spacing={3}>
          <Grid item xs={12} lg={8}>
            <Stack spacing={3}>
              <OrderHistory />
              <OrdersTable />
            </Stack>
          </Grid>
          <Grid item xs={12} lg={4}>
            <CreateOrderForm />
          </Grid>
        </Grid>
      </Box>
    </AccountGuard>
  );
};

export default Orders;
