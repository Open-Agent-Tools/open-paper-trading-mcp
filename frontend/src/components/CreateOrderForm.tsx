import React, { useState } from 'react';
import { TextField, Button, Select, MenuItem, FormControl, InputLabel, Paper, Typography, Box, Snackbar, Alert } from '@mui/material';
import type { NewOrder } from '../types';
import { createOrder } from '../services/apiClient';

const CreateOrderForm: React.FC = () => {
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState<number | ''>('');
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('MARKET');
  const [price, setPrice] = useState<number | ''>('');
  const [openSnackbar, setOpenSnackbar] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const order: NewOrder = {
      symbol,
      quantity: Number(quantity),
      type: orderType,
      price: orderType === 'LIMIT' ? Number(price) : undefined,
    };
    
    try {
      await createOrder(order);
      setSnackbarMessage('Order submitted successfully!');
      setSnackbarSeverity('success');
      setSymbol('');
      setQuantity('');
      setPrice('');
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
                onChange={(e) => setOrderType(e.target.value as 'MARKET' | 'LIMIT')}
              >
                <MenuItem value="MARKET">Market</MenuItem>
                <MenuItem value="LIMIT">Limit</MenuItem>
              </Select>
            </FormControl>
            {orderType === 'LIMIT' && (
              <TextField
                label="Price"
                variant="outlined"
                type="number"
                value={price}
                onChange={(e) => setPrice(Number(e.target.value))}
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
