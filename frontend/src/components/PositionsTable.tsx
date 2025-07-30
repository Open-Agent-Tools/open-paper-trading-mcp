import React, { useEffect, useState } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef, GridValueFormatterParams } from '@mui/x-data-grid';
import { CircularProgress, Alert, Paper, Typography, Box } from '@mui/material';
import { getPositions } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';
import type { Position } from '../types';

// Enhanced Position interface with unique ID for DataGrid
interface PositionWithId extends Position {
  uniqueId: string;
}

// Generate unique ID for each position row
const generateUniqueId = (position: Position): string => {
  const baseId = position.symbol;
  
  // For options, include strike and expiration to ensure uniqueness
  if (position.strike && position.expiration_date) {
    return `${baseId}_${position.strike}_${position.expiration_date.replace(/-/g, '')}`;
  }
  
  // For stocks or positions without options data, use symbol with asset type
  return `${baseId}_${position.asset_type || 'stock'}`;
};

const columns: GridColDef[] = [
  { field: 'symbol', headerName: 'Symbol', width: 120 },
  { 
    field: 'asset_type', 
    headerName: 'Type', 
    width: 80,
    valueFormatter: (params: GridValueFormatterParams) => {
      const value = params.value as string;
      return value ? value.toUpperCase() : 'STOCK';
    }
  },
  { field: 'quantity', headerName: 'Quantity', type: 'number', width: 100 },
  { 
    field: 'avg_price', 
    headerName: 'Avg Price', 
    type: 'number', 
    width: 120, 
    valueFormatter: (params: GridValueFormatterParams) => 
      params.value ? `$${(params.value as number).toFixed(2)}` : '-'
  },
  { 
    field: 'current_price', 
    headerName: 'Current Price', 
    type: 'number', 
    width: 130, 
    valueFormatter: (params: GridValueFormatterParams) => 
      params.value ? `$${(params.value as number).toFixed(2)}` : '-'
  },
  { 
    field: 'market_value', 
    headerName: 'Market Value', 
    type: 'number', 
    width: 130, 
    valueFormatter: (params: GridValueFormatterParams) => 
      params.value ? `$${(params.value as number).toLocaleString()}` : '-'
  },
  { 
    field: 'unrealized_pnl', 
    headerName: 'P&L', 
    type: 'number', 
    width: 120, 
    valueFormatter: (params: GridValueFormatterParams) => {
      if (!params.value) return '-';
      const value = params.value as number;
      const sign = value >= 0 ? '+' : '';
      return `${sign}$${value.toFixed(2)}`;
    },
    cellClassName: (params) => {
      if (!params.value) return '';
      return (params.value as number) >= 0 ? 'profit' : 'loss';
    }
  },
  { 
    field: 'unrealized_pnl_percent', 
    headerName: 'P&L %', 
    type: 'number', 
    width: 100, 
    valueFormatter: (params: GridValueFormatterParams) => {
      if (!params.value) return '-';
      const value = params.value as number;
      const sign = value >= 0 ? '+' : '';
      return `${sign}${value.toFixed(2)}%`;
    },
    cellClassName: (params) => {
      if (!params.value) return '';
      return (params.value as number) >= 0 ? 'profit' : 'loss';
    }
  },
  { 
    field: 'strike', 
    headerName: 'Strike', 
    type: 'number', 
    width: 90, 
    valueFormatter: (params: GridValueFormatterParams) => 
      params.value ? `$${(params.value as number).toFixed(2)}` : '-'
  },
  { 
    field: 'expiration_date', 
    headerName: 'Expiry', 
    width: 100, 
    valueFormatter: (params: GridValueFormatterParams) => {
      if (!params.value) return '-';
      const date = new Date(params.value as string);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
    }
  },
];

const PositionsTable: React.FC = () => {
  const [positions, setPositions] = useState<PositionWithId[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { selectedAccount } = useAccountContext();

  useEffect(() => {
    const fetchPositions = async () => {
      if (!selectedAccount) {
        setPositions([]);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await getPositions(selectedAccount.id);
        
        // Extract positions array from the response and add unique IDs
        const positionsWithIds: PositionWithId[] = (data.positions || []).map((position: Position) => ({
          ...position,
          uniqueId: generateUniqueId(position)
        }));
        
        setPositions(positionsWithIds);
      } catch (err) {
        setError('Failed to fetch positions. Please try again later.');
        console.error('Error fetching positions:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();
  }, [selectedAccount]);

  if (loading) {
    return (
      <Paper style={{ height: 400, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper style={{ height: 400, width: '100%' }}>
        <Box sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Positions
          </Typography>
          <Alert severity="error">{error}</Alert>
        </Box>
      </Paper>
    );
  }

  // Handle empty positions
  if (!positions || positions.length === 0) {
    return (
      <Paper style={{ height: 400, width: '100%' }}>
        <Typography variant="h6" gutterBottom sx={{ p: 2 }}>
          Positions
        </Typography>
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
          <Typography variant="body1" color="text.secondary">
            No positions found. Start trading to see your positions here.
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper style={{ height: 400, width: '100%' }}>
        <Typography variant="h6" gutterBottom sx={{ p: 2}}>
            Positions
        </Typography>
      <Box sx={{ 
        height: 350, 
        width: '100%',
        '& .profit': {
          color: 'success.main',
          fontWeight: 'bold',
        },
        '& .loss': {
          color: 'error.main',
          fontWeight: 'bold',
        }
      }}>
      <DataGrid
        rows={positions}
        columns={columns}
        getRowId={(row) => row.uniqueId}
        rowsPerPageOptions={[5, 10]}
        checkboxSelection
        disableSelectionOnClick
        autoHeight
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'action.hover',
          }
        }}
      />
      </Box>
    </Paper>
  );
};

export default PositionsTable;