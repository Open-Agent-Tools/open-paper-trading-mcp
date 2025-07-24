import React, { useEffect, useState } from 'react';
import { Card, CardContent, Typography, CircularProgress, Alert } from '@mui/material';
import { getAccountInfo } from '../services/apiClient';
import type { AccountInfo as AccountInfoType } from '../types';

const AccountInfo: React.FC = () => {
  const [accountInfo, setAccountInfo] = useState<AccountInfoType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAccountInfo = async () => {
      try {
        const data = await getAccountInfo();
        setAccountInfo(data);
      } catch (err) {
        setError('Failed to fetch account information.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchAccountInfo();
  }, []);

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
        {accountInfo ? (
          <>
            <Typography variant="body1">
              <strong>Owner:</strong> {accountInfo.owner}
            </Typography>
            <Typography variant="body1">
              <strong>Cash Balance:</strong> ${accountInfo.cash_balance.toLocaleString()}
            </Typography>
          </>
        ) : (
          <Typography>No account information available.</Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default AccountInfo;
