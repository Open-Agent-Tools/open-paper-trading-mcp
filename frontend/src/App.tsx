import React from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import theme from './theme';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Account from './pages/Account';
import AccountsList from './pages/AccountsList';
import Orders from './pages/Orders';
import StockResearch from './pages/StockResearch';
import { AccountProvider } from './contexts/AccountContext';
import { LoadingProvider } from './contexts/LoadingContext';
import GlobalLoadingIndicator from './components/GlobalLoadingIndicator';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <AccountsList /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'research', element: <StockResearch /> },
      { path: 'orders', element: <Orders /> },
      { path: 'account', element: <Account /> },
    ],
  },
]);

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <LoadingProvider>
        <AccountProvider>
          <GlobalLoadingIndicator variant="topbar" showDetails={true} />
          <RouterProvider router={router} />
        </AccountProvider>
      </LoadingProvider>
    </ThemeProvider>
  );
};

export default App;
