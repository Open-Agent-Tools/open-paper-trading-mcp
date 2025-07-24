import React from 'react';
import { Box, Grid, Stack } from '@mui/material';
import PositionsTable from '../components/PositionsTable';
import CreateOrderForm from '../components/CreateOrderForm';
import PortfolioValue from '../components/PortfolioValue';

const Dashboard: React.FC = () => {
  return (
    <Box sx={{ flexGrow: 1 }}>
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <PositionsTable />
        </Grid>
        <Grid item xs={12} md={4}>
          <Stack spacing={3}>
            <PortfolioValue />
            <CreateOrderForm />
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
