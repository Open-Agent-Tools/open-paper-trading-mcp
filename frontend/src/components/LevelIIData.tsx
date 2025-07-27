import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Alert,
  Chip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
} from '@mui/material';
import {
  Analytics as Level2Icon,
  Lock as LockIcon,
  Star as GoldIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { FONTS } from '../theme';

interface LevelIIDataProps {
  symbol: string;
  hasGoldSubscription?: boolean;
}

// Mock Level II data structure for display purposes
interface OrderBookEntry {
  price: number;
  size: number;
  market_maker?: string;
}

const LevelIIData: React.FC<LevelIIDataProps> = ({ 
  symbol,
  hasGoldSubscription = false 
}) => {
  const theme = useTheme();
  const [showUpgrade, setShowUpgrade] = useState(false);

  // Mock data for demonstration (would come from API in real implementation)
  const mockBids: OrderBookEntry[] = [
    { price: 150.25, size: 500, market_maker: 'NSDQ' },
    { price: 150.24, size: 1200, market_maker: 'ARCA' },
    { price: 150.23, size: 800, market_maker: 'NYSE' },
    { price: 150.22, size: 300, market_maker: 'BATS' },
    { price: 150.21, size: 1500, market_maker: 'IEX' },
  ];

  const mockAsks: OrderBookEntry[] = [
    { price: 150.26, size: 400, market_maker: 'NSDQ' },
    { price: 150.27, size: 900, market_maker: 'ARCA' },
    { price: 150.28, size: 600, market_maker: 'NYSE' },
    { price: 150.29, size: 1100, market_maker: 'BATS' },
    { price: 150.30, size: 750, market_maker: 'IEX' },
  ];

  const formatPrice = (price: number): string => `$${price.toFixed(2)}`;
  const formatSize = (size: number): string => size.toLocaleString();

  const renderOrderBook = (orders: OrderBookEntry[], type: 'bid' | 'ask') => {
    const maxSize = Math.max(...orders.map(o => o.size));
    const color = type === 'bid' ? theme.palette.success.main : theme.palette.error.main;

    return (
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{type === 'bid' ? 'Bid' : 'Ask'}</TableCell>
              <TableCell align="right">Size</TableCell>
              <TableCell align="center">Market</TableCell>
              <TableCell align="right">Depth</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orders.map((order, index) => (
              <TableRow key={index}>
                <TableCell>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontFamily: FONTS.monospace,
                      color: color,
                      fontWeight: 500
                    }}
                  >
                    {formatPrice(order.price)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" sx={{ fontFamily: FONTS.monospace }}>
                    {formatSize(order.size)}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Chip 
                    label={order.market_maker} 
                    size="small" 
                    variant="outlined"
                    sx={{ fontSize: '0.7rem' }}
                  />
                </TableCell>
                <TableCell align="right" sx={{ width: 60 }}>
                  <Box position="relative">
                    <LinearProgress
                      variant="determinate"
                      value={(order.size / maxSize) * 100}
                      sx={{
                        height: 8,
                        borderRadius: 1,
                        backgroundColor: 'rgba(0,0,0,0.1)',
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: color,
                          opacity: 0.6
                        }
                      }}
                    />
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  if (!hasGoldSubscription) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <Level2Icon color="disabled" />
              <Typography variant="h6" color="text.secondary">
                Level II Market Data
              </Typography>
              <LockIcon color="disabled" fontSize="small" />
            </Box>
          }
        />
        
        <CardContent>
          <Alert 
            severity="info" 
            sx={{ mb: 2 }}
            action={
              <Button 
                color="inherit" 
                size="small"
                startIcon={<GoldIcon />}
                onClick={() => setShowUpgrade(true)}
              >
                Upgrade
              </Button>
            }
          >
            Level II market data requires Robinhood Gold subscription
          </Alert>

          <Box sx={{ opacity: 0.3, pointerEvents: 'none' }}>
            <Typography variant="h6" gutterBottom>
              {symbol} Order Book Preview
            </Typography>
            
            <Box display="flex" gap={2}>
              <Box flex={1}>
                <Typography variant="subtitle2" color="success.main" gutterBottom>
                  Bids
                </Typography>
                {renderOrderBook(mockBids.slice(0, 3), 'bid')}
              </Box>
              
              <Box flex={1}>
                <Typography variant="subtitle2" color="error.main" gutterBottom>
                  Asks
                </Typography>
                {renderOrderBook(mockAsks.slice(0, 3), 'ask')}
              </Box>
            </Box>
          </Box>

          {showUpgrade && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              <Typography variant="body2">
                <strong>Robinhood Gold Features:</strong><br/>
                • Level II market data with order book depth<br/>
                • Market maker identification<br/>
                • Real-time bid/ask sizes<br/>
                • Professional trading tools
              </Typography>
              <Button 
                variant="contained" 
                size="small" 
                sx={{ mt: 1 }}
                startIcon={<GoldIcon />}
              >
                Learn More About Gold
              </Button>
            </Alert>
          )}

          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
            Level II data shows market depth and liquidity • Requires Gold subscription
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Full Level II component for Gold subscribers (would integrate with real API)
  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <Level2Icon color="primary" />
            <Typography variant="h6">
              Level II Market Data
            </Typography>
            <Chip 
              label="Gold" 
              size="small" 
              color="warning" 
              icon={<GoldIcon />}
            />
          </Box>
        }
        subheader={
          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: FONTS.monospace }}>
            {symbol} • Real-time order book
          </Typography>
        }
      />
      
      <CardContent>
        <Box display="flex" gap={2}>
          <Box flex={1}>
            <Typography variant="subtitle2" color="success.main" gutterBottom>
              Bids
            </Typography>
            {renderOrderBook(mockBids, 'bid')}
          </Box>
          
          <Box flex={1}>
            <Typography variant="subtitle2" color="error.main" gutterBottom>
              Asks
            </Typography>
            {renderOrderBook(mockAsks, 'ask')}
          </Box>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
          Real-time Level II data • Market maker identification • Order book depth
        </Typography>
      </CardContent>
    </Card>
  );
};

export default LevelIIData;