import React from 'react';
import { Box, Grid, Stack } from '@mui/material';
import OrdersTable from '../components/OrdersTable';
import CreateOrderForm from '../components/CreateOrderForm';
import OrderHistory from '../components/OrderHistory';

const Orders: React.FC = () => {
  return (
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
  );
};

export default Orders;
