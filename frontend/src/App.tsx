import React from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import theme from './theme';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Account from './pages/Account';
import AccountsList from './pages/AccountsList';
import Orders from './pages/Orders';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <AccountsList /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'account', element: <Account /> },
      { path: 'orders', element: <Orders /> },
    ],
  },
]);

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <RouterProvider router={router} />
    </ThemeProvider>
  );
};

export default App;
