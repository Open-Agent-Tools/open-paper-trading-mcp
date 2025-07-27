import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Alert,
  InputAdornment,
  CircularProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { createAccount } from '../services/apiClient';

interface CreateAccountModalProps {
  open: boolean;
  onClose: () => void;
  onAccountCreated?: () => void;
}

interface CreateAccountFormData {
  owner: string;
  startingBalance: string;
}

interface FormErrors {
  owner?: string;
  startingBalance?: string;
}

const CreateAccountModal: React.FC<CreateAccountModalProps> = ({
  open,
  onClose,
  onAccountCreated,
}) => {
  const theme = useTheme();
  const [formData, setFormData] = useState<CreateAccountFormData>({
    owner: '',
    startingBalance: '10000',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Validate owner
    if (!formData.owner.trim()) {
      newErrors.owner = 'Account owner is required';
    } else if (formData.owner.trim().length < 2) {
      newErrors.owner = 'Owner name must be at least 2 characters';
    } else if (formData.owner.trim().length > 50) {
      newErrors.owner = 'Owner name must be less than 50 characters';
    }

    // Validate starting balance
    const balance = parseFloat(formData.startingBalance);
    if (!formData.startingBalance.trim()) {
      newErrors.startingBalance = 'Starting balance is required';
    } else if (isNaN(balance)) {
      newErrors.startingBalance = 'Starting balance must be a valid number';
    } else if (balance < 100) {
      newErrors.startingBalance = 'Starting balance must be at least $100';
    } else if (balance > 1000000) {
      newErrors.startingBalance = 'Starting balance cannot exceed $1,000,000';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (field: keyof CreateAccountFormData) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = event.target.value;
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear field-specific error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
    
    // Clear submit error when user makes changes
    if (submitError) {
      setSubmitError(null);
    }
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const result = await createAccount({
        owner: formData.owner.trim(),
        starting_balance: parseFloat(formData.startingBalance),
      });
      
      if (result.success) {
        // Reset form
        setFormData({ owner: '', startingBalance: '10000' });
        setErrors({});
        
        // Notify parent component
        onAccountCreated?.();
        
        // Close modal
        onClose();
      } else {
        throw new Error(result.message || 'Failed to create account');
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'An unexpected error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setFormData({ owner: '', startingBalance: '10000' });
      setErrors({});
      setSubmitError(null);
      onClose();
    }
  };

  const formatCurrency = (value: string): string => {
    const numValue = parseFloat(value);
    if (isNaN(numValue)) return value;
    return numValue.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  };

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
          backgroundColor: theme.palette.primary.main,
          color: theme.palette.primary.contrastText,
          typography: 'h5',
          fontWeight: 500,
        }}
      >
        Create New Trading Account
      </DialogTitle>
      
      <DialogContent sx={{ pt: 3 }}>
        <Box component="form" noValidate>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Create a new paper trading account to simulate trading strategies 
            with virtual funds. Each account operates independently with its own 
            portfolio and transaction history.
          </Typography>

          {submitError && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {submitError}
            </Alert>
          )}

          <TextField
            autoFocus
            label="Account Owner"
            fullWidth
            value={formData.owner}
            onChange={handleInputChange('owner')}
            error={!!errors.owner}
            helperText={errors.owner || 'Enter the name of the account owner'}
            margin="normal"
            variant="outlined"
            disabled={isSubmitting}
            sx={{ mb: 2 }}
          />

          <TextField
            label="Starting Balance"
            fullWidth
            value={formData.startingBalance}
            onChange={handleInputChange('startingBalance')}
            error={!!errors.startingBalance}
            helperText={
              errors.startingBalance || 
              `Initial virtual cash: ${formatCurrency(formData.startingBalance || '0')}`
            }
            margin="normal"
            variant="outlined"
            disabled={isSubmitting}
            InputProps={{
              startAdornment: <InputAdornment position="start">$</InputAdornment>,
            }}
            sx={{ mb: 2 }}
          />

          <Box
            sx={{
              mt: 2,
              p: 2,
              backgroundColor: theme.palette.info.light,
              borderRadius: theme.spacing(1),
              border: `1px solid ${theme.palette.info.main}`,
            }}
          >
            <Typography variant="body2" color="info.main" sx={{ fontWeight: 500 }}>
              Account Features:
            </Typography>
            <Typography variant="body2" color="text.secondary" component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
              <li>Virtual trading with real market data</li>
              <li>Portfolio tracking and performance metrics</li>
              <li>Order history and transaction logs</li>
              <li>Risk analysis and position monitoring</li>
            </Typography>
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 2 }}>
        <Button
          onClick={handleClose}
          disabled={isSubmitting}
          sx={{
            color: theme.palette.text.secondary,
            '&:hover': {
              backgroundColor: theme.palette.action.hover,
            },
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={16} /> : null}
          sx={{
            backgroundColor: theme.palette.primary.main,
            color: theme.palette.primary.contrastText,
            fontWeight: 500,
            minWidth: 120,
            '&:hover': {
              backgroundColor: theme.palette.primary.dark,
            },
            '&:disabled': {
              backgroundColor: theme.palette.action.disabledBackground,
              color: theme.palette.action.disabled,
            },
          }}
        >
          {isSubmitting ? 'Creating...' : 'Create Account'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CreateAccountModal;