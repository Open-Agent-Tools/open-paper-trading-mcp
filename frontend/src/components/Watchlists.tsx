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
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tabs,
  Tab,
  useTheme,
} from '@mui/material';
import {
  Visibility as WatchIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useAccountContext } from '../contexts/AccountContext';
import { searchStocks, getStockPrice } from '../services/apiClient';
import type { StockSearchResult } from '../types';

interface WatchlistItem {
  symbol: string;
  name: string;
  addedAt: string;
  price?: number;
  change?: number;
  changePercent?: number;
  lastUpdated?: string;
}

interface Watchlist {
  id: string;
  name: string;
  description?: string;
  items: WatchlistItem[];
  createdAt: string;
}

const Watchlists: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedWatchlist, setSelectedWatchlist] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [priceLoading, setPriceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Dialog states
  const [showCreateWatchlistDialog, setShowCreateWatchlistDialog] = useState(false);
  const [showAddStockDialog, setShowAddStockDialog] = useState(false);
  const [newWatchlistName, setNewWatchlistName] = useState('');
  const [newWatchlistDescription, setNewWatchlistDescription] = useState('');
  const [stockSearchQuery, setStockSearchQuery] = useState('');
  const [stockSearchResults, setStockSearchResults] = useState<StockSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Load watchlists from localStorage
  const loadWatchlists = () => {
    try {
      const savedWatchlists = localStorage.getItem(`watchlists_${selectedAccount?.id || 'default'}`);
      if (savedWatchlists) {
        const parsed = JSON.parse(savedWatchlists);
        setWatchlists(parsed);
        if (parsed.length > 0 && !selectedWatchlist) {
          setSelectedWatchlist(parsed[0].id);
        }
      } else {
        // Create a default watchlist
        const defaultWatchlist: Watchlist = {
          id: '1',
          name: 'My Stocks',
          description: 'Default watchlist',
          items: [
            {
              symbol: 'AAPL',
              name: 'Apple Inc.',
              addedAt: new Date().toISOString()
            },
            {
              symbol: 'MSFT',
              name: 'Microsoft Corporation',
              addedAt: new Date().toISOString()
            },
            {
              symbol: 'GOOGL',
              name: 'Alphabet Inc.',
              addedAt: new Date().toISOString()
            }
          ],
          createdAt: new Date().toISOString()
        };
        const defaultWatchlists = [defaultWatchlist];
        setWatchlists(defaultWatchlists);
        setSelectedWatchlist(defaultWatchlist.id);
        saveWatchlists(defaultWatchlists);
      }
    } catch (err) {
      console.error('Failed to load watchlists:', err);
    }
  };

  const saveWatchlists = (watchlistsToSave: Watchlist[]) => {
    try {
      localStorage.setItem(
        `watchlists_${selectedAccount?.id || 'default'}`,
        JSON.stringify(watchlistsToSave)
      );
    } catch (err) {
      console.error('Failed to save watchlists:', err);
    }
  };

  const createWatchlist = () => {
    if (!newWatchlistName.trim()) return;

    const newWatchlist: Watchlist = {
      id: Date.now().toString(),
      name: newWatchlistName.trim(),
      description: newWatchlistDescription.trim(),
      items: [],
      createdAt: new Date().toISOString()
    };

    const updatedWatchlists = [...watchlists, newWatchlist];
    setWatchlists(updatedWatchlists);
    saveWatchlists(updatedWatchlists);
    setSelectedWatchlist(newWatchlist.id);
    setNewWatchlistName('');
    setNewWatchlistDescription('');
    setShowCreateWatchlistDialog(false);
  };

  const deleteWatchlist = (watchlistId: string) => {
    const updatedWatchlists = watchlists.filter(w => w.id !== watchlistId);
    setWatchlists(updatedWatchlists);
    saveWatchlists(updatedWatchlists);
    
    if (selectedWatchlist === watchlistId) {
      setSelectedWatchlist(updatedWatchlists.length > 0 ? updatedWatchlists[0].id : '');
    }
  };

  const searchStocksForWatchlist = async () => {
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

  const addStockToWatchlist = (stock: StockSearchResult) => {
    const currentWatchlist = watchlists.find(w => w.id === selectedWatchlist);
    if (!currentWatchlist) return;

    // Check if stock already exists
    if (currentWatchlist.items.some(item => item.symbol === stock.symbol)) {
      return; // Already in watchlist
    }

    const newItem: WatchlistItem = {
      symbol: stock.symbol,
      name: stock.name,
      addedAt: new Date().toISOString()
    };

    const updatedWatchlist = {
      ...currentWatchlist,
      items: [...currentWatchlist.items, newItem]
    };

    const updatedWatchlists = watchlists.map(w => 
      w.id === selectedWatchlist ? updatedWatchlist : w
    );

    setWatchlists(updatedWatchlists);
    saveWatchlists(updatedWatchlists);
    setShowAddStockDialog(false);
    setStockSearchQuery('');
    setStockSearchResults([]);
  };

  const removeStockFromWatchlist = (symbol: string) => {
    const currentWatchlist = watchlists.find(w => w.id === selectedWatchlist);
    if (!currentWatchlist) return;

    const updatedWatchlist = {
      ...currentWatchlist,
      items: currentWatchlist.items.filter(item => item.symbol !== symbol)
    };

    const updatedWatchlists = watchlists.map(w => 
      w.id === selectedWatchlist ? updatedWatchlist : w
    );

    setWatchlists(updatedWatchlists);
    saveWatchlists(updatedWatchlists);
  };

  const refreshPrices = async () => {
    const currentWatchlist = watchlists.find(w => w.id === selectedWatchlist);
    if (!currentWatchlist || currentWatchlist.items.length === 0) return;

    setPriceLoading(true);
    try {
      const pricePromises = currentWatchlist.items.map(async (item) => {
        try {
          const response = await getStockPrice(item.symbol);
          if (response.success && response.price_data) {
            return {
              ...item,
              price: response.price_data.price,
              change: response.price_data.change,
              changePercent: response.price_data.change_percent,
              lastUpdated: new Date().toISOString()
            };
          }
        } catch (err) {
          console.warn(`Failed to fetch price for ${item.symbol}:`, err);
        }
        return item;
      });

      const updatedItems = await Promise.all(pricePromises);
      
      const updatedWatchlist = {
        ...currentWatchlist,
        items: updatedItems
      };

      const updatedWatchlists = watchlists.map(w => 
        w.id === selectedWatchlist ? updatedWatchlist : w
      );

      setWatchlists(updatedWatchlists);
      saveWatchlists(updatedWatchlists);
    } catch (err) {
      setError('Failed to refresh prices');
    } finally {
      setPriceLoading(false);
    }
  };

  useEffect(() => {
    loadWatchlists();
  }, [selectedAccount]);

  useEffect(() => {
    if (stockSearchQuery.length >= 2) {
      const debounceTimer = setTimeout(() => {
        searchStocksForWatchlist();
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

  const formatPercent = (value: number | undefined) => {
    if (!value) return 'N/A';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getTrendIcon = (change: number | undefined) => {
    if (!change) return <TrendingFlat color="disabled" fontSize="small" />;
    if (change > 0) return <TrendingUp color="success" fontSize="small" />;
    if (change < 0) return <TrendingDown color="error" fontSize="small" />;
    return <TrendingFlat color="disabled" fontSize="small" />;
  };

  const getTrendColor = (change: number | undefined) => {
    if (!change) return theme.palette.text.secondary;
    if (change > 0) return theme.palette.success.main;
    if (change < 0) return theme.palette.error.main;
    return theme.palette.text.secondary;
  };

  const currentWatchlist = watchlists.find(w => w.id === selectedWatchlist);

  return (
    <>
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <WatchIcon color="primary" />
              <Typography variant="h6">Watchlists</Typography>
            </Box>
          }
          action={
            <Box display="flex" gap={1}>
              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => setShowCreateWatchlistDialog(true)}
              >
                New List
              </Button>
              <IconButton 
                onClick={refreshPrices} 
                disabled={priceLoading || !currentWatchlist?.items.length}
                title="Refresh Prices"
              >
                <RefreshIcon />
              </IconButton>
            </Box>
          }
          subheader={
            <Typography variant="body2" color="text.secondary">
              Track and monitor your favorite stocks
            </Typography>
          }
        />
        <CardContent>
          {/* Watchlist Tabs */}
          {watchlists.length > 0 && (
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
              <Tabs 
                value={selectedWatchlist} 
                onChange={(_, newValue) => setSelectedWatchlist(newValue)}
                variant="scrollable"
                scrollButtons="auto"
              >
                {watchlists.map((watchlist) => (
                  <Tab 
                    key={watchlist.id}
                    label={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography>{watchlist.name}</Typography>
                        <Chip 
                          label={watchlist.items.length} 
                          size="small" 
                          variant="outlined"
                        />
                        {watchlists.length > 1 && (
                          <IconButton 
                            size="small" 
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteWatchlist(watchlist.id);
                            }}
                            sx={{ ml: 1, p: 0.5 }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        )}
                      </Box>
                    }
                    value={watchlist.id}
                  />
                ))}
              </Tabs>
            </Box>
          )}

          {/* Current Watchlist Content */}
          {currentWatchlist ? (
            <Box>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="subtitle1">
                  {currentWatchlist.name} ({currentWatchlist.items.length} stocks)
                </Typography>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => setShowAddStockDialog(true)}
                >
                  Add Stock
                </Button>
              </Box>

              {currentWatchlist.items.length > 0 ? (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell>Company</TableCell>
                        <TableCell align="right">Price</TableCell>
                        <TableCell align="right">Change</TableCell>
                        <TableCell align="right">Change %</TableCell>
                        <TableCell>Updated</TableCell>
                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {currentWatchlist.items.map((item) => (
                        <TableRow key={item.symbol} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight="bold">
                              {item.symbol}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {item.name}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                              {formatCurrency(item.price)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Box display="flex" alignItems="center" justifyContent="flex-end" gap={0.5}>
                              {getTrendIcon(item.change)}
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  fontFamily: 'Roboto Mono, monospace',
                                  color: getTrendColor(item.change)
                                }}
                              >
                                {formatCurrency(item.change)}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell align="right">
                            <Typography 
                              variant="body2" 
                              sx={{ 
                                fontFamily: 'Roboto Mono, monospace',
                                color: getTrendColor(item.change)
                              }}
                            >
                              {formatPercent(item.changePercent)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {item.lastUpdated 
                                ? new Date(item.lastUpdated).toLocaleTimeString()
                                : 'Never'
                              }
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            <IconButton 
                              size="small" 
                              onClick={() => removeStockFromWatchlist(item.symbol)}
                              color="error"
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
                  <Typography color="text.secondary">No stocks in this watchlist</Typography>
                </Box>
              )}
            </Box>
          ) : (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
              <Typography color="text.secondary">Create a watchlist to get started</Typography>
            </Box>
          )}

          {priceLoading && (
            <Box display="flex" justifyContent="center" mt={2}>
              <CircularProgress size={20} />
              <Typography variant="body2" sx={{ ml: 1 }}>Updating prices...</Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Create Watchlist Dialog */}
      <Dialog open={showCreateWatchlistDialog} onClose={() => setShowCreateWatchlistDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Watchlist</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Watchlist Name"
            fullWidth
            variant="outlined"
            value={newWatchlistName}
            onChange={(e) => setNewWatchlistName(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Description (Optional)"
            fullWidth
            variant="outlined"
            multiline
            rows={2}
            value={newWatchlistDescription}
            onChange={(e) => setNewWatchlistDescription(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCreateWatchlistDialog(false)}>Cancel</Button>
          <Button 
            onClick={createWatchlist} 
            variant="contained"
            disabled={!newWatchlistName.trim()}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Stock Dialog */}
      <Dialog open={showAddStockDialog} onClose={() => setShowAddStockDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Stock to Watchlist</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Search Stocks"
            fullWidth
            variant="outlined"
            value={stockSearchQuery}
            onChange={(e) => setStockSearchQuery(e.target.value.toUpperCase())}
            placeholder="Enter symbol or company name (e.g., AAPL, Apple)"
            sx={{ mb: 2 }}
          />
          
          {searchLoading && (
            <Box display="flex" justifyContent="center" my={2}>
              <CircularProgress size={20} />
            </Box>
          )}

          {stockSearchResults.length > 0 && (
            <List sx={{ maxHeight: 300, overflow: 'auto' }}>
              {stockSearchResults.slice(0, 10).map((stock) => (
                <ListItem 
                  key={stock.symbol}
                  button
                  onClick={() => addStockToWatchlist(stock)}
                  disabled={currentWatchlist?.items.some(item => item.symbol === stock.symbol)}
                >
                  <ListItemText
                    primary={stock.name}
                    secondary={stock.symbol}
                  />
                  <ListItemSecondaryAction>
                    {currentWatchlist?.items.some(item => item.symbol === stock.symbol) ? (
                      <Chip label="Added" size="small" color="success" />
                    ) : (
                      <Button size="small" onClick={() => addStockToWatchlist(stock)}>
                        Add
                      </Button>
                    )}
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAddStockDialog(false)}>Done</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default Watchlists;