import React, { useState, useCallback } from 'react';
import {
  Box,
  TextField,
  Autocomplete,
  Paper,
  Typography,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { searchStocks } from '../services/apiClient';
import type { StockSearchResult } from '../types';

interface StockSearchProps {
  onSelectStock?: (stock: StockSearchResult) => void;
  placeholder?: string;
  fullWidth?: boolean;
}

const StockSearch: React.FC<StockSearchProps> = ({
  onSelectStock,
  placeholder = "Search stocks by symbol or company name...",
  fullWidth = true,
}) => {
  const theme = useTheme();
  const [options, setOptions] = useState<StockSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState('');

  const searchHandler = useCallback(async (query: string) => {
    if (!query.trim() || query.length < 1) {
      setOptions([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await searchStocks(query);
      if (response.success && response.results.results) {
        setOptions(response.results.results);
      } else {
        setOptions([]);
        setError('No results found');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = (_: React.SyntheticEvent, value: string) => {
    setInputValue(value);
    
    // Debounce search
    const timeoutId = setTimeout(() => {
      searchHandler(value);
    }, 300);

    return () => clearTimeout(timeoutId);
  };

  const handleSelection = (_: React.SyntheticEvent, value: StockSearchResult | null) => {
    if (value && onSelectStock) {
      onSelectStock(value);
    }
  };

  return (
    <Box>
      <Autocomplete
        options={options}
        getOptionLabel={(option) => `${option.symbol} - ${option.name}`}
        loading={loading}
        fullWidth={fullWidth}
        inputValue={inputValue}
        onInputChange={handleInputChange}
        onChange={handleSelection}
        filterOptions={(x) => x} // Disable client-side filtering since we search server-side
        renderInput={(params) => (
          <TextField
            {...params}
            placeholder={placeholder}
            variant="outlined"
            InputProps={{
              ...params.InputProps,
              startAdornment: <SearchIcon sx={{ color: 'action.active', mr: 1 }} />,
              endAdornment: (
                <>
                  {loading ? <CircularProgress color="inherit" size={20} /> : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: theme.palette.background.paper,
                '&:hover': {
                  backgroundColor: theme.palette.action.hover,
                },
                '&.Mui-focused': {
                  backgroundColor: theme.palette.background.paper,
                },
              },
            }}
          />
        )}
        renderOption={(props, option) => (
          <Box component="li" {...props}>
            <Box display="flex" alignItems="center" width="100%">
              <Typography
                variant="subtitle1"
                sx={{
                  fontWeight: 500,
                  color: theme.palette.primary.main,
                  minWidth: 80,
                  mr: 2,
                }}
              >
                {option.symbol}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ flexGrow: 1 }}
              >
                {option.name}
              </Typography>
              {option.tradeable && (
                <Chip
                  label="Tradeable"
                  size="small"
                  color="success"
                  sx={{ ml: 1 }}
                />
              )}
            </Box>
          </Box>
        )}
        PaperComponent={({ children, ...props }) => (
          <Paper
            {...props}
            sx={{
              mt: 1,
              boxShadow: theme.shadows[8],
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            {children}
          </Paper>
        )}
        noOptionsText={
          inputValue.length === 0 
            ? "Start typing to search stocks..." 
            : "No stocks found"
        }
      />
      
      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default StockSearch;