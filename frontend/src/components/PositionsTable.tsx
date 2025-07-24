import React, { useEffect, useState } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef, GridValueFormatterParams } from '@mui/x-data-grid';
import { CircularProgress, Alert, Paper, Typography, Box } from '@mui/material';
import { getPositions } from '../services/apiClient';
import type { Position } from '../types';

const columns: GridColDef[] = [
  { field: 'symbol', headerName: 'Symbol', width: 150 },
  { field: 'quantity', headerName: 'Quantity', type: 'number', width: 150 },
  { field: 'average_price', headerName: 'Average Price', type: 'number', width: 200, valueFormatter: (params: GridValueFormatterParams) => `$${(params.value as number).toLocaleString()}` },
  { field: 'value', headerName: 'Value', type: 'number', width: 150, valueFormatter: (params: GridValueFormatterParams) => `$${(params.value as number).toLocaleString()}` },
];

const PositionsTable: React.FC = () => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const data = await getPositions();
        // Assuming the API returns an array of positions, each with a unique 'id'
        setPositions(data);
      } catch (err) {
        setError('Failed to fetch positions.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();
  }, []);

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
      <Box sx={{ height: 350, width: '100%' }}>
      <DataGrid
        rows={positions}
        columns={columns}
        rowsPerPageOptions={[5, 10]}
        checkboxSelection
        disableSelectionOnClick
      />
      </Box>
    </Paper>
  );
};

export default PositionsTable;