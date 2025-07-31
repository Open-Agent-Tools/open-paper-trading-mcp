import React, { useState, useEffect, useCallback } from 'react';
import { 
  TextField, Button, Select, MenuItem, FormControl, InputLabel, Paper, Typography, Box, 
  Snackbar, Alert, Chip, Divider, Card, CardContent, Grid, Switch, FormControlLabel,
  Accordion, AccordionSummary, AccordionDetails, Tooltip, CircularProgress
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoIcon from '@mui/icons-material/Info';
import type { NewOrder, OrderType, OrderCondition } from '../types';
import { createOrder, getStockPrice } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';

interface OrderPreview {
  estimatedCost: number;
  estimatedValue: number;
  currentPrice?: number;
  priceImpact?: number;
  marginRequired?: number;
}

const CreateOrderForm: React.FC = () => {
  // Basic order fields
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState<number | ''>('');
  const [orderType, setOrderType] = useState<OrderType>('buy');
  const [condition, setCondition] = useState<OrderCondition>('market');
  const [price, setPrice] = useState<number | ''>('');
  const [stopPrice, setStopPrice] = useState<number | ''>('');

  // Advanced options
  const [isAdvancedMode, setIsAdvancedMode] = useState(false);
  const [timeInForce, setTimeInForce] = useState('day'); // day, gtc, ioc, fok
  const [allOrNone, setAllOrNone] = useState(false);
  
  // Real-time validation and preview
  const [isValidatingSymbol, setIsValidatingSymbol] = useState(false);
  const [symbolValid, setSymbolValid] = useState<boolean | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [orderPreview, setOrderPreview] = useState<OrderPreview | null>(null);
  
  // UI states
  const [openSnackbar, setOpenSnackbar] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const { selectedAccount } = useAccountContext();

  // Real-time symbol validation
  const validateSymbol = useCallback(async (symbolToValidate: string) => {
    if (!symbolToValidate || symbolToValidate.length < 1) {
      setSymbolValid(null);
      setCurrentPrice(null);
      return;
    }

    setIsValidatingSymbol(true);
    try {
      const response = await getStockPrice(symbolToValidate.toUpperCase());
      if (response.success && response.price_data?.price) {
        setSymbolValid(true);
        setCurrentPrice(response.price_data.price);
      } else {
        setSymbolValid(false);
        setCurrentPrice(null);
      }
    } catch (error) {
      setSymbolValid(false);
      setCurrentPrice(null);
    } finally {
      setIsValidatingSymbol(false);
    }
  }, []);

  // Calculate order preview
  const calculateOrderPreview = useCallback(() => {
    if (!currentPrice || !quantity || typeof quantity !== 'number') {
      setOrderPreview(null);
      return;
    }

    let effectivePrice = currentPrice;
    if (condition === 'limit' && price && typeof price === 'number') {
      effectivePrice = price;
    } else if (condition === 'stop' && stopPrice && typeof stopPrice === 'number') {
      effectivePrice = stopPrice;
    } else if (condition === 'stop_limit' && price && typeof price === 'number') {
      effectivePrice = price;
    }

    const estimatedValue = effectivePrice * quantity;
    const estimatedCost = estimatedValue; // Plus commissions if any
    const priceImpact = ((effectivePrice - currentPrice) / currentPrice) * 100;
    
    setOrderPreview({
      estimatedCost,
      estimatedValue,
      currentPrice,
      priceImpact,
      marginRequired: orderType === 'sell' ? estimatedValue * 0.5 : undefined, // Simplified margin calc
    });
  }, [currentPrice, quantity, condition, price, stopPrice, orderType]);

  // Effects for real-time updates
  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      if (symbol) {
        validateSymbol(symbol);
      }
    }, 500);

    return () => clearTimeout(debounceTimer);
  }, [symbol, validateSymbol]);

  useEffect(() => {
    calculateOrderPreview();
  }, [calculateOrderPreview]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    
    if (!selectedAccount) {
      setSnackbarMessage('Please select an account first.');
      setSnackbarSeverity('error');
      setOpenSnackbar(true);
      return;
    }

    if (!symbolValid) {
      setSnackbarMessage('Please enter a valid stock symbol.');
      setSnackbarSeverity('error');
      setOpenSnackbar(true);
      return;
    }

    setIsSubmitting(true);

    const order: NewOrder = {
      symbol: symbol.toUpperCase(),
      order_type: orderType,
      quantity: Number(quantity),
      condition,
      price: condition === 'limit' || condition === 'stop_limit' ? Number(price) : undefined,
      stop_price: (condition === 'stop' || condition === 'stop_limit') ? Number(stopPrice) : undefined,
      account_id: selectedAccount.id,
    };
    
    try {
      const response = await createOrder(order);
      if (response.success) {
        setSnackbarMessage(`Order submitted successfully! Order ID: ${response.order_id || 'N/A'}`);
        setSnackbarSeverity('success');
        // Reset form
        setSymbol('');
        setQuantity('');
        setPrice('');
        setStopPrice('');
        setSymbolValid(null);
        setCurrentPrice(null);
        setOrderPreview(null);
      } else {
        setSnackbarMessage(response.message || 'Failed to submit order.');
        setSnackbarSeverity('error');
      }
    } catch (error) {
      setSnackbarMessage('Failed to submit order. Please try again.');
      setSnackbarSeverity('error');
    } finally {
      setIsSubmitting(false);
      setOpenSnackbar(true);
    }
  };

  const handleCloseSnackbar = () => {
    setOpenSnackbar(false);
  };

  // const getSymbolStatusColor = () => {
  //   if (isValidatingSymbol) return 'info';
  //   if (symbolValid === true) return 'success';
  //   if (symbolValid === false) return 'error';
  //   return 'default';
  // };

  const getSymbolHelperText = () => {
    if (isValidatingSymbol) return 'Validating symbol...';
    if (symbolValid === false) return 'Invalid symbol or not found';
    if (symbolValid === true && currentPrice) return `Current price: $${currentPrice.toFixed(2)}`;
    return '';
  };

  return (
    <>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom sx={{ mb: 3 }}>
          Create Order
        </Typography>
        
        <form onSubmit={handleSubmit}>
          <Grid container spacing={3}>
            {/* Basic Order Information */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Order Details
                  </Typography>
                  
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField
                      label="Symbol"
                      variant="outlined"
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                      required
                      helperText={getSymbolHelperText()}
                      error={symbolValid === false}
                      InputProps={{
                        endAdornment: isValidatingSymbol ? <CircularProgress size={20} /> : null,
                      }}
                    />
                  
                    <TextField
                      label="Quantity"
                      variant="outlined"
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(Number(e.target.value))}
                      required
                      inputProps={{ min: 1, step: 1 }}
                      helperText="Number of shares"
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
                        <MenuItem value="market">
                          <Box>
                            <Typography>Market</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Execute at current market price
                            </Typography>
                          </Box>
                        </MenuItem>
                        <MenuItem value="limit">
                          <Box>
                            <Typography>Limit</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Execute at or better than specified price
                            </Typography>
                          </Box>
                        </MenuItem>
                        <MenuItem value="stop">
                          <Box>
                            <Typography>Stop</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Market order when stop price is reached
                            </Typography>
                          </Box>
                        </MenuItem>
                        <MenuItem value="stop_limit">
                          <Box>
                            <Typography>Stop Limit</Typography>
                            <Typography variant="caption" color="text.secondary">
                              Limit order when stop price is reached
                            </Typography>
                          </Box>
                        </MenuItem>
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
                        helperText="Maximum price for buy orders, minimum for sell orders"
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
                        helperText="Price that triggers the order"
                      />
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Order Preview & Advanced Options */}
            <Grid item xs={12} md={6}>
              {/* Order Preview */}
              {orderPreview && (
                <Card variant="outlined" sx={{ mb: 2 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Order Preview
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2">Current Price:</Typography>
                        <Typography variant="body2" fontWeight="bold">
                          ${orderPreview.currentPrice?.toFixed(2)}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2">Estimated Cost:</Typography>
                        <Typography variant="body2" fontWeight="bold" color="primary">
                          ${orderPreview.estimatedCost.toFixed(2)}
                        </Typography>
                      </Box>
                      {orderPreview.priceImpact !== undefined && (
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Typography variant="body2">Price Impact:</Typography>
                          <Chip 
                            label={`${orderPreview.priceImpact.toFixed(2)}%`}
                            size="small"
                            color={Math.abs(orderPreview.priceImpact) > 5 ? 'warning' : 'default'}
                          />
                        </Box>
                      )}
                      {orderPreview.marginRequired && (
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Typography variant="body2">Margin Required:</Typography>
                          <Typography variant="body2" color="warning.main">
                            ${orderPreview.marginRequired.toFixed(2)}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              )}

              {/* Advanced Options */}
              <Accordion expanded={isAdvancedMode} onChange={() => setIsAdvancedMode(!isAdvancedMode)}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">Advanced Options</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <FormControl fullWidth>
                      <InputLabel>Time in Force</InputLabel>
                      <Select
                        value={timeInForce}
                        label="Time in Force"
                        onChange={(e) => setTimeInForce(e.target.value)}
                      >
                        <MenuItem value="day">Day (DAY)</MenuItem>
                        <MenuItem value="gtc">Good Till Cancelled (GTC)</MenuItem>
                        <MenuItem value="ioc">Immediate or Cancel (IOC)</MenuItem>
                        <MenuItem value="fok">Fill or Kill (FOK)</MenuItem>
                      </Select>
                    </FormControl>
                    
                    <FormControlLabel
                      control={
                        <Switch
                          checked={allOrNone}
                          onChange={(e) => setAllOrNone(e.target.checked)}
                        />
                      }
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography>All or None</Typography>
                          <Tooltip title="Order must be filled completely or not at all">
                            <InfoIcon fontSize="small" />
                          </Tooltip>
                        </Box>
                      }
                    />
                  </Box>
                </AccordionDetails>
              </Accordion>
            </Grid>

            {/* Submit Button */}
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
                <Button 
                  type="submit" 
                  variant="contained" 
                  color="primary" 
                  size="large"
                  disabled={!symbolValid || isSubmitting}
                  sx={{ minWidth: 200 }}
                >
                  {isSubmitting ? (
                    <>
                      <CircularProgress size={20} sx={{ mr: 1 }} />
                      Submitting...
                    </>
                  ) : (
                    'Submit Order'
                  )}
                </Button>
                <Button 
                  type="button" 
                  variant="outlined" 
                  size="large"
                  onClick={() => {
                    setSymbol('');
                    setQuantity('');
                    setPrice('');
                    setStopPrice('');
                    setSymbolValid(null);
                    setCurrentPrice(null);
                    setOrderPreview(null);
                  }}
                >
                  Clear Form
                </Button>
              </Box>
            </Grid>
          </Grid>
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
