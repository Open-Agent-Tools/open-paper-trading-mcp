import React, { useEffect, useState, useCallback } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef, GridValueFormatterParams, GridRenderCellParams } from '@mui/x-data-grid';
import { CircularProgress, Alert, Paper, Typography, Chip, Snackbar, Button, Box } from '@mui/material';
import { getOrders, cancelOrder } from '../services/apiClient';
import type { Order } from '../types';
import CancelIcon from '@mui/icons-material/Cancel';

const OrdersTable: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: 'success' | 'error' } | null>(null);

  const fetchOrders = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getOrders();
      setOrders(data);
    } catch (err) {
      setError('Failed to fetch orders.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleCancelClick = useCallback(
    (id: string) => async () => {
      try {
        await cancelOrder(id);
        setSnackbar({ open: true, message: 'Order cancelled successfully!', severity: 'success' });
        fetchOrders();
      } catch (error) {
        setSnackbar({ open: true, message: 'Failed to cancel order.', severity: 'error' });
      }
    },
    [fetchOrders],
  );

  const columns: GridColDef[] = [
    { field: 'symbol', headerName: 'Symbol', width: 150 },
    { field: 'quantity', headerName: 'Quantity', type: 'number', width: 150 },
    { field: 'type', headerName: 'Type', width: 150 },
    { field: 'price', headerName: 'Price', type: 'number', width: 150, valueFormatter: (params: GridValueFormatterParams) => (params.value ? `$${(params.value as number).toLocaleString()}` : 'N/A') },
    {
      field: 'status',
      headerName: 'Status',
      width: 150,
      renderCell: (params: GridRenderCellParams) => {
        let color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' = 'default';
        if (params.value === 'FILLED') {
          color = 'success';
        } else if (params.value === 'CANCELLED') {
          color = 'error';
        } else if (params.value === 'PENDING') {
          color = 'warning';
        }
        return <Chip label={params.value} color={color} />;
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 150,
      renderCell: (params: GridRenderCellParams) => {
        if (params.row.status !== 'PENDING') {
          return null;
        }
        return (
          <Button
            onClick={handleCancelClick(params.id as string)}
            startIcon={<CancelIcon />}
            color="error"
          >
            Cancel
          </Button>
        );
      },
    },
  ];

  if (loading) {
    return <CircularProgress />;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <>
      <Paper style={{ height: 400, width: '100%' }}>
        <Typography variant="h6" gutterBottom sx={{ p: 2 }}>
          Order History
        </Typography>
        <Box sx={{ height: 350, width: '100%' }}>
        <DataGrid
          rows={orders}
          columns={columns}
          rowsPerPageOptions={[5, 10]}
          checkboxSelection
          disableSelectionOnClick
        />
        </Box>
      </Paper>
      {snackbar && (
        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={() => setSnackbar(null)}
        >
          <Alert onClose={() => setSnackbar(null)} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      )}
    </>
  );
};

export default OrdersTable;