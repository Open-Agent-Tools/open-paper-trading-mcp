# Account Management Integration Guide

This guide shows how to integrate the comprehensive account management system into your Open Paper Trading MCP frontend application.

## Files Created

### Core Components
- `frontend/src/components/account/AccountCreationForm.tsx` - Account creation form with validation
- `frontend/src/components/account/AccountSelectionGrid.tsx` - Responsive account selection grid
- `frontend/src/components/account/AccountDeletionDialog.tsx` - Safe account deletion with confirmation
- `frontend/src/components/account/AccountManagementDashboard.tsx` - Main dashboard combining all flows
- `frontend/src/components/account/index.ts` - Component exports

### Hooks and Services
- `frontend/src/hooks/useAccountManagement.ts` - Custom hook for account state management
- `frontend/src/services/accountApi.ts` - Dedicated API client for account operations
- `frontend/src/types/account.ts` - TypeScript interfaces for account data

### Pages and Examples
- `frontend/src/pages/AccountManagement.tsx` - Complete account management page
- `frontend/src/examples/AccountManagementExample.tsx` - Integration example
- `frontend/src/components/account/README.md` - Detailed component documentation

## Quick Integration Steps

### 1. Add to Your Router

```tsx
// In your main App.tsx or router configuration
import AccountManagementPage from './pages/AccountManagement';

// Add to your routes
<Route path="/accounts" element={<AccountManagementPage />} />
```

### 2. Use Individual Components

```tsx
// Import specific components
import { AccountManagementDashboard } from './components/account';

// Use in your component
<AccountManagementDashboard
  onAccountSelected={(account) => {
    // Handle account selection - navigate to trading, update state, etc.
    console.log('Selected account:', account);
  }}
/>
```

### 3. Use the Custom Hook

```tsx
import { useAccountManagement } from './hooks/useAccountManagement';

const MyComponent = () => {
  const {
    accounts,
    selectedAccount,
    loading,
    error,
    createNewAccount,
    selectAccount,
    removeAccount
  } = useAccountManagement();

  // Your component logic here
};
```

## API Endpoints Required

The components expect these FastAPI endpoints to be available:

- `GET /api/v1/trading/accounts` - List all accounts
- `POST /api/v1/trading/accounts` - Create new account
- `GET /api/v1/trading/accounts/{account_id}` - Get account details
- `DELETE /api/v1/trading/accounts/{account_id}` - Delete account
- `GET /api/v1/trading/accounts/{account_id}/balance` - Get account balance
- `GET /api/v1/trading/accounts/summary` - Get accounts summary

## Component Features

### AccountCreationForm
- ✅ Form validation with real-time feedback
- ✅ Account owner name (2-100 characters)
- ✅ Optional account name field
- ✅ Starting balance ($100 - $10,000,000)
- ✅ Account type selection
- ✅ Loading states and error handling
- ✅ Success feedback with account ID
- ✅ Currency formatting

### AccountSelectionGrid
- ✅ Responsive card-based layout
- ✅ Real-time search functionality
- ✅ Account performance indicators
- ✅ Balance and creation date display
- ✅ Visual selection feedback
- ✅ Account deletion with menu
- ✅ Empty state handling
- ✅ Loading skeletons

### AccountDeletionDialog
- ✅ Two-step confirmation process
- ✅ Complete account details display
- ✅ Data loss warnings
- ✅ Performance metrics overview
- ✅ Loading states during deletion
- ✅ Error handling

### AccountManagementDashboard
- ✅ Tabbed interface (Create/Select)
- ✅ Breadcrumb navigation
- ✅ Selected account status
- ✅ Mobile-responsive design
- ✅ Floating action button (mobile)
- ✅ Global notifications
- ✅ Account summary statistics

## Theme Integration

All components use your existing Material UI theme:

```tsx
// Your theme colors are automatically applied
const theme = createTheme({
  palette: {
    primary: { main: '#1f4788' },     // Primary blue
    secondary: { main: '#1f7a4f' },   // Primary green
    success: { main: '#006b3c' },     // Success green
    error: { main: '#dc3545' },       // Error red
    warning: { main: '#b45309' },     // Warning orange
  },
});
```

## Responsive Design

The components are fully responsive:

- **Mobile** (< 600px): Single column layout, floating action button
- **Tablet** (600px - 960px): Two column grid, optimized spacing
- **Desktop** (> 960px): Three+ column grid, full feature set

## Accessibility Features

- ✅ Full keyboard navigation
- ✅ ARIA labels and descriptions
- ✅ Screen reader compatibility
- ✅ High contrast ratios (WCAG 2.1 AA)
- ✅ Focus management
- ✅ Semantic HTML

## Error Handling

Comprehensive error handling throughout:

- Network error detection with user-friendly messages
- Form validation with real-time feedback
- API error parsing and display
- Retry mechanisms for failed operations
- Loading state management

## Type Safety

Full TypeScript support with comprehensive interfaces:

```typescript
// All components are fully typed
interface AccountSummary {
  id: string;
  owner: string;
  created_at: string;
  starting_balance: number;
  current_balance: number;
  balance_change: number;
  balance_change_percent: number;
}
```

## Performance Optimizations

- React.memo for component optimization
- Efficient re-rendering with proper dependency arrays
- Skeleton loading states for better perceived performance
- Debounced search functionality
- Optimistic updates where appropriate

## Navigation Integration

### Option 1: Direct Navigation
```tsx
const handleAccountSelected = (account: AccountSummary) => {
  // Navigate to trading dashboard
  navigate(`/trading?account=${account.id}`);
};
```

### Option 2: Global State Integration
```tsx
// With Redux or Zustand
const handleAccountSelected = (account: AccountSummary) => {
  dispatch(setActiveAccount(account));
  navigate('/trading');
};
```

### Option 3: Context Integration
```tsx
// With React Context
const { setCurrentAccount } = useAccountContext();

const handleAccountSelected = (account: AccountSummary) => {
  setCurrentAccount(account);
  navigate('/trading');
};
```

## Testing Integration

Example test setup:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { AccountManagementDashboard } from './components/account';
import theme from './theme';

// Mock the API
jest.mock('./services/accountApi', () => ({
  getAllAccounts: jest.fn(() => Promise.resolve({
    success: true,
    accounts: [],
    summary: { total_count: 0, total_current_balance: 0, total_balance_change: 0 }
  }))
}));

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

test('renders account management dashboard', async () => {
  renderWithTheme(<AccountManagementDashboard />);
  
  await waitFor(() => {
    expect(screen.getByText('Account Management')).toBeInTheDocument();
  });
});
```

## Migration from Existing Components

If you have existing account components, here's how to migrate:

1. **Replace existing AccountModal**:
   ```tsx
   // Old
   <CreateAccountModal open={open} onClose={onClose} />
   
   // New
   <AccountCreationForm onAccountCreated={handleCreated} onCancel={onClose} />
   ```

2. **Replace existing AccountsGrid**:
   ```tsx
   // Old
   <AccountsGrid accounts={accounts} onSelect={onSelect} />
   
   // New
   <AccountSelectionGrid 
     onAccountSelected={onSelect}
     selectedAccountId={currentId}
   />
   ```

3. **Use the new hook instead of manual state**:
   ```tsx
   // Old
   const [accounts, setAccounts] = useState([]);
   const [loading, setLoading] = useState(false);
   // ... manual API calls
   
   // New
   const { accounts, loading, loadAccounts } = useAccountManagement();
   ```

## Next Steps

1. **Deploy the components** to your frontend
2. **Test the API integration** with your FastAPI backend
3. **Customize the styling** to match your brand
4. **Add navigation** to your existing router
5. **Integrate with your trading dashboard**

## Support and Customization

The components are designed to be highly customizable:

- Override theme colors and typography
- Customize form validation rules
- Add additional account fields
- Extend the API with additional endpoints
- Add custom business logic to the hooks

For questions or customization needs, refer to the component README files or the example implementations provided.