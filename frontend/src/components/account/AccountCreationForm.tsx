import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  InputAdornment,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Card,
  CardContent,
  CardActions,
  Grid,
  Chip,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import PersonIcon from '@mui/icons-material/Person';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import BusinessIcon from '@mui/icons-material/Business';
import { createAccount } from '../../services/accountApi';
import type { AccountFormData, AccountFormErrors, AccountType } from '../../types/account';

interface AccountCreationFormProps {
  onAccountCreated?: (accountId: string) => void;
  onCancel?: () => void;
}

const ACCOUNT_TYPES: { value: AccountType; label: string; icon: React.ReactNode }[] = [
  { value: 'individual', label: 'Individual', icon: <PersonIcon /> },
  { value: 'joint', label: 'Joint Account', icon: <PersonIcon /> },
  { value: 'corporate', label: 'Corporate', icon: <BusinessIcon /> },
  { value: 'trust', label: 'Trust', icon: <AccountBalanceIcon /> },
];

const AccountCreationForm: React.FC<AccountCreationFormProps> = ({
  onAccountCreated,
  onCancel,
}) => {
  const theme = useTheme();
  const [formData, setFormData] = useState<AccountFormData>({
    owner: '',
    name: '',
    startingBalance: '10000',
    accountType: 'individual',
  });
  const [errors, setErrors] = useState<AccountFormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const validateForm = (): boolean => {
    const newErrors: AccountFormErrors = {};

    // Validate owner
    if (!formData.owner.trim()) {
      newErrors.owner = 'Account owner is required';
    } else if (formData.owner.trim().length < 2) {
      newErrors.owner = 'Owner name must be at least 2 characters';
    } else if (formData.owner.trim().length > 100) {
      newErrors.owner = 'Owner name must be less than 100 characters';
    }

    // Validate account name (optional but if provided, must be valid)
    if (formData.name.trim() && formData.name.trim().length < 2) {
      newErrors.name = 'Account name must be at least 2 characters';
    } else if (formData.name.trim().length > 50) {
      newErrors.name = 'Account name must be less than 50 characters';
    }

    // Validate starting balance
    const balance = parseFloat(formData.startingBalance);
    if (!formData.startingBalance.trim()) {
      newErrors.startingBalance = 'Starting balance is required';
    } else if (isNaN(balance)) {
      newErrors.startingBalance = 'Starting balance must be a valid number';
    } else if (balance < 100) {
      newErrors.startingBalance = 'Starting balance must be at least $100';
    } else if (balance > 10000000) {
      newErrors.startingBalance = 'Starting balance cannot exceed $10,000,000';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (field: keyof AccountFormData) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = event.target.value;
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear field-specific error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
    
    // Clear submit messages when user makes changes  
    if (submitError) setSubmitError(null);
    if (submitSuccess) setSubmitSuccess(null);
  };

  const handleSelectChange = (field: keyof AccountFormData) => (
    event: SelectChangeEvent<string>
  ) => {
    const value = event.target.value;
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear field-specific error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
    
    // Clear submit messages when user makes changes  
    if (submitError) setSubmitError(null);
    if (submitSuccess) setSubmitSuccess(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      const result = await createAccount({
        owner: formData.owner.trim(),
        starting_balance: parseFloat(formData.startingBalance),
        name: formData.name.trim() || undefined,
      });
      
      if (result.success) {
        setSubmitSuccess(`Account created successfully! Account ID: ${result.account_id}`);
        
        // Reset form
        setFormData({
          owner: '',
          name: '',
          startingBalance: '10000',
          accountType: 'individual',
        });
        setErrors({});
        
        // Notify parent component
        onAccountCreated?.(result.account_id);
      } else {
        throw new Error(result.message || 'Failed to create account');
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'An unexpected error occurred');
    } finally {
      setIsSubmitting(false);
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
    <Card elevation={4} sx={{ maxWidth: 600, mx: 'auto' }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom sx={{ 
          color: theme.palette.primary.main,
          fontWeight: 500,
          mb: 1
        }}>
          Create New Trading Account
        </Typography>
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Set up a new paper trading account to simulate trading strategies with virtual funds. 
          Each account operates independently with its own portfolio and transaction history.
        </Typography>

        {submitError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {submitError}
          </Alert>
        )}

        {submitSuccess && (
          <Alert severity="success" sx={{ mb: 3 }}>
            {submitSuccess}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} noValidate>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                label="Account Owner"
                fullWidth
                required
                value={formData.owner}
                onChange={handleInputChange('owner')}
                error={!!errors.owner}
                helperText={errors.owner || 'Enter the full name of the account owner'}
                variant="outlined" 
                disabled={isSubmitting}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <PersonIcon color="action" />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                label="Account Name (Optional)"
                fullWidth
                value={formData.name}
                onChange={handleInputChange('name')}
                error={!!errors.name}
                helperText={errors.name || 'Descriptive name for this account (e.g., "Growth Portfolio", "Day Trading")'}
                variant="outlined"
                disabled={isSubmitting}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth variant="outlined" disabled={isSubmitting}>
                <InputLabel>Account Type</InputLabel>
                <Select
                  value={formData.accountType}
                  onChange={handleSelectChange('accountType')}
                  label="Account Type"
                >
                  {ACCOUNT_TYPES.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {type.icon}
                        {type.label}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                label="Starting Balance"
                fullWidth
                required
                value={formData.startingBalance}
                onChange={handleInputChange('startingBalance')}
                error={!!errors.startingBalance}
                helperText={
                  errors.startingBalance || 
                  `Virtual cash: ${formatCurrency(formData.startingBalance || '0')}`
                }
                variant="outlined"
                disabled={isSubmitting}
                InputProps={{
                  startAdornment: <InputAdornment position="start">$</InputAdornment>,
                }}
              />
            </Grid>
          </Grid>

          <Box
            sx={{
              mt: 3,
              p: 2,
              backgroundColor: theme.palette.info.light,
              borderRadius: 1,
              border: `1px solid ${theme.palette.info.main}`,
            }}
          >
            <Typography variant="subtitle2" color="info.main" sx={{ fontWeight: 600, mb: 1 }}>
              Account Features:
            </Typography>
            <Grid container spacing={1}>
              <Grid item>
                <Chip size="small" label="Virtual Trading" variant="outlined" />
              </Grid>
              <Grid item>
                <Chip size="small" label="Real Market Data" variant="outlined" />
              </Grid>
              <Grid item>
                <Chip size="small" label="Portfolio Tracking" variant="outlined" />
              </Grid>
              <Grid item>
                <Chip size="small" label="Risk Analysis" variant="outlined" />
              </Grid>
            </Grid>
          </Box>
        </Box>
      </CardContent>

      <CardActions sx={{ p: 3, pt: 0, justifyContent: 'flex-end' }}>
        {onCancel && (
          <Button
            onClick={onCancel}
            disabled={isSubmitting}
            color="inherit"
            sx={{ mr: 1 }}
          >
            Cancel
          </Button>
        )}
        <Button
          type="submit"
          variant="contained"
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={16} /> : <AccountBalanceIcon />}
          onClick={handleSubmit}
          sx={{
            minWidth: 140,
            fontWeight: 500,
          }}
        >
          {isSubmitting ? 'Creating...' : 'Create Account'}
        </Button>
      </CardActions>
    </Card>
  );
};

export default AccountCreationForm;