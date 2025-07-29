import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent, 
  CardActions,
  Typography,
  Button,
  Grid,
  TextField,
  InputAdornment,
  Chip,
  Alert,
  Skeleton,
  Container,
  IconButton,
  Menu,
  MenuItem,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import SearchIcon from '@mui/icons-material/Search';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PersonIcon from '@mui/icons-material/Person';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import { getAllAccounts } from '../../services/accountApi';
import type { AccountSummary, AccountsResponse } from '../../types/account';

interface AccountSelectionGridProps {
  onAccountSelected: (account: AccountSummary) => void;
  onAccountDeleted?: (accountId: string) => void;
  selectedAccountId?: string;
}

interface AccountCardProps {
  account: AccountSummary;
  isSelected: boolean;
  onSelect: (account: AccountSummary) => void;
  onDelete?: (accountId: string) => void;
}

const AccountCard: React.FC<AccountCardProps> = ({ 
  account, 
  isSelected, 
  onSelect, 
  onDelete 
}) => {
  const theme = useTheme();
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setMenuAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchorEl(null);
  };

  const handleDelete = () => {
    onDelete?.(account.id);
    handleMenuClose();
  };

  const formatCurrency = (amount: number): string => {
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatPercent = (percent: number): string => {
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  };

  const isProfit = account.balance_change >= 0;

  return (
    <Card
      elevation={isSelected ? 8 : 2}
      sx={{
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        border: isSelected ? `2px solid ${theme.palette.primary.main}` : '2px solid transparent',
        position: 'relative',
        '&:hover': {
          elevation: 6,
          transform: 'translateY(-2px)',
        },
      }}
      onClick={() => onSelect(account)}
    >
      <CardContent sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" component="h3" sx={{ fontWeight: 600, mb: 0.5 }}>
              {account.owner}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <PersonIcon fontSize="small" />
              Account ID: {account.id}
            </Typography>
          </Box>
          
          {onDelete && (
            <IconButton 
              size="small" 
              onClick={handleMenuOpen}
              sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
            >
              <MoreVertIcon />
            </IconButton>
          )}
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
            <CalendarTodayIcon fontSize="small" />
            Created: {formatDate(account.created_at)}
          </Typography>
        </Box>

        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Starting Balance
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 500 }}>
              {formatCurrency(account.starting_balance)}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Current Balance
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {formatCurrency(account.current_balance)}
            </Typography>
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="body2" color="text.secondary">
            Performance
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {isProfit ? (
              <TrendingUpIcon sx={{ color: theme.palette.success.main, fontSize: 16 }} />
            ) : (
              <TrendingDownIcon sx={{ color: theme.palette.error.main, fontSize: 16 }} />
            )}
            <Typography
              variant="body2"
              sx={{
                color: isProfit ? theme.palette.success.main : theme.palette.error.main,
                fontWeight: 600,
              }}
            >
              {formatCurrency(account.balance_change)} ({formatPercent(account.balance_change_percent)})
            </Typography>
          </Box>
        </Box>
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button
          fullWidth
          variant={isSelected ? "contained" : "outlined"}
          startIcon={<AccountBalanceIcon />}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(account);
          }}
          sx={{ fontWeight: 500 }}
        >
          {isSelected ? 'Selected' : 'Select Account'}
        </Button>
      </CardActions>

      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem onClick={handleDelete} sx={{ color: theme.palette.error.main }}>
          Delete Account
        </MenuItem>
      </Menu>
    </Card>
  );
};

const AccountSelectionGrid: React.FC<AccountSelectionGridProps> = ({
  onAccountSelected,
  onAccountDeleted,
  selectedAccountId,
}) => {
  const theme = useTheme();
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [filteredAccounts, setFilteredAccounts] = useState<AccountSummary[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<AccountsResponse['summary'] | null>(null);

  const loadAccounts = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await getAllAccounts();
      if (response.success) {
        setAccounts(response.accounts);
        setFilteredAccounts(response.accounts);
        setSummary(response.summary);
      } else {
        throw new Error(response.message || 'Failed to load accounts');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    const filtered = accounts.filter(account => 
      account.owner.toLowerCase().includes(searchTerm.toLowerCase()) ||
      account.id.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredAccounts(filtered);
  }, [searchTerm, accounts]);

  const handleAccountDeleted = (accountId: string) => {
    setAccounts(accounts.filter(account => account.id !== accountId));
    onAccountDeleted?.(accountId);
  };

  const formatCurrency = (amount: number): string => {
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  };

  if (loading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ mb: 4 }}>
          <Skeleton variant="text" width={200} height={40} />
          <Skeleton variant="text" width={400} height={24} />
        </Box>
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={12} sm={6} md={4} key={i}>
              <Skeleton variant="rectangular" height={250} sx={{ borderRadius: 2 }} />
            </Grid>
          ))}
        </Grid>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg">
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
        <Box sx={{ mt: 2, textAlign: 'center' }}>
          <Button variant="outlined" onClick={loadAccounts}>
            Retry
          </Button>
        </Box>
      </Container>
    );
  }

  if (accounts.length === 0) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <AccountBalanceIcon sx={{ fontSize: 64, color: theme.palette.action.disabled, mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            No Trading Accounts Found
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            Create your first trading account to start paper trading with virtual funds.
          </Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom sx={{ 
          color: theme.palette.primary.main,
          fontWeight: 500 
        }}>
          Select Trading Account
        </Typography>
        
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
          Choose an account to view portfolio and trading options
        </Typography>

        {summary && (
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Chip
                label={`${summary.total_count} Accounts`}
                icon={<AccountBalanceIcon />}
                variant="outlined"
                sx={{ minWidth: 120 }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Chip
                label={`${formatCurrency(summary.total_current_balance)} Total`}
                icon={<TrendingUpIcon />}
                color="primary"
                variant="outlined"
                sx={{ minWidth: 120 }}
              />
            </Grid>
          </Grid>
        )}

        <TextField
          fullWidth
          placeholder="Search by owner name or account ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ maxWidth: 400 }}
        />
      </Box>

      {filteredAccounts.length === 0 && searchTerm ? (
        <Alert severity="info">
          No accounts found matching "{searchTerm}". Try a different search term.
        </Alert>
      ) : (
        <Grid container spacing={3}>
          {filteredAccounts.map((account) => (
            <Grid item xs={12} sm={6} md={4} key={account.id}>
              <AccountCard
                account={account}
                isSelected={selectedAccountId === account.id}
                onSelect={onAccountSelected}
                onDelete={onAccountDeleted ? handleAccountDeleted : undefined}
              />
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
};

export default AccountSelectionGrid;