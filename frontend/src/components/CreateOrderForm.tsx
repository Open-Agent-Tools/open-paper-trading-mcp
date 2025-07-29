import React, { useState } from 'react';
import { TextField, Button, Select, MenuItem, FormControl, InputLabel, Paper, Typography, Box, Snackbar, Alert } from '@mui/material';
import type { NewOrder, OrderType, OrderCondition } from '../types';
import { createOrder } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';

const CreateOrderForm: React.FC = () => {
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState<number | ''>('');
  const [orderType, setOrderType] = useState<OrderType>('buy');
  const [condition, setCondition] = useState<OrderCondition>('market');
  const [price, setPrice] = useState<number | ''>('');
  const [stopPrice, setStopPrice] = useState<number | ''>('');
  const [openSnackbar, setOpenSnackbar] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');
  const { selectedAccount } = useAccountContext();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    
    if (!selectedAccount) {
      setSnackbarMessage('Please select an account first.');
      setSnackbarSeverity('error');
      setOpenSnackbar(true);
      return;
    }

    const order: NewOrder = {
      symbol,
      order_type: orderType,
      quantity: Number(quantity),
      condition,
      price: condition === 'limit' ? Number(price) : undefined,
      stop_price: (condition === 'stop' || condition === 'stop_limit') ? Number(stopPrice) : undefined,
      account_id: selectedAccount.id,
    };
    
    try {
      await createOrder(order);
      setSnackbarMessage('Order submitted successfully!');
      setSnackbarSeverity('success');
      setSymbol('');
      setQuantity('');
      setPrice('');
      setStopPrice('');
    } catch (error) {
      setSnackbarMessage('Failed to submit order.');
      setSnackbarSeverity('error');
    } finally {
      setOpenSnackbar(true);
    }
  };

  const handleCloseSnackbar = () => {
    setOpenSnackbar(false);
  };

  return (
    <>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Create Order
        </Typography>
        <form onSubmit={handleSubmit}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Symbol"
              variant="outlined"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              required
            />
            <TextField
              label="Quantity"
              variant="outlined"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              required
              inputProps={{ min: 1 }}
            />
            <FormControl fullWidth>
              <InputLabel>Order Type</InputLabel>
              <Select
                value={orderType}
                label="Order Type"
                onChange={(e) => setOrderType(e.target.value as OrderType)}
              >
                <MenuItem value="buy">Buy</MenuItem>
                <MenuItem value="sell">Sell</MenuItem>
                <MenuItem value="buy_to_open">Buy to Open (Options)</MenuItem>
                <MenuItem value="sell_to_open">Sell to Open (Options)</MenuItem>
                <MenuItem value="buy_to_close">Buy to Close (Options)</MenuItem>
                <MenuItem value="sell_to_close">Sell to Close (Options)</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Order Condition</InputLabel>
              <Select
                value={condition}
                label="Order Condition"
                onChange={(e) => setCondition(e.target.value as OrderCondition)}
              >
                <MenuItem value="market">Market</MenuItem>
                <MenuItem value="limit">Limit</MenuItem>
                <MenuItem value="stop">Stop</MenuItem>
                <MenuItem value="stop_limit">Stop Limit</MenuItem>
              </Select>
            </FormControl>
            {(condition === 'limit' || condition === 'stop_limit') && (
              <TextField
                label="Limit Price"
                variant="outlined"
                type="number"
                value={price}
                onChange={(e) => setPrice(Number(e.target.value))}
                required
                inputProps={{ min: 0.01, step: 0.01 }}
              />
            )}
            {(condition === 'stop' || condition === 'stop_limit') && (
              <TextField
                label="Stop Price"
                variant="outlined"
                type="number"
                value={stopPrice}
                onChange={(e) => setStopPrice(Number(e.target.value))}
                required
                inputProps={{ min: 0.01, step: 0.01 }}
              />
            )}
            <Button type="submit" variant="contained" color="primary">
              Submit Order
            </Button>
          </Box>
        </form>
      </Paper>
      <Snackbar open={openSnackbar} autoHideDuration={6000} onClose={handleCloseSnackbar}>
        <Alert onClose={handleCloseSnackbar} severity={snackbarSeverity} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </>
  );
};

export default CreateOrderForm;
