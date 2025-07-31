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
  Grid,
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
  useTheme,
} from '@mui/material';
import {
  Bookmark as TemplateIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as UseIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { useAccountContext } from '../contexts/AccountContext';
import type { OrderType, OrderCondition } from '../types';

interface OrderTemplate {
  id: string;
  name: string;
  description?: string;
  symbol?: string;
  orderType: OrderType;
  quantity: number;
  condition: OrderCondition;
  price?: number;
  stopPrice?: number;
  trailPercent?: number;
  trailAmount?: number;
  createdAt: string;
  lastUsed?: string;
  useCount: number;
}

interface OrderTemplatesProps {
  onUseTemplate?: (template: OrderTemplate) => void;
}

const OrderTemplates: React.FC<OrderTemplatesProps> = ({ onUseTemplate }) => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [templates, setTemplates] = useState<OrderTemplate[]>([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<OrderTemplate | null>(null);
  const [newTemplate, setNewTemplate] = useState<Partial<OrderTemplate>>({
    orderType: 'buy',
    condition: 'market',
    quantity: 100
  });

  // Load templates from localStorage (in a real app, this would be from an API)
  const loadTemplates = () => {
    try {
      const savedTemplates = localStorage.getItem(`orderTemplates_${selectedAccount?.id || 'default'}`);
      if (savedTemplates) {
        setTemplates(JSON.parse(savedTemplates));
      } else {
        // Load some default templates
        const defaultTemplates: OrderTemplate[] = [
          {
            id: '1',
            name: 'Quick Buy Market',
            description: 'Market buy order for 100 shares',
            orderType: 'buy',
            quantity: 100,
            condition: 'market',
            createdAt: new Date().toISOString(),
            useCount: 0
          },
          {
            id: '2',
            name: 'Limit Buy Small',
            description: 'Limit buy order for 50 shares',
            orderType: 'buy',
            quantity: 50,
            condition: 'limit',
            price: 100,
            createdAt: new Date().toISOString(),
            useCount: 0
          },
          {
            id: '3',
            name: 'Stop Loss 5%',
            description: 'Stop loss order at 5% below current price',
            orderType: 'sell',
            quantity: 100,
            condition: 'stop',
            createdAt: new Date().toISOString(),
            useCount: 0
          }
        ];
        setTemplates(defaultTemplates);
        saveTemplates(defaultTemplates);
      }
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  };

  const saveTemplates = (templatesToSave: OrderTemplate[]) => {
    try {
      localStorage.setItem(
        `orderTemplates_${selectedAccount?.id || 'default'}`,
        JSON.stringify(templatesToSave)
      );
    } catch (err) {
      console.error('Failed to save templates:', err);
    }
  };

  const createTemplate = () => {
    if (!newTemplate.name || !newTemplate.orderType || !newTemplate.condition) {
      return;
    }

    const template: OrderTemplate = {
      id: Date.now().toString(),
      name: newTemplate.name,
      description: newTemplate.description,
      symbol: newTemplate.symbol,
      orderType: newTemplate.orderType,
      quantity: newTemplate.quantity || 100,
      condition: newTemplate.condition,
      price: newTemplate.price,
      stopPrice: newTemplate.stopPrice,
      trailPercent: newTemplate.trailPercent,
      trailAmount: newTemplate.trailAmount,
      createdAt: new Date().toISOString(),
      useCount: 0
    };

    const updatedTemplates = [...templates, template];
    setTemplates(updatedTemplates);
    saveTemplates(updatedTemplates);
    setNewTemplate({ orderType: 'buy', condition: 'market', quantity: 100 });
    setShowCreateDialog(false);
  };

  const updateTemplate = () => {
    if (!editingTemplate) return;

    const updatedTemplates = templates.map(t => 
      t.id === editingTemplate.id ? editingTemplate : t
    );
    setTemplates(updatedTemplates);
    saveTemplates(updatedTemplates);
    setEditingTemplate(null);
    setShowEditDialog(false);
  };

  const deleteTemplate = (templateId: string) => {
    const updatedTemplates = templates.filter(t => t.id !== templateId);
    setTemplates(updatedTemplates);
    saveTemplates(updatedTemplates);
  };

  const useTemplate = (template: OrderTemplate) => {
    // Update use count and last used
    const updatedTemplate = {
      ...template,
      useCount: template.useCount + 1,
      lastUsed: new Date().toISOString()
    };
    
    const updatedTemplates = templates.map(t => 
      t.id === template.id ? updatedTemplate : t
    );
    setTemplates(updatedTemplates);
    saveTemplates(updatedTemplates);

    // Notify parent component
    onUseTemplate?.(updatedTemplate);
  };

  useEffect(() => {
    loadTemplates();
  }, [selectedAccount]);

  const getOrderTypeColor = (orderType: OrderType) => {
    if (orderType.includes('buy')) return theme.palette.success.main;
    if (orderType.includes('sell')) return theme.palette.error.main;
    return theme.palette.text.secondary;
  };

  const getConditionLabel = (condition: OrderCondition) => {
    switch (condition) {
      case 'market': return 'MKT';
      case 'limit': return 'LMT';
      case 'stop': return 'STOP';
      case 'stop_limit': return 'STOP LMT';
      default: return condition.toUpperCase();
    }
  };

  const renderTemplateForm = (template: Partial<OrderTemplate>, onChange: (updates: Partial<OrderTemplate>) => void) => (
    <Grid container spacing={2}>
      <Grid item xs={12}>
        <TextField
          fullWidth
          size="small"
          label="Template Name"
          value={template.name || ''}
          onChange={(e) => onChange({ name: e.target.value })}
          required
        />
      </Grid>
      <Grid item xs={12}>
        <TextField
          fullWidth
          size="small"
          label="Description"
          value={template.description || ''}
          onChange={(e) => onChange({ description: e.target.value })}
          multiline
          rows={2}
        />
      </Grid>
      <Grid item xs={6}>
        <TextField
          fullWidth
          size="small"
          label="Symbol (Optional)"
          value={template.symbol || ''}
          onChange={(e) => onChange({ symbol: e.target.value.toUpperCase() })}
          placeholder="AAPL"
        />
      </Grid>
      <Grid item xs={6}>
        <TextField
          fullWidth
          size="small"
          label="Quantity"
          type="number"
          value={template.quantity || 100}
          onChange={(e) => onChange({ quantity: Number(e.target.value) })}
          InputProps={{ inputProps: { min: 1 } }}
        />
      </Grid>
      <Grid item xs={6}>
        <FormControl fullWidth size="small">
          <InputLabel>Order Type</InputLabel>
          <Select
            value={template.orderType || 'buy'}
            label="Order Type"
            onChange={(e) => onChange({ orderType: e.target.value as OrderType })}
          >
            <MenuItem value="buy">Buy</MenuItem>
            <MenuItem value="sell">Sell</MenuItem>
            <MenuItem value="buy_to_open">Buy to Open</MenuItem>
            <MenuItem value="sell_to_open">Sell to Open</MenuItem>
            <MenuItem value="buy_to_close">Buy to Close</MenuItem>
            <MenuItem value="sell_to_close">Sell to Close</MenuItem>
          </Select>
        </FormControl>
      </Grid>
      <Grid item xs={6}>
        <FormControl fullWidth size="small">
          <InputLabel>Condition</InputLabel>
          <Select
            value={template.condition || 'market'}
            label="Condition"
            onChange={(e) => onChange({ condition: e.target.value as OrderCondition })}
          >
            <MenuItem value="market">Market</MenuItem>
            <MenuItem value="limit">Limit</MenuItem>
            <MenuItem value="stop">Stop</MenuItem>
            <MenuItem value="stop_limit">Stop Limit</MenuItem>
          </Select>
        </FormControl>
      </Grid>
      {(template.condition === 'limit' || template.condition === 'stop_limit') && (
        <Grid item xs={6}>
          <TextField
            fullWidth
            size="small"
            label="Limit Price"
            type="number"
            value={template.price || ''}
            onChange={(e) => onChange({ price: Number(e.target.value) })}
            InputProps={{ inputProps: { step: 0.01 } }}
          />
        </Grid>
      )}
      {(template.condition === 'stop' || template.condition === 'stop_limit') && (
        <Grid item xs={6}>
          <TextField
            fullWidth
            size="small"
            label="Stop Price"
            type="number"
            value={template.stopPrice || ''}
            onChange={(e) => onChange({ stopPrice: Number(e.target.value) })}
            InputProps={{ inputProps: { step: 0.01 } }}
          />
        </Grid>
      )}
    </Grid>
  );

  return (
    <>
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <TemplateIcon color="primary" />
              <Typography variant="h6">Order Templates</Typography>
            </Box>
          }
          action={
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setShowCreateDialog(true)}
            >
              New Template
            </Button>
          }
          subheader={
            <Typography variant="body2" color="text.secondary">
              Save and reuse common order configurations
            </Typography>
          }
        />
        <CardContent>
          {templates.length > 0 ? (
            <List>
              {templates.map((template, index) => (
                <ListItem
                  key={template.id}
                  divider={index < templates.length - 1}
                  sx={{ 
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 1,
                    mb: 1,
                    '&:last-child': { mb: 0 }
                  }}
                >
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle2" fontWeight="bold">
                          {template.name}
                        </Typography>
                        <Chip 
                          label={template.orderType.replace('_', ' ').toUpperCase()}
                          size="small"
                          sx={{ 
                            backgroundColor: getOrderTypeColor(template.orderType),
                            color: 'white'
                          }}
                        />
                        <Chip 
                          label={getConditionLabel(template.condition)}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          {template.description || 'No description'}
                        </Typography>
                        <Box display="flex" gap={2} mt={1}>
                          <Typography variant="caption" color="text.secondary">
                            Qty: {template.quantity}
                          </Typography>
                          {template.symbol && (
                            <Typography variant="caption" color="text.secondary">
                              Symbol: {template.symbol}
                            </Typography>
                          )}
                          {template.price && (
                            <Typography variant="caption" color="text.secondary">
                              Price: ${template.price}
                            </Typography>
                          )}
                          <Typography variant="caption" color="text.secondary">
                            Used: {template.useCount} times
                          </Typography>
                        </Box>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Box display="flex" gap={1}>
                      <IconButton 
                        size="small" 
                        onClick={() => useTemplate(template)}
                        title="Use Template"
                      >
                        <UseIcon />
                      </IconButton>
                      <IconButton 
                        size="small" 
                        onClick={() => {
                          setEditingTemplate(template);
                          setShowEditDialog(true);
                        }}
                        title="Edit Template"
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton 
                        size="small" 
                        onClick={() => deleteTemplate(template.id)}
                        color="error"
                        title="Delete Template"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Box>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          ) : (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
              <Typography color="text.secondary">No order templates found</Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Create Template Dialog */}
      <Dialog open={showCreateDialog} onClose={() => setShowCreateDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Order Template</DialogTitle>
        <DialogContent sx={{ mt: 1 }}>
          {renderTemplateForm(newTemplate, (updates) => setNewTemplate(prev => ({ ...prev, ...updates })))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCreateDialog(false)}>Cancel</Button>
          <Button 
            onClick={createTemplate} 
            variant="contained"
            startIcon={<SaveIcon />}
            disabled={!newTemplate.name}
          >
            Save Template
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Template Dialog */}
      <Dialog open={showEditDialog} onClose={() => setShowEditDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Order Template</DialogTitle>
        <DialogContent sx={{ mt: 1 }}>
          {editingTemplate && renderTemplateForm(
            editingTemplate, 
            (updates) => setEditingTemplate(prev => prev ? { ...prev, ...updates } : null)
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowEditDialog(false)}>Cancel</Button>
          <Button 
            onClick={updateTemplate} 
            variant="contained"
            startIcon={<SaveIcon />}
            disabled={!editingTemplate?.name}
          >
            Update Template
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default OrderTemplates;