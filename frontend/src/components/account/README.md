# Account Management Components

A comprehensive React TypeScript component library for managing trading accounts in the Open Paper Trading MCP application.

## Components Overview

### 1. AccountCreationForm
A form component for creating new trading accounts with validation and error handling.

**Features:**
- Account owner name validation (2-100 characters)
- Optional account name field
- Starting balance validation ($100 - $10,000,000)
- Account type selection (Individual, Joint, Corporate, Trust)
- Real-time form validation with error messages
- Loading states and success feedback
- Currency formatting for balance display

**Props:**
```typescript
interface AccountCreationFormProps {
  onAccountCreated?: (accountId: string) => void;
  onCancel?: () => void;
}
```

**Usage:**
```tsx
import { AccountCreationForm } from './components/account';

<AccountCreationForm
  onAccountCreated={(accountId) => console.log('Created:', accountId)}
  onCancel={() => setShowForm(false)}
/>
```

### 2. AccountSelectionGrid
A responsive grid component for displaying and selecting trading accounts.

**Features:**
- Responsive card-based layout
- Real-time search by owner name or account ID
- Account performance indicators (profit/loss)
- Account balance and creation date display
- Individual account selection with visual feedback
- Account deletion with confirmation
- Empty state handling
- Loading skeletons

**Props:**
```typescript
interface AccountSelectionGridProps {
  onAccountSelected: (account: AccountSummary) => void;
  onAccountDeleted?: (accountId: string) => void;
  selectedAccountId?: string;
}
```

**Usage:**
```tsx
import { AccountSelectionGrid } from './components/account';

<AccountSelectionGrid
  onAccountSelected={(account) => setSelectedAccount(account)}
  onAccountDeleted={(id) => handleAccountDeleted(id)}
  selectedAccountId={currentAccount?.id}
/>
```

### 3. AccountDeletionDialog
A confirmation dialog for safely deleting trading accounts.

**Features:**
- Two-step confirmation process
- Complete account details display
- Data loss warnings
- Performance metrics overview
- Loading states during deletion
- Error handling with retry options

**Props:**
```typescript
interface AccountDeletionDialogProps {
  open: boolean;
  account: AccountSummary | null;
  onClose: () => void;
  onAccountDeleted?: (accountId: string) => void;
}
```

**Usage:**
```tsx
import { AccountDeletionDialog } from './components/account';

<AccountDeletionDialog
  open={showDeleteDialog}
  account={accountToDelete}
  onClose={() => setShowDeleteDialog(false)}
  onAccountDeleted={(id) => handleDeleted(id)}
/>
```

### 4. AccountManagementDashboard
The main dashboard component that combines all account management functionality.

**Features:**
- Tabbed interface (Create/Select)
- Breadcrumb navigation
- Selected account status display
- Mobile-responsive design with floating action button
- Global snackbar notifications
- Account summary statistics

**Props:**
```typescript
interface AccountManagementDashboardProps {
  onAccountSelected?: (account: AccountSummary) => void;
  initialTab?: number;
}
```

**Usage:**
```tsx
import { AccountManagementDashboard } from './components/account';

<AccountManagementDashboard
  onAccountSelected={(account) => navigateToTrading(account)}
  initialTab={1} // Start with selection tab
/>
```

## Custom Hook

### useAccountManagement
A custom hook that provides account management state and actions.

**Features:**
- Account list management
- Selected account state
- Loading and error states
- CRUD operations for accounts
- Automatic data synchronization

**Return Value:**
```typescript
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
```

**Usage:**
```tsx
import { useAccountManagement } from '../hooks/useAccountManagement';

const MyComponent = () => {
  const {
    accounts,
    selectedAccount,
    loading,
    error,
    loadAccounts,
    createNewAccount,
    selectAccount
  } = useAccountManagement();

  // Use the hook data and methods...
};
```

## API Services

### accountApi.ts
Centralized API client for account management operations.

**Available Functions:**
- `getAllAccounts()` - Fetch all accounts with summary
- `createAccount(data)` - Create new trading account
- `deleteAccount(accountId)` - Delete existing account
- `getAccountBalance(accountId)` - Get current balance
- `getAccountDetails(accountId)` - Get detailed account info
- `getAccountsSummary()` - Get accounts summary statistics

## Type Definitions

### Core Types
```typescript
export interface AccountSummary {
  id: string;
  owner: string;
  created_at: string;
  starting_balance: number;
  current_balance: number;
  balance_change: number;
  balance_change_percent: number;
}

export interface CreateAccountRequest {
  owner: string;
  starting_balance: number;
  name?: string;
}

export type AccountType = 'individual' | 'joint' | 'corporate' | 'trust';
```

## Styling and Theme

All components follow the Material UI design system and integrate with the application's custom theme:

**Color Palette:**
- Primary Blue: `#1f4788`
- Success Green: `#006b3c`
- Error Red: `#dc3545`
- Warning Orange: `#b45309`

**Typography:**
- Primary Font: `'Roboto', sans-serif`
- Monospace Font: `'Roboto Mono', monospace`

**Responsive Breakpoints:**
- Mobile: `< 600px`
- Tablet: `600px - 960px`
- Desktop: `> 960px`

## Accessibility Features

- Full keyboard navigation support
- ARIA labels and descriptions
- Screen reader compatible
- High contrast color ratios (WCAG 2.1 AA)
- Focus management for modals and dialogs
- Semantic HTML structure

## Error Handling

All components include comprehensive error handling:

- Network error detection and user-friendly messages
- Form validation with real-time feedback
- API error parsing and display
- Retry mechanisms for failed operations
- Loading state management

## Testing Considerations

When testing these components:

1. **API Mocking**: Mock the `accountApi` functions
2. **User Interactions**: Test form submissions, button clicks, search
3. **Error States**: Test network failures and validation errors  
4. **Loading States**: Test loading spinners and skeleton screens
5. **Responsive Design**: Test across different screen sizes

## Integration Example

Here's a complete example of integrating the account management system:

```tsx
import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { AccountManagementDashboard } from './components/account';
import theme from './theme';

const App: React.FC = () => {
  const handleAccountSelected = (account) => {
    // Navigate to trading dashboard or update global state
    console.log('Selected account:', account);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AccountManagementDashboard
        onAccountSelected={handleAccountSelected}
      />
    </ThemeProvider>
  );
};

export default App;
```

## Future Enhancements

Potential improvements for the account management system:

1. **Bulk Operations**: Select and manage multiple accounts
2. **Account Templates**: Pre-configured account types
3. **Import/Export**: Account data portability
4. **Advanced Filtering**: Filter by balance, performance, date
5. **Account Sharing**: Collaborative account management
6. **Audit Logs**: Track account modifications
7. **Backup/Restore**: Account data protection