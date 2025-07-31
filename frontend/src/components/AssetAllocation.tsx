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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  useTheme,
} from '@mui/material';
import {
  PieChart as PieChartIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { useAccountContext } from '../contexts/AccountContext';
import { getPositions } from '../services/apiClient';
import type { Position } from '../types';

interface AllocationData {
  name: string;
  value: number;
  percentage: number;
  count: number;
  color: string;
}

const AssetAllocation: React.FC = () => {
  const theme = useTheme();
  const { selectedAccount } = useAccountContext();
  const [allocationData, setAllocationData] = useState<AllocationData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Color palette for different asset types
  const colorPalette = [
    theme.palette.primary.main,
    theme.palette.secondary.main,
    theme.palette.success.main,
    theme.palette.warning.main,
    theme.palette.error.main,
    theme.palette.info.main,
    '#9C27B0', // Purple
    '#FF9800', // Orange
    '#795548', // Brown
    '#607D8B', // Blue Grey
  ];

  const calculateAllocation = (positions: Position[]): AllocationData[] => {
    if (!positions.length) return [];

    // Group positions by asset type
    const assetGroups = new Map<string, { value: number; count: number }>();
    
    positions.forEach(position => {
      const assetType = position.asset_type || (position.option_type ? 'Options' : 'Stock');
      const marketValue = position.market_value || 0;
      
      if (assetGroups.has(assetType)) {
        const existing = assetGroups.get(assetType)!;
        assetGroups.set(assetType, {
          value: existing.value + marketValue,
          count: existing.count + 1
        });
      } else {
        assetGroups.set(assetType, { value: marketValue, count: 1 });
      }
    });

    // Calculate total portfolio value
    const totalValue = Array.from(assetGroups.values()).reduce((sum, group) => sum + group.value, 0);

    // Convert to allocation data with percentages
    const allocation: AllocationData[] = [];
    let colorIndex = 0;
    
    assetGroups.forEach((group, assetType) => {
      allocation.push({
        name: assetType,
        value: group.value,
        percentage: (group.value / totalValue) * 100,
        count: group.count,
        color: colorPalette[colorIndex % colorPalette.length]
      });
      colorIndex++;
    });

    // Sort by value descending
    return allocation.sort((a, b) => b.value - a.value);
  };

  const fetchAllocationData = async () => {
    if (!selectedAccount) {
      setAllocationData([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getPositions(selectedAccount.id);
      
      if (response.success) {
        const positions = response.positions || [];
        const allocation = calculateAllocation(positions);
        setAllocationData(allocation);
      } else {
        setError('Failed to load position data');
      }
    } catch (err) {
      setError('Failed to calculate asset allocation');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllocationData();
  }, [selectedAccount]);

  const formatCurrency = (value: number) => {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Box
          sx={{
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 1,
            p: 1.5,
            boxShadow: theme.shadows[3]
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
            {data.name}
          </Typography>
          <Typography variant="body2">
            Value: {formatCurrency(data.value)}
          </Typography>
          <Typography variant="body2">
            Allocation: {data.percentage.toFixed(1)}%
          </Typography>
          <Typography variant="body2">
            Positions: {data.count}
          </Typography>
        </Box>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
          <CircularProgress />
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
              <PieChartIcon color="primary" />
              <Typography variant="h6">Asset Allocation</Typography>
            </Box>
          }
          action={
            <IconButton onClick={fetchAllocationData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!selectedAccount) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
          <Typography color="text.secondary">Select an account to view asset allocation</Typography>
        </CardContent>
      </Card>
    );
  }

  if (allocationData.length === 0) {
    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={1}>
              <PieChartIcon color="primary" />
              <Typography variant="h6">Asset Allocation</Typography>
            </Box>
          }
        />
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
            <Typography color="text.secondary">No positions available for allocation analysis</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const totalValue = allocationData.reduce((sum, item) => sum + item.value, 0);

  return (
    <Card>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <PieChartIcon color="primary" />
            <Typography variant="h6">Asset Allocation</Typography>
          </Box>
        }
        action={
          <IconButton onClick={fetchAllocationData} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
        subheader={
          <Typography variant="body2" color="text.secondary">
            Portfolio breakdown by asset type • Total: {formatCurrency(totalValue)}
          </Typography>
        }
      />
      <CardContent>
        <Box display="flex" flexDirection={{ xs: 'column', md: 'row' }} gap={3}>
          {/* Pie Chart */}
          <Box flex={1} minHeight={300}>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={allocationData}
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  innerRadius={40}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {allocationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend 
                  verticalAlign="bottom" 
                  height={36}
                  formatter={(value, entry: any) => (
                    <span style={{ color: entry.color }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </Box>

          {/* Allocation Table */}
          <Box flex={1}>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Asset Type</TableCell>
                    <TableCell align="right">Value</TableCell>
                    <TableCell align="right">Allocation</TableCell>
                    <TableCell align="right">Positions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {allocationData.map((row) => (
                    <TableRow key={row.name} hover>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Box
                            sx={{
                              width: 12,
                              height: 12,
                              borderRadius: '50%',
                              backgroundColor: row.color,
                            }}
                          />
                          <Typography variant="body2" fontWeight="medium">
                            {row.name}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                          {formatCurrency(row.value)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                          {row.percentage.toFixed(1)}%
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" sx={{ fontFamily: 'Roboto Mono, monospace' }}>
                          {row.count}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default AssetAllocation;