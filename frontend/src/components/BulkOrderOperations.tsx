import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Alert,
  CircularProgress,
  IconButton,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  useTheme,
} from '@mui/material';
import {
  Cancel as CancelIcon,
  Refresh as RefreshIcon,
  SelectAll as SelectAllIcon,
  ClearAll as ClearAllIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useAccountContext } from '../contexts/AccountContext';
import { getOrders, cancelOrder } from '../services/apiClient';
import type { Order } from '../types';
import axios from 'axios';

interface BulkOperationResult {
  success: boolean;
  cancelled_count?: number;
  cancelled_orders?: string[];
  message: string;
}

interface BulkOrderOperationsProps {
  onOrdersModified?: () => void;
}

const BulkOrderOperations: React.FC<BulkOrderOperationsProps> = ({ onOrdersModified }) => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrders, setSelectedOrders] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [showBulkDialog, setShowBulkDialog] = useState(false);
  const [bulkOperation, setBulkOperation] = useState<'cancel-selected' | 'cancel-all-stocks' | 'cancel-all-options' | ''>('');
  const [operationResult, setOperationResult] = useState<BulkOperationResult | null>(null);

  const fetchOrders = async () => {
    if (!selectedAccount) {
      setOrders([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getOrders(selectedAccount.id);
      
      if (response.success) {
        setOrders(response.orders || []);
      } else {
        setError('Failed to load orders');
      }
    } catch (err) {
      setError('Failed to load orders');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = () => {
    const cancellableOrders = filteredOrders.filter(order => 
      order.status === 'pending' || order.status === 'triggered'
    );
    
    if (selectedOrders.size === cancellableOrders.length) {
      setSelectedOrders(new Set());
    } else {
      setSelectedOrders(new Set(cancellableOrders.map(order => order.id)));
    }
  };

  const handleOrderSelect = (orderId: string) => {
    const newSelected = new Set(selectedOrders);
    if (newSelected.has(orderId)) {
      newSelected.delete(orderId);
    } else {
      newSelected.add(orderId);
    }
    setSelectedOrders(newSelected);
  };

  const executeBulkOperation = async () => {
    if (!selectedAccount || !bulkOperation) return;

    setLoading(true);
    setError(null);
    setOperationResult(null);

    try {
      let response;
      const apiClient = axios.create({ baseURL: '/api/v1/trading' });

      switch (bulkOperation) {
        case 'cancel-selected':
          // Cancel individual selected orders
          const cancelPromises = Array.from(selectedOrders).map(orderId => 
            cancelOrder(orderId)
          );
          const results = await Promise.allSettled(cancelPromises);
          const successCount = results.filter(r => r.status === 'fulfilled').length;
          
          setOperationResult({
            success: successCount > 0,
            cancelled_count: successCount,
            message: `Successfully cancelled ${successCount} of ${selectedOrders.size} selected orders`
          });
          break;

        case 'cancel-all-stocks':
          response = await apiClient.delete('/orders/stocks/all', {
            params: { account_id: selectedAccount.id }
          });
          setOperationResult(response.data);
          break;

        case 'cancel-all-options':
          response = await apiClient.delete('/orders/options/all', {
            params: { account_id: selectedAccount.id }
          });
          setOperationResult(response.data);
          break;

        default:
          setError('Invalid bulk operation');
          return;
      }

      // Refresh orders after operation
      await fetchOrders();
      setSelectedOrders(new Set());
      
    } catch (err) {
      setError('Failed to execute bulk operation');
      console.error(err);
    } finally {
      setLoading(false);
      setShowBulkDialog(false);
      setBulkOperation('');
      // Refresh orders list and notify parent component
      fetchOrders();
      onOrdersModified?.();
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [selectedAccount]);

  const filteredOrders = orders.filter(order => {
    if (filterStatus === 'all') return true;
    return order.status === filterStatus;
  });

  const cancellableOrders = filteredOrders.filter(order => 
    order.status === 'pending' || order.status === 'triggered'
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'filled': return theme.palette.success.main;
      case 'cancelled': return theme.palette.error.main;
      case 'pending': return theme.palette.warning.main;
      case 'triggered': return theme.palette.info.main;
      case 'rejected': return theme.palette.error.main;
      default: return theme.palette.text.secondary;
    }
  };

  const formatCurrency = (value: number | undefined) => {
    if (!value) return 'N/A';
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    });
  };

  const getBulkOperationDescription = (operation: string) => {
    switch (operation) {
      case 'cancel-selected':
        return `Cancel ${selectedOrders.size} selected orders`;
      case 'cancel-all-stocks':
        return 'Cancel all pending stock orders';
      case 'cancel-all-options':
        return 'Cancel all pending options orders';
      default:
        return '';
    }
  };

  if (loading && orders.length === 0) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error && !operationResult) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <CancelIcon color="primary" />
              <Typography variant="h6">Bulk Order Operations</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchOrders} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!selectedAccount) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
          <Typography color="text.secondary">Select an account to manage orders</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <CancelIcon color="primary" />
              <Typography variant="h6">Bulk Order Operations</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchOrders} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
          subheader={
            <Typography variant="body2" color="text.secondary">
              Manage multiple orders with bulk operations
            </Typography>
          }
        />
        <CardContent>
          {/* Operation Result */}
          {operationResult && (
            <Alert 
              severity={operationResult.success ? 'success' : 'error'} 
              sx={{ mb: 2 }}
              onClose={() => setOperationResult(null)}
            >
              {operationResult.message}
              {operationResult.cancelled_count && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Orders cancelled: {operationResult.cancelled_count}
                </Typography>
              )}
            </Alert>
          )}

          {/* Controls */}
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Box display="flex" alignItems="center" gap={2}>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Filter Status</InputLabel>
                <Select
                  value={filterStatus}
                  label="Filter Status"
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <MenuItem value="all">All Orders</MenuItem>
                  <MenuItem value="pending">Pending</MenuItem>
                  <MenuItem value="triggered">Triggered</MenuItem>
                  <MenuItem value="filled">Filled</MenuItem>
                  <MenuItem value="cancelled">Cancelled</MenuItem>
                </Select>
              </FormControl>
              
              <Button
                size="small"
                startIcon={selectedOrders.size === cancellableOrders.length ? <ClearAllIcon /> : <SelectAllIcon />}
                onClick={handleSelectAll}
                disabled={cancellableOrders.length === 0}
              >
                {selectedOrders.size === cancellableOrders.length ? 'Clear All' : 'Select All'}
              </Button>
            </Box>

            <Box display="flex" alignItems="center" gap={1}>
              {selectedOrders.size > 0 && (
                <Chip 
                  label={`${selectedOrders.size} selected`} 
                  size="small" 
                  color="primary" 
                />
              )}
              
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  setBulkOperation('cancel-selected');
                  setShowBulkDialog(true);
                }}
                disabled={selectedOrders.size === 0}
              >
                Cancel Selected
              </Button>
              
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  setBulkOperation('cancel-all-stocks');
                  setShowBulkDialog(true);
                }}
              >
                Cancel All Stocks
              </Button>
              
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  setBulkOperation('cancel-all-options');
                  setShowBulkDialog(true);
                }}
              >
                Cancel All Options
              </Button>
            </Box>
          </Box>

          {/* Orders Table */}
          {filteredOrders.length > 0 ? (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox">
                      <Checkbox
                        indeterminate={selectedOrders.size > 0 && selectedOrders.size < cancellableOrders.length}
                        checked={cancellableOrders.length > 0 && selectedOrders.size === cancellableOrders.length}
                        onChange={handleSelectAll}
                        disabled={cancellableOrders.length === 0}
                      />
                    </TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell align="right">Quantity</TableCell>
                    <TableCell align="right">Price</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Created</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredOrders.map((order) => {
                    const isCancellable = order.status === 'pending' || order.status === 'triggered';
                    const isSelected = selectedOrders.has(order.id);
                    
                    return (
                      <TableRow 
                        key={order.id}
                        hover
                        selected={isSelected}
                      >
                        <TableCell padding="checkbox">
                          <Checkbox
                            checked={isSelected}
                            onChange={() => handleOrderSelect(order.id)}
                            disabled={!isCancellable}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight="medium">
                            {order.symbol}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {order.order_type.replace('_', ' ').toUpperCase()}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                            {order.quantity}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                            {formatCurrency(order.price)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip 
                            label={order.status.toUpperCase()} 
                            size="small"
                            sx={{ 
                              backgroundColor: getStatusColor(order.status),
                              color: 'white'
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {order.created_at ? new Date(order.created_at).toLocaleDateString() : 'N/A'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
              <Typography color="text.secondary">
                {orders.length === 0 ? 'No orders found' : `No ${filterStatus} orders found`}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Bulk Operation Confirmation Dialog */}
      <Dialog open={showBulkDialog} onClose={() => setShowBulkDialog(false)}>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <WarningIcon color="warning" />
            <Typography variant="h6">Confirm Bulk Operation</Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Are you sure you want to {getBulkOperationDescription(bulkOperation)}?
          </Typography>
          <Alert severity="warning">
            This action cannot be undone. Orders that are already filled or cancelled will not be affected.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowBulkDialog(false)}>Cancel</Button>
          <Button 
            onClick={executeBulkOperation} 
            variant="contained" 
            color="error"
            disabled={loading}
          >
            {loading ? <CircularProgress size={20} /> : 'Confirm'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default BulkOrderOperations;