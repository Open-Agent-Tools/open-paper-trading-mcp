import React, { useEffect, useState, useCallback } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { CircularProgress, Alert, Paper, Typography, Chip, Snackbar, Button, Box } from '@mui/material';
import { getOrders, cancelOrder } from '../services/apiClient';
import { useComponentLoading } from '../contexts/LoadingContext';
import type { Order } from '../types';
import CancelIcon from '@mui/icons-material/Cancel';

const OrdersTable: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const { loading, startLoading, stopLoading } = useComponentLoading('order-history');
  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: 'success' | 'error' } | null>(null);

  const fetchOrders = useCallback(async () => {
    try {
      startLoading();
      const response = await getOrders();
      if (response.success && response.orders) {
        setOrders(response.orders);
      } else {
        setError(response.message || 'Failed to fetch orders.');
      }
    } catch (err) {
      setError('Failed to fetch orders.');
      console.error(err);
    } finally {
      stopLoading();
    }
  }, [startLoading, stopLoading]);

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
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    { field: 'quantity', headerName: 'Quantity', type: 'number', width: 100 },
    { field: 'order_type', headerName: 'Order Type', width: 140 },
    { field: 'condition', headerName: 'Condition', width: 120 },
    { 
      field: 'price', 
      headerName: 'Price', 
      type: 'number', 
      width: 120, 
      valueFormatter: (params) => (params ? `$${(params as number).toFixed(2)}` : 'N/A') 
    },
    { 
      field: 'stop_price', 
      headerName: 'Stop Price', 
      type: 'number', 
      width: 120, 
      valueFormatter: (params) => (params ? `$${(params as number).toFixed(2)}` : 'N/A') 
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params: GridRenderCellParams) => {
        let color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' = 'default';
        const status = params.value as string;
        if (status === 'filled') {
          color = 'success';
        } else if (status === 'cancelled' || status === 'rejected') {
          color = 'error';
        } else if (status === 'pending' || status === 'triggered') {
          color = 'warning';
        } else if (status === 'partially_filled') {
          color = 'info';
        }
        return <Chip label={status.toUpperCase()} color={color} size="small" />;
      },
    },
    { 
      field: 'created_at', 
      headerName: 'Created', 
      width: 120,
      valueFormatter: (params) => {
        if (params) {
          return new Date(params as string).toLocaleDateString();
        }
        return 'N/A';
      }
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      renderCell: (params: GridRenderCellParams) => {
        const status = params.row.status;
        if (status !== 'pending' && status !== 'triggered') {
          return null;
        }
        return (
          <Button
            onClick={handleCancelClick(params.id as string)}
            startIcon={<CancelIcon />}
            color="error"
            size="small"
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
          pageSizeOptions={[5, 10]}
          checkboxSelection
          disableRowSelectionOnClick
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