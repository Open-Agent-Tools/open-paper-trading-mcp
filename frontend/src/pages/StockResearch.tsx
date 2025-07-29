import React, { useState } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Paper,
  Button,
  Tabs,
  Tab,
  Alert,
} from '@mui/material';
import { 
  Search as SearchIcon,
  TrendingUp as TrendingUpIcon,
  ShowChart as ChartIcon,
  Assessment as RatingsIcon,
  AccountTree as OptionsIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import StockSearch from '../components/StockSearch';
import StockQuote from '../components/StockQuote';
import CompanyInfo from '../components/CompanyInfo';
import PriceHistoryChart from '../components/PriceHistoryChart';
import AnalystRatings from '../components/AnalystRatings';
import OptionsChain from '../components/OptionsChain';
import OptionGreeks from '../components/OptionGreeks';
import { useAccountContext } from '../contexts/AccountContext';
import type { StockSearchResult, OptionQuote } from '../types';

const StockResearch: React.FC = () => {
  const navigate = useNavigate();
  const { selectedAccount } = useAccountContext();
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [selectedOption, setSelectedOption] = useState<OptionQuote | null>(null);
  const [tabValue, setTabValue] = useState(0); // 0 = overview, 1 = charts, 2 = ratings, 3 = options

  const handleStockSelect = (stock: StockSearchResult) => {
    setSelectedStock(stock);
  };

  const handleCreateOrder = () => {
    if (selectedStock) {
      if (!selectedAccount) {
        // Show account selection prompt
        navigate('/', { 
          state: { 
            message: 'Please select an account to place trades',
            prefillSymbol: selectedStock.symbol 
          } 
        });
      } else {
        // Navigate to orders page with pre-filled symbol
        navigate('/orders', { 
          state: { 
            prefillSymbol: selectedStock.symbol 
          } 
        });
      }
    }
  };

  const handleOptionSelect = (option: OptionQuote) => {
    // Store selected option for Greeks display
    setSelectedOption(option);
  };

  const handleTradeOption = () => {
    if (selectedOption) {
      if (!selectedAccount) {
        // Show account selection prompt
        navigate('/', {
          state: {
            message: 'Please select an account to trade options',
            prefillSymbol: selectedOption.symbol,
            orderType: 'option'
          }
        });
      } else {
        // Navigate to orders page with pre-filled option symbol
        navigate('/orders', {
          state: {
            prefillSymbol: selectedOption.symbol,
            orderType: 'option'
          }
        });
      }
    }
  };

  return (
    <Container maxWidth={false} sx={{ py: 4 }}>
      {/* Header Section */}
      <Box mb={4}>
        <Typography variant="h3" component="h1" gutterBottom>
          Stock Research
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Search and research stocks to make informed trading decisions. 
          View company fundamentals, market metrics, and financial data.
        </Typography>
      </Box>

      {/* Account Context Warning */}
      {!selectedAccount && (
        <Alert 
          severity="info" 
          icon={<WarningIcon />}
          sx={{ mb: 3 }}
        >
          <Typography variant="body2">
            <strong>No account selected:</strong> You can research stocks without an account, 
            but you'll need to select a trading account to place orders.
          </Typography>
        </Alert>
      )}

      {/* Search Section */}
      <Box mb={4}>
        <Paper 
          sx={{ 
            p: 3, 
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
          }}
        >
          <Box display="flex" alignItems="center" gap={1} mb={2}>
            <SearchIcon color="primary" />
            <Typography variant="h6" fontWeight={500}>
              Search Stocks
            </Typography>
          </Box>
          
          <StockSearch 
            onSelectStock={handleStockSelect}
            placeholder="Search by symbol (e.g., AAPL) or company name..."
          />
          
          {selectedStock && (
            <Box mt={2} display="flex" alignItems="center" gap={2}>
              <Typography variant="body2" color="text.secondary">
                Selected:
              </Typography>
              <Typography variant="subtitle1" fontWeight={500}>
                {selectedStock.symbol} - {selectedStock.name}
              </Typography>
              {selectedStock.tradeable && (
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<TrendingUpIcon />}
                  onClick={handleCreateOrder}
                  sx={{ ml: 'auto' }}
                >
                  Trade {selectedStock.symbol}
                </Button>
              )}
            </Box>
          )}
        </Paper>
      </Box>

      {/* Research Data Tabs */}
      {selectedStock && (
        <Box mt={4}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
              <Tab label="Overview" icon={<TrendingUpIcon />} iconPosition="start" />
              <Tab label="Charts" icon={<ChartIcon />} iconPosition="start" />
              <Tab label="Ratings" icon={<RatingsIcon />} iconPosition="start" />
              <Tab label="Options" icon={<OptionsIcon />} iconPosition="start" />
            </Tabs>
          </Box>

          {/* Tab Content */}
          {tabValue === 0 && (
            <Grid container spacing={3}>
              {/* Stock Quote */}
              <Grid item xs={12} lg={6}>
                <StockQuote
                  symbol={selectedStock.symbol}
                  autoRefresh={true}
                  refreshInterval={30}
                />
              </Grid>
              
              {/* Company Information */}
              <Grid item xs={12} lg={6}>
                <CompanyInfo
                  symbol={selectedStock.symbol}
                />
              </Grid>
            </Grid>
          )}

          {tabValue === 1 && (
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <PriceHistoryChart
                  symbol={selectedStock.symbol}
                />
              </Grid>
            </Grid>
          )}

          {tabValue === 2 && (
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <AnalystRatings
                  symbol={selectedStock.symbol}
                />
              </Grid>
            </Grid>
          )}

          {tabValue === 3 && (
            <Grid container spacing={3}>
              <Grid item xs={12} lg={8}>
                <OptionsChain
                  symbol={selectedStock.symbol}
                  onOptionSelect={handleOptionSelect}
                />
              </Grid>
              {selectedOption && (
                <Grid item xs={12} lg={4}>
                  <OptionGreeks
                    optionSymbol={selectedOption.symbol}
                  />
                  <Box mt={2}>
                    <Button
                      variant="contained"
                      color="primary"
                      fullWidth
                      onClick={handleTradeOption}
                    >
                      Trade This Option
                    </Button>
                  </Box>
                </Grid>
              )}
            </Grid>
          )}
        </Box>
      )}

      {/* No Stock Selected Message */}
      {!selectedStock && (
        <Box mt={4}>
          <Paper 
            sx={{ 
              p: 6, 
              textAlign: 'center',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              backgroundColor: 'action.hover',
            }}
          >
            <Typography variant="h6" gutterBottom>
              Select a Stock to Begin Research
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Use the search above to find stocks and access price charts, analyst ratings, options chains, and more
            </Typography>
          </Paper>
        </Box>
      )}
    </Container>
  );
};

export default StockResearch;