import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react';
import type { AccountSummary, AccountsResponse } from '../types/account';

// API base URL configuration - use direct backend URL during development
const API_BASE_URL = import.meta.env.DEV 
  ? 'http://localhost:2080/api/v1/trading'  // Direct backend call
  : '/api/v1/trading';  // Proxy/relative path for production

// Account Context Types
export interface AccountContextState {
  selectedAccount: AccountSummary | null;
  availableAccounts: AccountSummary[];
  isLoading: boolean;
  error: string | null;
  isInitialized: boolean;
}

export interface AccountContextActions {
  selectAccount: (account: AccountSummary) => void;
  clearAccount: () => void;
  refreshAccounts: () => Promise<void>;
  setError: (error: string | null) => void;
  clearError: () => void;
}

export interface AccountContextValue extends AccountContextState, AccountContextActions {}

// Action Types
type AccountAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_ACCOUNTS'; payload: AccountSummary[] }
  | { type: 'SELECT_ACCOUNT'; payload: AccountSummary }
  | { type: 'CLEAR_ACCOUNT' }
  | { type: 'SET_INITIALIZED'; payload: boolean };

// Initial State
const initialState: AccountContextState = {
  selectedAccount: null,
  availableAccounts: [],
  isLoading: false,
  error: null,
  isInitialized: false,
};

// Reducer Function
function accountReducer(state: AccountContextState, action: AccountAction): AccountContextState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    case 'SET_ACCOUNTS':
      return { ...state, availableAccounts: action.payload, isLoading: false, error: null };
    case 'SELECT_ACCOUNT':
      return { ...state, selectedAccount: action.payload, error: null };
    case 'CLEAR_ACCOUNT':
      return { ...state, selectedAccount: null };
    case 'SET_INITIALIZED':
      return { ...state, isInitialized: action.payload };
    default:
      return state;
  }
}

// Local Storage Keys
const SELECTED_ACCOUNT_KEY = 'openPaperTrading_selectedAccount';
const ACCOUNTS_CACHE_KEY = 'openPaperTrading_accountsCache';
const CACHE_EXPIRY_KEY = 'openPaperTrading_cacheExpiry';
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

// Utility Functions
const saveToLocalStorage = (key: string, data: any) => {
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.warn('Failed to save to localStorage:', error);
  }
};

const loadFromLocalStorage = (key: string) => {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : null;
  } catch (error) {
    console.warn('Failed to load from localStorage:', error);
    return null;
  }
};

const isCacheValid = (): boolean => {
  const expiry = loadFromLocalStorage(CACHE_EXPIRY_KEY);
  return expiry ? new Date().getTime() < expiry : false;
};

// API Functions
const fetchAccounts = async (): Promise<AccountSummary[]> => {
  const response = await fetch(`${API_BASE_URL}/accounts`);
  if (!response.ok) {
    throw new Error(`Failed to fetch accounts: ${response.status} ${response.statusText}`);
  }
  
  const data: AccountsResponse = await response.json();
  if (!data.success) {
    throw new Error(data.message || 'Failed to fetch accounts');
  }
  
  return data.accounts;
};

const validateAccountExists = async (accountId: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/accounts/${accountId}/balance`);
    return response.ok;
  } catch {
    return false;
  }
};

// Create Context
const AccountContext = createContext<AccountContextValue | undefined>(undefined);

// Account Provider Component
interface AccountProviderProps {
  children: React.ReactNode;
}

export const AccountProvider: React.FC<AccountProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(accountReducer, initialState);

  // Load cached data on mount
  useEffect(() => {
    const loadCachedData = async () => {
      dispatch({ type: 'SET_LOADING', payload: true });
      
      try {
        // Load cached accounts if valid
        if (isCacheValid()) {
          const cachedAccounts = loadFromLocalStorage(ACCOUNTS_CACHE_KEY);
          if (cachedAccounts && Array.isArray(cachedAccounts)) {
            dispatch({ type: 'SET_ACCOUNTS', payload: cachedAccounts });
          }
        } else {
          // Fetch fresh accounts
          const accounts = await fetchAccounts();
          dispatch({ type: 'SET_ACCOUNTS', payload: accounts });
          
          // Cache the results
          saveToLocalStorage(ACCOUNTS_CACHE_KEY, accounts);
          saveToLocalStorage(CACHE_EXPIRY_KEY, new Date().getTime() + CACHE_DURATION);
        }

        // Load selected account and validate it still exists
        const savedAccount = loadFromLocalStorage(SELECTED_ACCOUNT_KEY);
        if (savedAccount) {
          const exists = await validateAccountExists(savedAccount.id);
          if (exists) {
            dispatch({ type: 'SELECT_ACCOUNT', payload: savedAccount });
          } else {
            // Account no longer exists, clear from storage
            localStorage.removeItem(SELECTED_ACCOUNT_KEY);
            dispatch({ type: 'SET_ERROR', payload: 'Previously selected account no longer exists' });
          }
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to load account data';
        dispatch({ type: 'SET_ERROR', payload: errorMessage });
        console.error('Error loading account data:', error);
      } finally {
        dispatch({ type: 'SET_INITIALIZED', payload: true });
      }
    };

    loadCachedData();
  }, []);

  // Action Implementations
  const selectAccount = useCallback((account: AccountSummary) => {
    dispatch({ type: 'SELECT_ACCOUNT', payload: account });
    saveToLocalStorage(SELECTED_ACCOUNT_KEY, account);
    
    // Clear any existing errors
    dispatch({ type: 'SET_ERROR', payload: null });
  }, []);

  const clearAccount = useCallback(() => {
    dispatch({ type: 'CLEAR_ACCOUNT' });
    localStorage.removeItem(SELECTED_ACCOUNT_KEY);
  }, []);

  const refreshAccounts = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });
    
    try {
      const accounts = await fetchAccounts();
      dispatch({ type: 'SET_ACCOUNTS', payload: accounts });
      
      // Update cache
      saveToLocalStorage(ACCOUNTS_CACHE_KEY, accounts);
      saveToLocalStorage(CACHE_EXPIRY_KEY, new Date().getTime() + CACHE_DURATION);
      
      // Validate selected account still exists
      if (state.selectedAccount) {
        const stillExists = accounts.some(account => account.id === state.selectedAccount?.id);
        if (!stillExists) {
          clearAccount();
          dispatch({ type: 'SET_ERROR', payload: 'Selected account was deleted' });
        } else {
          // Update selected account with fresh data
          const updatedAccount = accounts.find(account => account.id === state.selectedAccount?.id);
          if (updatedAccount) {
            selectAccount(updatedAccount);
          }
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to refresh accounts';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
      console.error('Error refreshing accounts:', error);
    }
  }, [state.selectedAccount, selectAccount, clearAccount]);

  const setError = useCallback((error: string | null) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'SET_ERROR', payload: null });
  }, []);

  // Context Value
  const contextValue: AccountContextValue = {
    // State
    selectedAccount: state.selectedAccount,
    availableAccounts: state.availableAccounts,
    isLoading: state.isLoading,
    error: state.error,
    isInitialized: state.isInitialized,
    // Actions
    selectAccount,
    clearAccount,
    refreshAccounts,
    setError,
    clearError,
  };

  return (
    <AccountContext.Provider value={contextValue}>
      {children}
    </AccountContext.Provider>
  );
};

// Custom Hook
export const useAccountContext = (): AccountContextValue => {
  const context = useContext(AccountContext);
  if (context === undefined) {
    throw new Error('useAccountContext must be used within an AccountProvider');
  }
  return context;
};

// Hook for checking if an account is selected
export const useRequireAccount = (): AccountSummary => {
  const { selectedAccount } = useAccountContext();
  if (!selectedAccount) {
    throw new Error('No account selected. Please select an account first.');
  }
  return selectedAccount;
};

export default AccountContext;