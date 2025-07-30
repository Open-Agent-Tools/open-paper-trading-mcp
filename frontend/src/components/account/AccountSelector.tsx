import React, { useState } from 'react';
import {
  Box,
  Button,
  Menu,
  MenuItem,
  Typography,
  Chip,
  Avatar,
  Divider,
  ListItemIcon,
  ListItemText,
  Alert,
  CircularProgress,
  useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import {
  AccountBalance as AccountIcon,
  ExpandMore as ExpandIcon,
  PersonAdd as AddAccountIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAccountContext } from '../../contexts/AccountContext';
import type { AccountSummary } from '../../types/account';

interface AccountSelectorProps {
  variant?: 'button' | 'compact' | 'chip';
  showBalance?: boolean;
  showCreateOption?: boolean;
  className?: string;
}

const AccountSelector: React.FC<AccountSelectorProps> = ({
  variant = 'button',
  showBalance = true,
  showCreateOption = true,
  className,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  const {
    selectedAccount,
    availableAccounts,
    isLoading,
    error,
    selectAccount,
    refreshAccounts,
    clearError,
  } = useAccountContext();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
    if (error) {
      clearError();
    }
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleAccountSelect = (account: AccountSummary) => {
    selectAccount(account);
    handleClose();
    navigate('/account');
  };

  const handleCreateAccount = () => {
    handleClose();
    navigate('/');
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refreshAccounts();
    } finally {
      setIsRefreshing(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return amount.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    });
  };

  const getBalanceChangeColor = (change: number, _changePercent: number) => {
    if (change > 0) return theme.palette.success.main;
    if (change < 0) return theme.palette.error.main;
    return theme.palette.text.secondary;
  };

  const getAccountInitials = (owner: string) => {
    return owner
      .split(' ')
      .map(word => word.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('');
  };

  const renderMenu = () => {
    return (
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        PaperProps={{
          sx: {
            minWidth: 320,
            maxWidth: 400,
            maxHeight: 400,
          },
        }}
        transformOrigin={{ horizontal: 'left', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}
      >
        {/* Error Alert */}
        {error && (
          <Box sx={{ p: 2 }}>
            <Alert severity="error">
              {error}
            </Alert>
          </Box>
        )}

        {/* Current Selection */}
        {selectedAccount && (
          <>
            <MenuItem disabled>
              <ListItemIcon>
                <CheckIcon color="success" />
              </ListItemIcon>
              <ListItemText
                primary="Current Account"
                secondary={
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      {selectedAccount.owner}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      ID: {selectedAccount.id}
                    </Typography>
                    {showBalance && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                        <Typography variant="caption">
                          Balance: {formatCurrency(selectedAccount.current_balance)}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            color: getBalanceChangeColor(
                              selectedAccount.balance_change,
                              selectedAccount.balance_change_percent
                            ),
                            fontWeight: 'medium',
                          }}
                        >
                          {selectedAccount.balance_change >= 0 ? '+' : ''}
                          {formatCurrency(selectedAccount.balance_change)} (
                          {selectedAccount.balance_change_percent.toFixed(2)}%)
                        </Typography>
                      </Box>
                    )}
                  </Box>
                }
              />
            </MenuItem>
            <Divider />
          </>
        )}

        {/* Available Accounts */}
        {availableAccounts.length > 0 ? (
          availableAccounts
            .filter(account => account.id !== selectedAccount?.id)
            .map((account) => (
              <MenuItem
                key={account.id}
                onClick={() => handleAccountSelect(account)}
              >
                <ListItemIcon>
                  <Avatar sx={{ width: 32, height: 32, fontSize: '0.75rem' }}>
                    {getAccountInitials(account.owner)}
                  </Avatar>
                </ListItemIcon>
                <ListItemText
                  primary={account.owner}
                  secondary={
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        ID: {account.id}
                      </Typography>
                      {showBalance && (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="caption">
                            {formatCurrency(account.current_balance)}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              color: getBalanceChangeColor(
                                account.balance_change,
                                account.balance_change_percent
                              ),
                            }}
                          >
                            {account.balance_change >= 0 ? '+' : ''}
                            {formatCurrency(account.balance_change)}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  }
                />
              </MenuItem>
            ))
        ) : (
          <MenuItem disabled>
            <ListItemIcon>
              <WarningIcon color="warning" />
            </ListItemIcon>
            <ListItemText primary="No accounts available" />
          </MenuItem>
        )}

        <Divider />

        {/* Actions */}
        <MenuItem onClick={handleRefresh} disabled={isRefreshing}>
          <ListItemIcon>
            {isRefreshing ? (
              <CircularProgress size={20} />
            ) : (
              <RefreshIcon />
            )}
          </ListItemIcon>
          <ListItemText primary="Refresh Accounts" />
        </MenuItem>

        {showCreateOption && (
          <MenuItem onClick={handleCreateAccount}>
            <ListItemIcon>
              <AddAccountIcon />
            </ListItemIcon>
            <ListItemText primary="Create New Account" />
          </MenuItem>
        )}
      </Menu>
    );
  };

  // Compact variant for mobile/small spaces
  if (variant === 'compact') {
    return (
      <Box className={className}>
        <Button
          onClick={handleClick}
          size="small"
          variant="outlined"
          disabled={isLoading}
          sx={{
            minWidth: 'auto',
            px: 1,
            color: 'white',
            borderColor: 'rgba(255, 255, 255, 0.5)',
            '&:hover': {
              borderColor: 'rgba(255, 255, 255, 0.8)',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            },
          }}
        >
          {selectedAccount ? (
            <Typography variant="caption" noWrap sx={{ maxWidth: 100 }}>
              {selectedAccount.owner}
            </Typography>
          ) : (
            <Typography variant="caption">Select Account</Typography>
          )}
          <ExpandIcon sx={{ ml: 0.5, fontSize: '1rem' }} />
        </Button>
        {renderMenu()}
      </Box>
    );
  }

  // Chip variant for inline use
  if (variant === 'chip') {
    return (
      <Box className={className}>
        <Chip
          onClick={handleClick}
          avatar={
            selectedAccount ? (
              <Avatar sx={{ bgcolor: theme.palette.primary.main, fontSize: '0.75rem' }}>
                {getAccountInitials(selectedAccount.owner)}
              </Avatar>
            ) : (
              <Avatar sx={{ bgcolor: theme.palette.grey[400] }}>
                <AccountIcon sx={{ fontSize: '1rem' }} />
              </Avatar>
            )
          }
          label={
            selectedAccount
              ? `${selectedAccount.owner} ${showBalance ? `(${formatCurrency(selectedAccount.current_balance)})` : ''}`
              : 'Select Account'
          }
          variant="outlined"
          disabled={isLoading}
          sx={{
            maxWidth: isMobile ? 200 : 300,
            '& .MuiChip-label': {
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            },
          }}
        />
        {renderMenu()}
      </Box>
    );
  }

  // Default button variant
  return (
    <Box className={className}>
      <Button
        onClick={handleClick}
        variant="outlined"
        disabled={isLoading}
        startIcon={isLoading ? <CircularProgress size={16} /> : <AccountIcon />}
        endIcon={<ExpandIcon />}
        sx={{
          minWidth: 200,
          maxWidth: isMobile ? 250 : 350,
          justifyContent: 'space-between',
          textAlign: 'left',
          color: 'white',
          borderColor: 'rgba(255, 255, 255, 0.5)',
          '&:hover': {
            borderColor: 'rgba(255, 255, 255, 0.8)',
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          },
        }}
      >
        <Box sx={{ overflow: 'hidden', flex: 1 }}>
          {selectedAccount ? (
            <>
              <Typography variant="body2" noWrap>
                {selectedAccount.owner}
              </Typography>
              {showBalance && (
                <Typography variant="caption" color="rgba(255, 255, 255, 0.7)" noWrap>
                  {formatCurrency(selectedAccount.current_balance)}
                </Typography>
              )}
            </>
          ) : (
            <Typography variant="body2">Select Account</Typography>
          )}
        </Box>
      </Button>
      {renderMenu()}
    </Box>
  );
};

export default AccountSelector;