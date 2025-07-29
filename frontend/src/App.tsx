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
      <AccountProvider>
        <RouterProvider router={router} />
      </AccountProvider>
    </ThemeProvider>
  );
};

export default App;
