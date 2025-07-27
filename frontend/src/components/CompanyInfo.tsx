import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Grid,
  Chip,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Business as BusinessIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getStockInfo } from '../services/apiClient';
import type { StockInfo } from '../types';

interface CompanyInfoProps {
  symbol: string;
  onLoadingChange?: (loading: boolean) => void;
}

const CompanyInfo: React.FC<CompanyInfoProps> = ({ 
  symbol, 
  onLoadingChange 
}) => {
  const theme = useTheme();
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStockInfo = async () => {
      if (!symbol) {
        setStockInfo(null);
        return;
      }

      setLoading(true);
      setError(null);
      onLoadingChange?.(true);

      try {
        const response = await getStockInfo(symbol);
        if (response.success) {
          setStockInfo(response.info);
        } else {
          setError('Failed to load company information');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load company information');
      } finally {
        setLoading(false);
        onLoadingChange?.(false);
      }
    };

    fetchStockInfo();
  }, [symbol, onLoadingChange]);

  const formatCurrency = (value: string): string => {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    
    if (num >= 1e12) return `$${(num / 1e12).toFixed(1)}T`;
    if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
    
    return `$${num.toLocaleString()}`;
  };

  const formatNumber = (value: string): string => {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    return num.toLocaleString();
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading company information...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        {error}
      </Alert>
    );
  }

  if (!stockInfo) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Select a stock to view company information
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <BusinessIcon color="primary" />
            <Typography variant="h6">
              {stockInfo.symbol} - {stockInfo.company_name}
            </Typography>
            {stockInfo.tradeable && (
              <Chip
                label="Tradeable"
                size="small"
                color="success"
                sx={{ ml: 1 }}
              />
            )}
          </Box>
        }
        subheader={`${stockInfo.sector} • ${stockInfo.industry}`}
      />
      
      <CardContent>
        <Typography variant="body2" color="text.secondary" paragraph>
          {stockInfo.description}
        </Typography>

        <Divider sx={{ my: 2 }} />

        <Grid container spacing={3}>
          {/* Market Metrics */}
          <Grid item xs={12} md={6}>
            <Box>
              <Typography 
                variant="subtitle1" 
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1, 
                  mb: 2,
                  fontWeight: 500,
                }}
              >
                <AssessmentIcon fontSize="small" color="primary" />
                Market Metrics
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Market Cap
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatCurrency(stockInfo.market_cap)}
                  </Typography>
                </Grid>
                
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    P/E Ratio
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {stockInfo.pe_ratio}
                  </Typography>
                </Grid>
                
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Dividend Yield
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {parseFloat(stockInfo.dividend_yield).toFixed(2)}%
                  </Typography>
                </Grid>
                
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Average Volume
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                    {formatNumber(stockInfo.average_volume)}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          </Grid>

          {/* Price Range */}
          <Grid item xs={12} md={6}>
            <Box>
              <Typography 
                variant="subtitle1" 
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1, 
                  mb: 2,
                  fontWeight: 500,
                }}
              >
                <TrendingUpIcon fontSize="small" color="primary" />
                52-Week Range
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    52-Week Low
                  </Typography>
                  <Typography 
                    variant="h6" 
                    sx={{ 
                      fontFamily: 'Roboto Mono, monospace',
                      color: theme.palette.error.main,
                    }}
                  >
                    ${parseFloat(stockInfo.low_52_weeks).toFixed(2)}
                  </Typography>
                </Grid>
                
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    52-Week High
                  </Typography>
                  <Typography 
                    variant="h6" 
                    sx={{ 
                      fontFamily: 'Roboto Mono, monospace',
                      color: theme.palette.success.main,
                    }}
                  >
                    ${parseFloat(stockInfo.high_52_weeks).toFixed(2)}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default CompanyInfo;