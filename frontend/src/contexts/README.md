# Account Context Management System

This document explains how to use the Account Context system in the Open Paper Trading MCP SPA.

## Overview

The Account Context provides centralized management of:
- Currently selected trading account
- Available accounts list
- Account switching functionality
- Persistent account selection (localStorage)
- Account validation and error handling

## Files

### Core Context Files
- **`AccountContext.tsx`** - Main context provider with state management
- **`AccountSelector.tsx`** - UI component for account selection in navigation
- **`AccountGuard.tsx`** - Wrapper component that ensures account selection

### Integration Files
- **`App.tsx`** - Root-level AccountProvider integration
- **`Layout.tsx`** - Navigation with AccountSelector components
- **Examples in pages/** - Dashboard, Orders, StockResearch with context usage

## Quick Start

### 1. Setup (Already Done)

The AccountProvider is already integrated at the root level in `App.tsx`:

```tsx
<AccountProvider>
  <RouterProvider router={router} />
</AccountProvider>
```

### 2. Using Account Context in Components

#### Option A: For components that REQUIRE an account

```tsx
import { useRequireAccount } from '../contexts/AccountContext';

const MyTradingComponent: React.FC = () => {
  // This will throw an error if no account is selected
  const selectedAccount = useRequireAccount();
  
  return (
    <div>
      <h2>Trading as: {selectedAccount.owner}</h2>
      <p>Balance: ${selectedAccount.current_balance}</p>
      {/* Your trading UI here */}
    </div>
  );
};
```

#### Option B: For components that can work without an account

```tsx
import { useAccountContext } from '../contexts/AccountContext';

const MyComponent: React.FC = () => {
  const { selectedAccount, availableAccounts, selectAccount } = useAccountContext();
  
  if (!selectedAccount) {
    return <div>Please select an account first</div>;
  }
  
  return (
    <div>
      <h2>Account: {selectedAccount.owner}</h2>
      {/* Your component UI here */}
    </div>
  );
};
```

### 3. Using AccountGuard for Page-Level Protection

Wrap entire pages that require account selection:

```tsx
import AccountGuard from '../components/account/AccountGuard';

const Dashboard: React.FC = () => {
  return (
    <AccountGuard
      fallbackMessage="Please select a trading account to view your dashboard."
      showAccountSelector={true}
    >
      {/* Your dashboard content here */}
    </AccountGuard>
  );
};
```

### 4. Adding Account Selector to Navigation

Already integrated in `Layout.tsx`:

```tsx
{/* Desktop Navigation */}
<AccountSelector 
  variant="button" 
  showBalance={true} 
  showCreateOption={true}
/>

{/* Mobile Navigation */}
<AccountSelector 
  variant="compact" 
  showBalance={false} 
  showCreateOption={true}
/>
```

## Component API Reference

### AccountContext Hook

```tsx
const {
  // State
  selectedAccount,      // Currently selected account or null
  availableAccounts,    // Array of all available accounts
  isLoading,           // Loading state for async operations
  error,               // Error message or null
  isInitialized,       // Whether context has finished initial setup
  
  // Actions
  selectAccount,       // (account: AccountSummary) => void
  clearAccount,        // () => void - clear selection
  refreshAccounts,     // () => Promise<void> - reload from API
  setError,           // (error: string | null) => void
  clearError,         // () => void
} = useAccountContext();
```

### AccountSelector Component

```tsx
<AccountSelector
  variant="button" | "compact" | "chip"  // Display style
  showBalance={boolean}                   // Show account balance
  showCreateOption={boolean}              // Show "Create Account" option
  className={string}                      // CSS class name
/>
```

**Variants:**
- **`button`** - Full button with account name and balance (desktop)
- **`compact`** - Small button for mobile/constrained spaces
- **`chip`** - Chip-style display for inline use

### AccountGuard Component

```tsx
<AccountGuard
  fallbackMessage="Custom message when no account selected"
  showAccountSelector={boolean}     // Show account selector in fallback
  redirectTo="/custom-path"         // Where to redirect for account creation
  requireAccount={boolean}          // Whether account is required (default: true)
>
  {children}
</AccountGuard>
```

## Best Practices

### 1. Choose the Right Hook

- Use **`useRequireAccount()`** for components that cannot function without an account
- Use **`useAccountContext()`** for components that can gracefully handle missing accounts

### 2. Handle Loading States

```tsx
const { selectedAccount, isLoading, isInitialized } = useAccountContext();

if (!isInitialized) {
  return <LoadingSpinner />;
}

if (isLoading) {
  return <div>Refreshing accounts...</div>;
}
```

### 3. Account-Aware API Calls

Always include the selected account ID in API calls:

```tsx
const { selectedAccount } = useAccountContext();

const placeOrder = async (orderData) => {
  if (!selectedAccount) return;
  
  await fetch('/api/orders', {
    method: 'POST',
    body: JSON.stringify({
      account_id: selectedAccount.id,
      ...orderData
    })
  });
};
```

### 4. Custom Hooks with Account Context

Create reusable hooks that automatically use the selected account:

```tsx
const useAccountOrders = () => {
  const { selectedAccount } = useAccountContext();
  const [orders, setOrders] = useState([]);
  
  const fetchOrders = useCallback(async () => {
    if (!selectedAccount) return;
    
    const response = await fetch(`/api/accounts/${selectedAccount.id}/orders`);
    const data = await response.json();
    setOrders(data.orders);
  }, [selectedAccount]);
  
  return { orders, fetchOrders };
};
```

### 5. Error Handling

```tsx
const { error, clearError } = useAccountContext();

if (error) {
  return (
    <Alert severity="error" onClose={clearError}>
      {error}
    </Alert>
  );
}
```

## Integration Examples

### Page-Level Integration

```tsx
// Dashboard.tsx
import AccountGuard from '../components/account/AccountGuard';
import { useAccountContext } from '../contexts/AccountContext';

const Dashboard: React.FC = () => {
  const { selectedAccount } = useAccountContext();
  
  return (
    <AccountGuard>
      <div>
        <h1>Dashboard for {selectedAccount.owner}</h1>
        {/* Dashboard content */}
      </div>
    </AccountGuard>
  );
};
```

### Component-Level Integration

```tsx
// TradingForm.tsx
import { useRequireAccount } from '../contexts/AccountContext';

const TradingForm: React.FC = () => {
  const account = useRequireAccount();
  
  const handleSubmit = async (formData) => {
    await fetch('/api/orders', {
      method: 'POST',
      body: JSON.stringify({
        account_id: account.id,
        ...formData
      })
    });
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <div>Trading as: {account.owner}</div>
      <div>Available: ${account.current_balance}</div>
      {/* Form fields */}
    </form>
  );
};
```

### Navigation Integration

```tsx
// Already integrated in Layout.tsx
<AccountSelector 
  variant="button"
  showBalance={true}
  showCreateOption={true}
/>
```

## TypeScript Interfaces

```tsx
interface AccountSummary {
  id: string;
  owner: string;
  created_at: string;
  starting_balance: number;
  current_balance: number;
  balance_change: number;
  balance_change_percent: number;
}

interface AccountContextState {
  selectedAccount: AccountSummary | null;
  availableAccounts: AccountSummary[];
  isLoading: boolean;
  error: string | null;
  isInitialized: boolean;
}

interface AccountContextActions {
  selectAccount: (account: AccountSummary) => void;
  clearAccount: () => void;
  refreshAccounts: () => Promise<void>;
  setError: (error: string | null) => void;
  clearError: () => void;
}
```

## Local Storage

The context automatically persists:
- **Selected account** to `openPaperTrading_selectedAccount`
- **Account cache** to `openPaperTrading_accountsCache` (5-minute TTL)
- **Cache expiry** to `openPaperTrading_cacheExpiry`

Data is automatically restored on app load and validated against the API.

## Error Handling

The context handles:
- **Network errors** during account fetching
- **Account validation** (ensures selected account still exists)
- **Cache invalidation** when accounts change
- **Graceful degradation** when API is unavailable

## Performance Considerations

- **Caching**: Accounts are cached for 5 minutes to reduce API calls
- **Lazy loading**: Context only fetches data on first access
- **Validation**: Selected account is validated on app startup
- **Cleanup**: Automatic cleanup of event listeners and timers

## Migration Guide

If you have existing components that manage account state locally:

1. **Remove local account state**:
   ```tsx
   // Remove this
   const [selectedAccount, setSelectedAccount] = useState(null);
   ```

2. **Add context hook**:
   ```tsx
   // Add this
   const { selectedAccount, selectAccount } = useAccountContext();
   ```

3. **Wrap with AccountGuard** (if account is required):
   ```tsx
   return (
     <AccountGuard>
       {/* Your component */}
     </AccountGuard>
   );
   ```

4. **Update API calls** to use account ID from context:
   ```tsx
   // Before
   fetch(`/api/orders?account=${localAccountId}`)
   
   // After
   fetch(`/api/orders?account=${selectedAccount.id}`)
   ```

This system provides a robust, type-safe, and user-friendly way to manage account context throughout the application.