import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Alert,
  CircularProgress,
  IconButton,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Assessment as AssessmentIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { getStockRatings } from '../services/apiClient';
import type { StockRatingsData } from '../types';

interface AnalystRatingsProps {
  symbol: string;
  onLoadingChange?: (loading: boolean) => void;
}

const AnalystRatings: React.FC<AnalystRatingsProps> = ({ 
  symbol, 
  onLoadingChange 
}) => {
  const theme = useTheme();
  const [ratingsData, setRatingsData] = useState<StockRatingsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStockRatings = async () => {
    if (!symbol) {
      setRatingsData(null);
      return;
    }

    setLoading(true);
    setError(null);
    onLoadingChange?.(true);

    try {
      const response = await getStockRatings(symbol);
      if (response.success) {
        setRatingsData(response.ratings);
      } else {
        setError('Failed to load analyst ratings');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analyst ratings');
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    fetchStockRatings();
  }, [symbol]);


  const getRatingChipColor = (rating: string): 'success' | 'error' | 'warning' => {
    const lowerRating = rating.toLowerCase();
    if (lowerRating.includes('buy')) return 'success';
    if (lowerRating.includes('sell')) return 'error';
    return 'warning';
  };

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  if (loading && !ratingsData) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading analyst ratings...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <AssessmentIcon color="primary" />
              <Typography variant="h6">
                {symbol} Analyst Ratings
              </Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchStockRatings} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="info">
            {error}. Analyst ratings may not be available for this symbol or require a subscription.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!ratingsData) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Select a stock to view analyst ratings
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Handle the actual API response structure
  const ratingsBreakdown = ratingsData.ratings_breakdown || {};
  const priceTargets = ratingsData.price_targets || {};
  
  // Calculate total ratings and simplified breakdown
  const buyCount = (ratingsBreakdown.strong_buy || 0) + (ratingsBreakdown.buy || 0);
  const holdCount = ratingsBreakdown.hold || 0;
  const sellCount = (ratingsBreakdown.sell || 0) + (ratingsBreakdown.strong_sell || 0);
  const totalRatings = buyCount + holdCount + sellCount;
  
  // Create summary object from API data
  const summary = {
    buy: buyCount,
    hold: holdCount,
    sell: sellCount,
    average_rating: ratingsData.overall_rating || 'N/A',
    target_price: priceTargets.average_target || 0
  };

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <AssessmentIcon color="primary" />
            <Typography variant="h6">
              {symbol} Analyst Ratings
            </Typography>
            <Chip
              label={summary.average_rating}
              size="small"
              color={getRatingChipColor(summary.average_rating)}
            />
          </Box>
        }
        action={
          <IconButton onClick={fetchStockRatings} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
        subheader={
          <Typography variant="body2" color="text.secondary">
            {ratingsData.analyst_count || totalRatings} analyst{(ratingsData.analyst_count || totalRatings) !== 1 ? 's' : ''} • Target: ${summary.target_price.toFixed(2)}
          </Typography>
        }
      />
      
      <CardContent>
        {/* Ratings Summary */}
        <Grid container spacing={3} mb={3}>
          {/* Buy */}
          <Grid item xs={4}>
            <Box textAlign="center">
              <Typography variant="h4" color="success.main" sx={{ fontWeight: 'bold' }}>
                {summary.buy}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Buy
              </Typography>
              {totalRatings > 0 && (
                <LinearProgress
                  variant="determinate"
                  value={(summary.buy / totalRatings) * 100}
                  color="success"
                  sx={{ mt: 1, height: 6, borderRadius: 3 }}
                />
              )}
            </Box>
          </Grid>
          
          {/* Hold */}
          <Grid item xs={4}>
            <Box textAlign="center">
              <Typography variant="h4" color="warning.main" sx={{ fontWeight: 'bold' }}>
                {summary.hold}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Hold
              </Typography>
              {totalRatings > 0 && (
                <LinearProgress
                  variant="determinate"
                  value={(summary.hold / totalRatings) * 100}
                  color="warning"
                  sx={{ mt: 1, height: 6, borderRadius: 3 }}
                />
              )}
            </Box>
          </Grid>
          
          {/* Sell */}
          <Grid item xs={4}>
            <Box textAlign="center">
              <Typography variant="h4" color="error.main" sx={{ fontWeight: 'bold' }}>
                {summary.sell}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Sell
              </Typography>
              {totalRatings > 0 && (
                <LinearProgress
                  variant="determinate"
                  value={(summary.sell / totalRatings) * 100}
                  color="error"
                  sx={{ mt: 1, height: 6, borderRadius: 3 }}
                />
              )}
            </Box>
          </Grid>
        </Grid>

        {/* Target Price */}
        <Box 
          display="flex" 
          alignItems="center" 
          justifyContent="center" 
          gap={1} 
          mb={3}
          p={2}
          sx={{ 
            backgroundColor: theme.palette.action.hover,
            borderRadius: 2 
          }}
        >
          <TrendingUpIcon color="primary" />
          <Typography variant="h6">
            Target Price:
          </Typography>
          <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace', color: 'primary.main' }}>
            ${summary.target_price.toFixed(2)}
          </Typography>
        </Box>

        {/* Price Target Details */}
        <Box>
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
            Price Target Range
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={3}>
              <Box textAlign="center" p={2} sx={{ backgroundColor: theme.palette.action.hover, borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">High</Typography>
                <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                  ${priceTargets.high_target?.toFixed(2) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={3}>
              <Box textAlign="center" p={2} sx={{ backgroundColor: theme.palette.action.hover, borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">Median</Typography>
                <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                  ${priceTargets.median_target?.toFixed(2) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={3}>
              <Box textAlign="center" p={2} sx={{ backgroundColor: theme.palette.action.hover, borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">Low</Typography>
                <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                  ${priceTargets.low_target?.toFixed(2) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={3}>
              <Box textAlign="center" p={2} sx={{ backgroundColor: theme.palette.primary.main, borderRadius: 1 }}>
                <Typography variant="body2" sx={{ color: 'white' }}>Score</Typography>
                <Typography variant="h6" sx={{ fontFamily: 'Roboto Mono, monospace', color: 'white' }}>
                  {ratingsData.rating_score?.toFixed(1) || 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Box>

        {/* Individual Ratings Table - Show if legacy ratings data is available */}
        {ratingsData.ratings && ratingsData.ratings.length > 0 && (
          <Box mt={3}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
              Recent Ratings
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Firm</TableCell>
                    <TableCell>Rating</TableCell>
                    <TableCell align="right">Target Price</TableCell>
                    <TableCell align="right">Date</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {ratingsData.ratings.slice(0, 10).map((rating, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {rating.firm}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={rating.rating}
                          size="small"
                          color={getRatingChipColor(rating.rating)}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                          ${rating.target_price.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" color="text.secondary">
                          {formatDate(rating.date)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            
            {ratingsData.ratings.length > 10 && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Showing 10 of {ratingsData.ratings.length} ratings
              </Typography>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default AnalystRatings;