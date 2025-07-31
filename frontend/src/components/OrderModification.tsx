import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField,
  Typography, Box, Alert, CircularProgress, FormControl, InputLabel,
  Select, MenuItem, Chip, Grid, Card, CardContent, Divider, IconButton
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import EditIcon from '@mui/icons-material/Edit';
import type { Order, OrderCondition } from '../types';
import { cancelOrder, createOrder, getStockPrice } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';

interface OrderModificationProps {
  order: Order | null;
  open: boolean;
  onClose: () => void;
  onOrderModified: () => void;
}

const OrderModification: React.FC<OrderModificationProps> = ({
  order,
  open,
  onClose,
  onOrderModified
}) => {
  const [modifiedQuantity, setModifiedQuantity] = useState<number | ''>('');
  const [modifiedPrice, setModifiedPrice] = useState<number | ''>('');
  const [modifiedStopPrice, setModifiedStopPrice] = useState<number | ''>('');
  const [modifiedCondition, setModifiedCondition] = useState<OrderCondition>('market');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [loadingPrice, setLoadingPrice] = useState(false);
  
  const { selectedAccount } = useAccountContext();

  // Initialize form with current order values
  useEffect(() => {
    if (order) {
      setModifiedQuantity(order.quantity);
      setModifiedPrice(order.price || '');
      setModifiedStopPrice(order.stop_price || '');
      setModifiedCondition(order.condition);
      setError(null);
      
      // Fetch current price for reference
      if (order.symbol) {
        fetchCurrentPrice(order.symbol);
      }
    }
  }, [order]);

  const fetchCurrentPrice = useCallback(async (symbol: string) => {
    setLoadingPrice(true);
    try {
      const response = await getStockPrice(symbol);
      if (response.success && response.price_data?.price) {
        setCurrentPrice(response.price_data.price);
      }
    } catch (error) {
      console.error('Failed to fetch current price:', error);
    } finally {
      setLoadingPrice(false);
    }
  }, []);

  const handleModifyOrder = async () => {
    if (!order || !selectedAccount) return;

    setIsLoading(true);
    setError(null);

    try {
      // Step 1: Cancel the existing order
      const cancelResponse = await cancelOrder(order.id);
      if (!cancelResponse.success) {
        throw new Error(cancelResponse.message || 'Failed to cancel existing order');
      }

      // Step 2: Create a new order with modified parameters
      const newOrder = {
        symbol: order.symbol,
        order_type: order.order_type,
        quantity: Number(modifiedQuantity),
        condition: modifiedCondition,
        price: (modifiedCondition === 'limit' || modifiedCondition === 'stop_limit') ? Number(modifiedPrice) : undefined,
        stop_price: (modifiedCondition === 'stop' || modifiedCondition === 'stop_limit') ? Number(modifiedStopPrice) : undefined,
        account_id: selectedAccount.id,
      };

      const createResponse = await createOrder(newOrder);
      if (!createResponse.success) {
        throw new Error(createResponse.message || 'Failed to create modified order');
      }

      onOrderModified();
      onClose();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to modify order');
    } finally {
      setIsLoading(false);
    }
  };

  const getOrderStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'filled': return 'success';
      case 'cancelled': case 'rejected': return 'error';
      case 'pending': case 'triggered': return 'warning';
      case 'partially_filled': return 'info';
      default: return 'default';
    }
  };

  const isModifiable = order?.status === 'pending' || order?.status === 'triggered';
  const hasChanges = order && (
    Number(modifiedQuantity) !== order.quantity ||
    Number(modifiedPrice) !== (order.price || 0) ||
    Number(modifiedStopPrice) !== (order.stop_price || 0) ||
    modifiedCondition !== order.condition
  );

  if (!order) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            Modify Order - {order.symbol}
          </Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Grid container spacing={3}>
          {/* Current Order Information */}
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  Current Order
                  <Chip 
                    label={order.status.toUpperCase()} 
                    color={getOrderStatusColor(order.status)}
                    size="small"
                  />
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Symbol:</Typography>
                    <Typography variant="body2" fontWeight="bold">{order.symbol}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Order Type:</Typography>
                    <Typography variant="body2">{order.order_type}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Quantity:</Typography>
                    <Typography variant="body2">{order.quantity}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Condition:</Typography>
                    <Typography variant="body2">{order.condition}</Typography>
                  </Box>
                  {order.price && (
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" color="text.secondary">Price:</Typography>
                      <Typography variant="body2">${order.price.toFixed(2)}</Typography>
                    </Box>
                  )}
                  {order.stop_price && (
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" color="text.secondary">Stop Price:</Typography>
                      <Typography variant="body2">${order.stop_price.toFixed(2)}</Typography>
                    </Box>
                  )}
                  <Divider sx={{ my: 1 }} />
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Current Price:</Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {loadingPrice ? (
                        <CircularProgress size={16} />
                      ) : currentPrice ? (
                        `$${currentPrice.toFixed(2)}`
                      ) : (
                        'N/A'
                      )}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Modification Form */}
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <EditIcon fontSize="small" />
                  Modify Order
                </Typography>
                
                {!isModifiable ? (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    This order cannot be modified because its status is "{order.status}". 
                    Only pending or triggered orders can be modified.
                  </Alert>
                ) : (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField
                      label="Quantity"
                      variant="outlined"
                      type="number"
                      value={modifiedQuantity}
                      onChange={(e) => setModifiedQuantity(Number(e.target.value))}
                      required
                      inputProps={{ min: 1, step: 1 }}
                      helperText="Number of shares"
                    />

                    <FormControl fullWidth>
                      <InputLabel>Order Condition</InputLabel>
                      <Select
                        value={modifiedCondition}
                        label="Order Condition"
                        onChange={(e) => setModifiedCondition(e.target.value as OrderCondition)}
                      >
                        <MenuItem value="market">Market</MenuItem>
                        <MenuItem value="limit">Limit</MenuItem>
                        <MenuItem value="stop">Stop</MenuItem>
                        <MenuItem value="stop_limit">Stop Limit</MenuItem>
                      </Select>
                    </FormControl>

                    {(modifiedCondition === 'limit' || modifiedCondition === 'stop_limit') && (
                      <TextField
                        label="Limit Price"
                        variant="outlined"
                        type="number"
                        value={modifiedPrice}
                        onChange={(e) => setModifiedPrice(Number(e.target.value))}
                        required
                        inputProps={{ min: 0.01, step: 0.01 }}
                        helperText="Maximum price for buy orders, minimum for sell orders"
                      />
                    )}

                    {(modifiedCondition === 'stop' || modifiedCondition === 'stop_limit') && (
                      <TextField
                        label="Stop Price"
                        variant="outlined"
                        type="number"
                        value={modifiedStopPrice}
                        onChange={(e) => setModifiedStopPrice(Number(e.target.value))}
                        required
                        inputProps={{ min: 0.01, step: 0.01 }}
                        helperText="Price that triggers the order"
                      />
                    )}

                    {hasChanges && (
                      <Alert severity="info" sx={{ mt: 1 }}>
                        <Typography variant="body2" fontWeight="bold">
                          Important: This will cancel the existing order and create a new one.
                        </Typography>
                        <Typography variant="body2">
                          Your order queue position will be lost and a new order ID will be assigned.
                        </Typography>
                      </Alert>
                    )}
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Error Display */}
          {error && (
            <Grid item xs={12}>
              <Alert severity="error">
                {error}
              </Alert>
            </Grid>
          )}
        </Grid>
      </DialogContent>

      <DialogActions sx={{ p: 3 }}>
        <Button onClick={onClose} color="inherit">
          Cancel
        </Button>
        <Button
          onClick={handleModifyOrder}
          variant="contained"
          disabled={!isModifiable || !hasChanges || isLoading}
          startIcon={isLoading ? <CircularProgress size={16} /> : <EditIcon />}
        >
          {isLoading ? 'Modifying...' : 'Modify Order'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default OrderModification;