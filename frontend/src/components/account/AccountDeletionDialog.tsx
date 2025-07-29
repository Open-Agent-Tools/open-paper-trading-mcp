import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Button,
  Box,
  Alert,
  CircularProgress,
  Divider,
  Chip,
  Grid,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import WarningIcon from '@mui/icons-material/Warning';
import DeleteIcon from '@mui/icons-material/Delete';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { deleteAccount } from '../../services/accountApi';
import type { AccountSummary } from '../../types/account';

interface AccountDeletionDialogProps {
  open: boolean;
  account: AccountSummary | null;
  onClose: () => void;
  onAccountDeleted?: (accountId: string) => void;
}

const AccountDeletionDialog: React.FC<AccountDeletionDialogProps> = ({
  open,
  account,
  onClose,
  onAccountDeleted,
}) => {
  const theme = useTheme();
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [confirmationStep, setConfirmationStep] = useState(0);

  const handleDelete = async () => {
    if (!account) return;

    if (confirmationStep === 0) {
      setConfirmationStep(1);
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      const result = await deleteAccount(account.id);
      
      if (result.success) {
        onAccountDeleted?.(account.id);
        handleClose();
      } else {
        throw new Error(result.message || 'Failed to delete account');
      }
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'An unexpected error occurred');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleClose = () => {
    if (!isDeleting) {
      setConfirmationStep(0);
      setDeleteError(null);
      onClose();
    }
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
      month: 'long',
      day: 'numeric',
    });
  };

  const formatPercent = (percent: number): string => {
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  };

  if (!account) return null;

  const isProfit = account.balance_change >= 0;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: theme.spacing(1),
          boxShadow: theme.shadows[8],
        },
      }}
    >
      <DialogTitle
        sx={{
          backgroundColor: theme.palette.error.main,
          color: theme.palette.error.contrastText,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <WarningIcon />
        {confirmationStep === 0 ? 'Delete Account?' : 'Confirm Account Deletion'}
      </DialogTitle>
      
      <DialogContent sx={{ pt: 3 }}>
        {deleteError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {deleteError}
          </Alert>
        )}

        {confirmationStep === 0 ? (
          <>
            <Alert severity="warning" sx={{ mb: 3 }}>
              You are about to permanently delete this trading account. This action cannot be undone.
            </Alert>

            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Account Details
              </Typography>
              
              <Box sx={{ 
                p: 2, 
                backgroundColor: theme.palette.background.default,
                borderRadius: 1,
                border: `1px solid ${theme.palette.divider}`
              }}>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Owner
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>
                      {account.owner}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={6}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Account ID
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {account.id}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={6}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Created
                    </Typography>
                    <Typography variant="body2">
                      {formatDate(account.created_at)}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={6}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Starting Balance
                    </Typography>
                    <Typography variant="body2">
                      {formatCurrency(account.starting_balance)}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={6}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Current Balance
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {formatCurrency(account.current_balance)}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                      Performance
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {isProfit ? (
                        <TrendingUpIcon sx={{ color: theme.palette.success.main, fontSize: 16 }} />
                      ) : (
                        <TrendingDownIcon sx={{ color: theme.palette.error.main, fontSize: 16 }} />
                      )}
                      <Chip
                        size="small"
                        label={`${formatCurrency(account.balance_change)} (${formatPercent(account.balance_change_percent)})`}
                        color={isProfit ? 'success' : 'error'}
                        variant="outlined"
                      />
                    </Box>
                  </Grid>
                </Grid>
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary">
              The following data will be permanently deleted:
            </Typography>
            <Typography variant="body2" component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
              <li>All portfolio positions and holdings</li>
              <li>Complete order history and transaction logs</li>
              <li>Performance metrics and analytics data</li>
              <li>Account settings and preferences</li>
            </Typography>
          </>
        ) : (
          <>
            <Alert severity="error" sx={{ mb: 3 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                This is your final confirmation.
              </Typography>
              <Typography variant="body2">
                Account "{account.owner}" ({account.id}) and all associated data will be permanently deleted.
              </Typography>
            </Alert>

            <Typography variant="body1" sx={{ textAlign: 'center', fontWeight: 500 }}>
              Are you absolutely sure you want to proceed?
            </Typography>
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 2 }}>
        <Button
          onClick={handleClose}
          disabled={isDeleting}
          color="inherit"
        >
          Cancel
        </Button>
        
        <Button
          onClick={handleDelete}
          variant="contained"
          color="error"
          disabled={isDeleting}
          startIcon={isDeleting ? <CircularProgress size={16} /> : <DeleteIcon />}
          sx={{
            minWidth: 140,
            fontWeight: 500,
          }}
        >
          {isDeleting 
            ? 'Deleting...' 
            : confirmationStep === 0 
              ? 'Delete Account' 
              : 'Yes, Delete Forever'
          }
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AccountDeletionDialog;