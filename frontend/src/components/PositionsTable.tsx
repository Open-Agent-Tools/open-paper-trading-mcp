import React, { useEffect, useState } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef, GridValueFormatterParams } from '@mui/x-data-grid';
import { CircularProgress, Alert, Paper, Typography, Box } from '@mui/material';
import { getPositions } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';
import type { Position } from '../types';

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
  const [positions, setPositions] = useState<Position[]>([]);
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
        // Extract positions array from the response
        setPositions(data.positions || []);
      } catch (err) {
        setError('Failed to fetch positions.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();
  }, [selectedAccount]);

  if (loading) {
    return <CircularProgress />;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
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
        getRowId={(row) => row.symbol}
        rowsPerPageOptions={[5, 10]}
        checkboxSelection
        disableSelectionOnClick
      />
      </Box>
    </Paper>
  );
};

export default PositionsTable;