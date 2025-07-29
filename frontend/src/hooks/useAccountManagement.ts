import { useState, useEffect, useCallback } from 'react';
import { 
  getAllAccounts, 
  createAccount, 
  deleteAccount, 
  getAccountDetails 
} from '../services/accountApi';
import type { 
  AccountSummary, 
  CreateAccountRequest, 
  AccountsResponse 
} from '../types/account';

interface UseAccountManagementReturn {
  // State
  accounts: AccountSummary[];
  selectedAccount: AccountSummary | null;
  loading: boolean;
  error: string | null;
  summary: AccountsResponse['summary'] | null;
  
  // Actions
  loadAccounts: () => Promise<void>;
  createNewAccount: (data: CreateAccountRequest) => Promise<string>;
  selectAccount: (account: AccountSummary) => void;
  removeAccount: (accountId: string) => Promise<void>;
  refreshAccount: (accountId: string) => Promise<void>;
  clearSelection: () => void;
  clearError: () => void;
}

export const useAccountManagement = (): UseAccountManagementReturn => {
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<AccountsResponse['summary'] | null>(null);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await getAllAccounts();
      if (response.success) {
        setAccounts(response.accounts);
        setSummary(response.summary);
        
        // Update selected account if it still exists
        if (selectedAccount) {
          const updatedAccount = response.accounts.find(acc => acc.id === selectedAccount.id);
          if (updatedAccount) {
            setSelectedAccount(updatedAccount);
          } else {
            setSelectedAccount(null);
          }
        }
      } else {
        throw new Error(response.message || 'Failed to load accounts');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      console.error('Failed to load accounts:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedAccount]);

  const createNewAccount = useCallback(async (data: CreateAccountRequest): Promise<string> => {
    setError(null);
    
    try {
      const response = await createAccount(data);
      if (response.success) {
        // Reload accounts to include the new one
        await loadAccounts();
        return response.account_id;
      } else {
        throw new Error(response.message || 'Failed to create account');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create account';
      setError(errorMessage);
      throw err;
    }
  }, [loadAccounts]);

  const selectAccount = useCallback((account: AccountSummary) => {
    setSelectedAccount(account);
    setError(null);
  }, []);

  const removeAccount = useCallback(async (accountId: string): Promise<void> => {
    setError(null);
    
    try {
      const response = await deleteAccount(accountId);
      if (response.success) {
        // Remove from local state
        setAccounts(prev => prev.filter(acc => acc.id !== accountId));
        
        // Clear selection if deleted account was selected
        if (selectedAccount?.id === accountId) {
          setSelectedAccount(null);
        }
        
        // Reload to get updated summary
        await loadAccounts();
      } else {
        throw new Error(response.message || 'Failed to delete account');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete account';
      setError(errorMessage);
      throw err;
    }
  }, [selectedAccount, loadAccounts]);

  const refreshAccount = useCallback(async (accountId: string): Promise<void> => {
    setError(null);
    
    try {
      const response = await getAccountDetails(accountId);
      if (response.success) {
        // Update the account in the list
        setAccounts(prev => 
          prev.map(acc => acc.id === accountId ? response.account : acc)
        );
        
        // Update selected account if it's the one being refreshed
        if (selectedAccount?.id === accountId) {
          setSelectedAccount(response.account);
        }
      } else {
        throw new Error(response.message || 'Failed to refresh account');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to refresh account';
      setError(errorMessage);
      console.error('Failed to refresh account:', err);
    }
  }, [selectedAccount]);

  const clearSelection = useCallback(() => {
    setSelectedAccount(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Load accounts on mount
  useEffect(() => {
    loadAccounts();
  }, []);

  return {
    // State
    accounts,
    selectedAccount,
    loading,
    error,
    summary,
    
    // Actions
    loadAccounts,
    createNewAccount,
    selectAccount,
    removeAccount,
    refreshAccount,
    clearSelection,
    clearError,
  };
};

export default useAccountManagement;