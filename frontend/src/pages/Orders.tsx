import React from 'react';
import { Paper, Typography } from '@mui/material';
import OrdersTable from '../components/OrdersTable';

const Orders: React.FC = () => {
  return (
    <Paper sx={{ p: 4 }}>
      <Typography variant="h4" gutterBottom>
        Orders
      </Typography>
      <OrdersTable />
    </Paper>
  );
};

export default Orders;
