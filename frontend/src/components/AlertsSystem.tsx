import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  // Alert,
  CircularProgress,
  IconButton,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Grid,
  Switch,
  FormControlLabel,
  useTheme,
} from '@mui/material';
import {
  Notifications as AlertIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  // Edit as EditIcon,
  // NotificationsActive as ActiveIcon,
  // NotificationsOff as InactiveIcon,
} from '@mui/icons-material';
import { useAccountContext } from '../contexts/AccountContext';
import { searchStocks, getStockPrice } from '../services/apiClient';
import type { StockSearchResult } from '../types';

interface PriceAlert {
  id: string;
  symbol: string;
  companyName: string;
  alertType: 'above' | 'below' | 'change_percent';
  targetValue: number;
  currentValue?: number;
  isActive: boolean;
  isTriggered: boolean;
  triggeredAt?: string;
  createdAt: string;
  lastChecked?: string;
  note?: string;
}

const AlertsSystem: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [loading, setLoading] = useState(false);
  const [, setError] = useState<string | null>(null);
  
  // Form state
  const [newAlert, setNewAlert] = useState<Partial<PriceAlert>>({
    alertType: 'above',
    isActive: true
  });
  const [stockSearchQuery, setStockSearchQuery] = useState('');
  const [stockSearchResults, setStockSearchResults] = useState<StockSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);

  // Load alerts from localStorage
  const loadAlerts = () => {
    try {
      const savedAlerts = localStorage.getItem(`priceAlerts_${selectedAccount?.id || 'default'}`);
      if (savedAlerts) {
        setAlerts(JSON.parse(savedAlerts));
      } else {
        // Create some example alerts
        const exampleAlerts: PriceAlert[] = [
          {
            id: '1',
            symbol: 'AAPL',
            companyName: 'Apple Inc.',
            alertType: 'above',
            targetValue: 200,
            isActive: true,
            isTriggered: false,
            createdAt: new Date().toISOString(),
            note: 'Resistance level breakout'
          },
          {
            id: '2',
            symbol: 'TSLA',
            companyName: 'Tesla Inc.',
            alertType: 'below',
            targetValue: 300,
            isActive: true,
            isTriggered: false,
            createdAt: new Date().toISOString(),
            note: 'Support level watch'
          }
        ];
        setAlerts(exampleAlerts);
        saveAlerts(exampleAlerts);
      }
    } catch (err) {
      console.error('Failed to load alerts:', err);
    }
  };

  const saveAlerts = (alertsToSave: PriceAlert[]) => {
    try {
      localStorage.setItem(
        `priceAlerts_${selectedAccount?.id || 'default'}`,
        JSON.stringify(alertsToSave)
      );
    } catch (err) {
      console.error('Failed to save alerts:', err);
    }
  };

  const searchStocksForAlert = async () => {
    if (!stockSearchQuery.trim()) return;

    setSearchLoading(true);
    try {
      const response = await searchStocks(stockSearchQuery.trim());
      if (response.success) {
        setStockSearchResults(response.results.results || []);
      }
    } catch (err) {
      console.error('Stock search failed:', err);
    } finally {
      setSearchLoading(false);
    }
  };

  const createAlert = () => {
    if (!selectedStock || !newAlert.targetValue || !newAlert.alertType) return;

    const alert: PriceAlert = {
      id: Date.now().toString(),
      symbol: selectedStock.symbol,
      companyName: selectedStock.name,
      alertType: newAlert.alertType,
      targetValue: newAlert.targetValue,
      isActive: newAlert.isActive || true,
      isTriggered: false,
      createdAt: new Date().toISOString(),
      note: newAlert.note
    };

    const updatedAlerts = [...alerts, alert];
    setAlerts(updatedAlerts);
    saveAlerts(updatedAlerts);
    
    // Reset form
    setNewAlert({ alertType: 'above', isActive: true });
    setSelectedStock(null);
    setStockSearchQuery('');
    setStockSearchResults([]);
    setShowCreateDialog(false);
  };

  const deleteAlert = (alertId: string) => {
    const updatedAlerts = alerts.filter(a => a.id !== alertId);
    setAlerts(updatedAlerts);
    saveAlerts(updatedAlerts);
  };

  const toggleAlert = (alertId: string) => {
    const updatedAlerts = alerts.map(alert => 
      alert.id === alertId 
        ? { ...alert, isActive: !alert.isActive, isTriggered: false }
        : alert
    );
    setAlerts(updatedAlerts);
    saveAlerts(updatedAlerts);
  };

  const checkAlerts = async () => {
    if (alerts.length === 0) return;

    setLoading(true);
    try {
      const activeAlerts = alerts.filter(alert => alert.isActive && !alert.isTriggered);
      
      for (const alert of activeAlerts) {
        try {
          const response = await getStockPrice(alert.symbol);
          if (response.success && response.price_data.price) {
            const currentPrice = response.price_data.price;
            let shouldTrigger = false;

            switch (alert.alertType) {
              case 'above':
                shouldTrigger = currentPrice >= alert.targetValue;
                break;
              case 'below':
                shouldTrigger = currentPrice <= alert.targetValue;
                break;
              case 'change_percent':
                if (response.price_data.change_percent) {
                  shouldTrigger = Math.abs(response.price_data.change_percent) >= alert.targetValue;
                }
                break;
            }

            const updatedAlert = {
              ...alert,
              currentValue: currentPrice,
              lastChecked: new Date().toISOString(),
              isTriggered: shouldTrigger,
              triggeredAt: shouldTrigger ? new Date().toISOString() : alert.triggeredAt
            };

            const updatedAlerts = alerts.map(a => a.id === alert.id ? updatedAlert : a);
            setAlerts(updatedAlerts);
            saveAlerts(updatedAlerts);

            if (shouldTrigger) {
              // In a real app, this could send a notification
              console.log(`Alert triggered for ${alert.symbol}: ${alert.alertType} ${alert.targetValue}`);
            }
          }
        } catch (err) {
          console.warn(`Failed to check alert for ${alert.symbol}:`, err);
        }
      }
    } catch (err) {
      setError('Failed to check alerts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [selectedAccount]);

  useEffect(() => {
    if (stockSearchQuery.length >= 2) {
      const debounceTimer = setTimeout(() => {
        searchStocksForAlert();
      }, 500);
      return () => clearTimeout(debounceTimer);
    } else {
      setStockSearchResults([]);
    }
  }, [stockSearchQuery]);

  const formatCurrency = (value: number | undefined) => {
    if (!value) return 'N/A';
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    });
  };

  const getAlertTypeLabel = (type: string) => {
    switch (type) {
      case 'above': return 'Price Above';
      case 'below': return 'Price Below';
      case 'change_percent': return 'Daily Change %';
      default: return type;
    }
  };

  const getAlertStatusColor = (alert: PriceAlert) => {
    if (alert.isTriggered) return theme.palette.error.main;
    if (!alert.isActive) return theme.palette.text.disabled;
    return theme.palette.success.main;
  };

  const getAlertStatusLabel = (alert: PriceAlert) => {
    if (alert.isTriggered) return 'TRIGGERED';
    if (!alert.isActive) return 'INACTIVE';
    return 'ACTIVE';
  };

  const activeAlertsCount = alerts.filter(a => a.isActive && !a.isTriggered).length;
  const triggeredAlertsCount = alerts.filter(a => a.isTriggered).length;

  return (
    <>
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <AlertIcon color="primary" />
              <Typography variant="h6">Price Alerts</Typography>
            </Box>
          }
          action={
            <Box display="flex" gap={1}>
              <Button
                variant="outlined"
                size="small"
                onClick={checkAlerts}
                disabled={loading || activeAlertsCount === 0}
              >
                {loading ? <CircularProgress size={16} /> : 'Check Alerts'}
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => setShowCreateDialog(true)}
              >
                New Alert
              </Button>
            </Box>
          }
          subheader={
            <Box display="flex" gap={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Monitor price movements and get notified
              </Typography>
              <Chip 
                label={`${activeAlertsCount} Active`} 
                size="small" 
                color="success" 
                variant="outlined"
              />
              {triggeredAlertsCount > 0 && (
                <Chip 
                  label={`${triggeredAlertsCount} Triggered`} 
                  size="small" 
                  color="error" 
                  variant="outlined"
                />
              )}
            </Box>
          }
        />
        <CardContent>
          {alerts.length > 0 ? (
            <List>
              {alerts.map((alert, index) => (
                <ListItem
                  key={alert.id}
                  divider={index < alerts.length - 1}
                  sx={{ 
                    border: `1px solid ${alert.isTriggered ? theme.palette.error.main : theme.palette.divider}`,
                    borderRadius: 1,
                    mb: 1,
                    backgroundColor: alert.isTriggered ? `${theme.palette.error.main}10` : 'inherit',
                    '&:last-child': { mb: 0 }
                  }}
                >
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle2" fontWeight="bold">
                          {alert.symbol}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {getAlertTypeLabel(alert.alertType)}
                        </Typography>
                        <Typography variant="body2" fontWeight="medium">
                          {alert.alertType === 'change_percent' ? `${alert.targetValue}%` : formatCurrency(alert.targetValue)}
                        </Typography>
                        <Chip 
                          label={getAlertStatusLabel(alert)}
                          size="small"
                          sx={{ 
                            backgroundColor: getAlertStatusColor(alert),
                            color: 'white'
                          }}
                        />
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {alert.companyName}
                        </Typography>
                        {alert.note && (
                          <Typography variant="caption" color="text.secondary">
                            Note: {alert.note}
                          </Typography>
                        )}
                        <Box display="flex" gap={2} mt={0.5}>
                          {alert.currentValue && (
                            <Typography variant="caption" color="text.secondary">
                              Current: {formatCurrency(alert.currentValue)}
                            </Typography>
                          )}
                          {alert.lastChecked && (
                            <Typography variant="caption" color="text.secondary">
                              Checked: {new Date(alert.lastChecked).toLocaleTimeString()}
                            </Typography>
                          )}
                          {alert.triggeredAt && (
                            <Typography variant="caption" color="error.main">
                              Triggered: {new Date(alert.triggeredAt).toLocaleString()}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Box display="flex" alignItems="center" gap={1}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={alert.isActive}
                            onChange={() => toggleAlert(alert.id)}
                            size="small"
                          />
                        }
                        label=""
                        sx={{ mr: 1 }}
                      />
                      <IconButton 
                        size="small" 
                        onClick={() => deleteAlert(alert.id)}
                        color="error"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          ) : (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
              <Typography color="text.secondary">No price alerts configured</Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Create Alert Dialog */}
      <Dialog open={showCreateDialog} onClose={() => setShowCreateDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Price Alert</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                size="small"
                label="Search Stock"
                value={stockSearchQuery}
                onChange={(e) => setStockSearchQuery(e.target.value.toUpperCase())}
                placeholder="Enter symbol or company name"
              />
              
              {searchLoading && (
                <Box display="flex" justifyContent="center" my={1}>
                  <CircularProgress size={16} />
                </Box>
              )}

              {stockSearchResults.length > 0 && !selectedStock && (
                <List sx={{ maxHeight: 200, overflow: 'auto', border: `1px solid ${theme.palette.divider}`, borderRadius: 1, mt: 1 }}>
                  {stockSearchResults.slice(0, 5).map((stock) => (
                    <ListItem 
                      key={stock.symbol}
                      component="button"
                      onClick={() => {
                        setSelectedStock(stock);
                        setStockSearchQuery('');
                        setStockSearchResults([]);
                      }}
                      sx={{ cursor: 'pointer' }}
                    >
                      <ListItemText
                        primary={stock.name}
                        secondary={stock.symbol}
                      />
                    </ListItem>
                  ))}
                </List>
              )}

              {selectedStock && (
                <Box mt={1} p={1} border={`1px solid ${theme.palette.success.main}`} borderRadius={1}>
                  <Typography variant="body2" color="success.main">
                    Selected: {selectedStock.name} ({selectedStock.symbol})
                  </Typography>
                </Box>
              )}
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Alert Type</InputLabel>
                <Select
                  value={newAlert.alertType || 'above'}
                  label="Alert Type"
                  onChange={(e) => setNewAlert(prev => ({ ...prev, alertType: e.target.value as any }))}
                >
                  <MenuItem value="above">Price Above</MenuItem>
                  <MenuItem value="below">Price Below</MenuItem>
                  <MenuItem value="change_percent">Daily Change %</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <TextField
                fullWidth
                size="small"
                label={newAlert.alertType === 'change_percent' ? 'Change %' : 'Target Price'}
                type="number"
                value={newAlert.targetValue || ''}
                onChange={(e) => setNewAlert(prev => ({ ...prev, targetValue: Number(e.target.value) }))}
                InputProps={{ 
                  inputProps: { 
                    step: newAlert.alertType === 'change_percent' ? 0.1 : 0.01 
                  } 
                }}
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                size="small"
                label="Note (Optional)"
                value={newAlert.note || ''}
                onChange={(e) => setNewAlert(prev => ({ ...prev, note: e.target.value }))}
                multiline
                rows={2}
              />
            </Grid>
            
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={newAlert.isActive || true}
                    onChange={(e) => setNewAlert(prev => ({ ...prev, isActive: e.target.checked }))}
                  />
                }
                label="Alert is active"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCreateDialog(false)}>Cancel</Button>
          <Button 
            onClick={createAlert} 
            variant="contained"
            disabled={!selectedStock || !newAlert.targetValue}
          >
            Create Alert
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default AlertsSystem;