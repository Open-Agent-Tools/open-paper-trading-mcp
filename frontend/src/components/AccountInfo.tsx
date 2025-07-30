import React, { useEffect, useState } from 'react';
import { Card, CardContent, Typography, CircularProgress, Alert } from '@mui/material';
import { getAccountInfo } from '../services/apiClient';
import { useAccountContext } from '../contexts/AccountContext';
import type { AccountInfo as AccountInfoType } from '../types';

const AccountInfo: React.FC = () => {
  const { selectedAccount } = useAccountContext();
  const [accountInfo, setAccountInfo] = useState<AccountInfoType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAccountInfo = async () => {
      if (!selectedAccount) {
        setError('No account selected. Please choose an account from the dropdown.');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const response = await getAccountInfo(selectedAccount.id);
        if (response.success && response.account) {
          // Extract the account data from the API response
          setAccountInfo({
            owner: response.account.owner,
            cash_balance: response.account.cash_balance,
          });
        } else {
          setError('Failed to fetch account information.');
        }
      } catch (err) {
        setError('Failed to fetch account information.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchAccountInfo();
  }, [selectedAccount]);

  if (loading) {
    return <CircularProgress />;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Account Information
        </Typography>
        {selectedAccount && (
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Account ID: {selectedAccount.id}
          </Typography>
        )}
        {accountInfo ? (
          <>
            <Typography variant="body1">
              <strong>Owner:</strong> {accountInfo.owner}
            </Typography>
            <Typography variant="body1">
              <strong>Cash Balance:</strong> ${accountInfo.cash_balance.toLocaleString()}
            </Typography>
          </>
        ) : !loading && !error ? (
          <Typography>No account information available.</Typography>
        ) : null}
      </CardContent>
    </Card>
  );
};

export default AccountInfo;
