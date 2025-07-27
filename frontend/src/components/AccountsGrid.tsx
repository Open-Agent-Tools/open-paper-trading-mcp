import React, { useState, useEffect, useMemo } from 'react';
import {
  DataGrid,
  GridToolbar,
} from '@mui/x-data-grid';
import type {
  GridColDef,
  GridValueGetterParams,
  GridRenderCellParams,
} from '@mui/x-data-grid';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Typography,
  Chip,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import type { AccountSummary, AccountsResponse } from '../types';
import { getAllAccounts } from '../services/apiClient';

interface AccountsGridProps {
  onSelectAccount?: (accountId: string) => void;
  showSelectButton?: boolean;
  title?: string;
}

const AccountsGrid: React.FC<AccountsGridProps> = ({
  onSelectAccount,
  showSelectButton = false,
  title = 'All Accounts'
}) => {
  const theme = useTheme();
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [summary, setSummary] = useState<AccountsResponse['summary'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await getAllAccounts();
        if (response.success) {
          setAccounts(response.accounts);
          setSummary(response.summary);
        } else {
          setError(response.message || 'Failed to fetch accounts');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchAccounts();
  }, []);

  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatPercentage = (percent: number): string => {
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const columns: GridColDef[] = useMemo(() => [
    {
      field: 'id',
      headerName: 'Account ID',
      width: 120,
      sortable: true,
      filterable: true,
    },
    {
      field: 'owner',
      headerName: 'Owner',
      width: 150,
      sortable: true,
      filterable: true,
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 120,
      sortable: true,
      valueGetter: (params: GridValueGetterParams) => formatDate(params.value),
    },
    {
      field: 'starting_balance',
      headerName: 'Starting Balance',
      width: 150,
      sortable: true,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (params: GridValueGetterParams) => formatCurrency(params.value),
    },
    {
      field: 'current_balance',
      headerName: 'Current Balance',
      width: 150,
      sortable: true,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (params: GridValueGetterParams) => formatCurrency(params.value),
    },
    {
      field: 'balance_change',
      headerName: 'P&L',
      width: 120,
      sortable: true,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams) => {
        const value = params.value as number;
        const isPositive = value >= 0;
        return (
          <Typography
            sx={{
              color: isPositive ? theme.palette.success.main : theme.palette.error.main,
              fontWeight: 500,
              fontFamily: 'Roboto Mono, monospace',
            }}
          >
            {formatCurrency(value)}
          </Typography>
        );
      },
    },
    {
      field: 'balance_change_percent',
      headerName: 'P&L %',
      width: 100,
      sortable: true,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams) => {
        const value = params.value as number;
        const isPositive = value >= 0;
        return (
          <Chip
            label={formatPercentage(value)}
            size="small"
            sx={{
              backgroundColor: isPositive 
                ? theme.palette.success.light 
                : theme.palette.error.light,
              color: isPositive 
                ? theme.palette.success.main 
                : theme.palette.error.main,
              fontWeight: 500,
              fontFamily: 'Roboto Mono, monospace',
            }}
          />
        );
      },
    },
    ...(showSelectButton ? [{
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Button
          variant="outlined"
          size="small"
          onClick={() => onSelectAccount?.(params.row.id)}
          sx={{
            color: theme.palette.primary.main,
            borderColor: theme.palette.primary.main,
            '&:hover': {
              backgroundColor: theme.palette.primary.light,
              color: theme.palette.primary.contrastText,
            },
          }}
        >
          Select
        </Button>
      ),
    }] : []),
  ], [theme, showSelectButton, onSelectAccount]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader
        title={title}
        subheader={summary ? `${summary.total_count} accounts` : ''}
      />
      <CardContent>
        {summary && (
          <Box mb={3}>
            <Typography variant="h6" gutterBottom>
              Portfolio Summary
            </Typography>
            <Box display="flex" gap={4} flexWrap="wrap">
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Total Starting Balance
                </Typography>
                <Typography variant="h6">
                  {formatCurrency(summary.total_starting_balance)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Total Current Balance
                </Typography>
                <Typography variant="h6">
                  {formatCurrency(summary.total_current_balance)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Total P&L
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    color: summary.total_balance_change >= 0 
                      ? theme.palette.success.main 
                      : theme.palette.error.main,
                    fontWeight: 500,
                    fontFamily: 'Roboto Mono, monospace',
                  }}
                >
                  {formatCurrency(summary.total_balance_change)}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}
        
        <Box height={600}>
          <DataGrid
            rows={accounts}
            columns={columns}
            components={{ Toolbar: GridToolbar }}
            componentsProps={{
              toolbar: {
                showQuickFilter: true,
                quickFilterProps: { debounceMs: 500 },
              },
            }}
            disableSelectionOnClick
            pageSize={25}
            rowsPerPageOptions={[10, 25, 50, 100]}
            initialState={{
              sorting: {
                sortModel: [{ field: 'created_at', sort: 'desc' }],
              },
            }}
            sx={{
              '& .MuiDataGrid-root': {
                border: 'none',
              },
              '& .MuiDataGrid-cell': {
                borderBottom: `1px solid ${theme.palette.divider}`,
              },
              '& .MuiDataGrid-columnHeaders': {
                backgroundColor: theme.palette.background.default,
                borderBottom: `2px solid ${theme.palette.divider}`,
              },
              '& .MuiDataGrid-virtualScroller': {
                backgroundColor: theme.palette.background.paper,
              },
              '& .MuiDataGrid-footerContainer': {
                borderTop: `2px solid ${theme.palette.divider}`,
                backgroundColor: theme.palette.background.default,
              },
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
};

export default AccountsGrid;