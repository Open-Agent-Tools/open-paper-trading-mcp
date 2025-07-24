import React from 'react';
import { AppBar, Toolbar, Typography, Button, Container, Box, useMediaQuery, IconButton, Menu, MenuItem } from '@mui/material';
import { Link as RouterLink, Outlet } from 'react-router-dom';
import Footer from './Footer';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import { useTheme } from '@mui/material/styles';

const Layout: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Open Paper Trading
          </Typography>
          {isMobile ? (
            <>
              <IconButton
                size="large"
                edge="start"
                color="inherit"
                aria-label="menu"
                onClick={handleMenu}
                sx={{ ml: 2 }}
              >
                <MenuIcon />
              </IconButton>
              <Menu
                id="menu-appbar"
                anchorEl={anchorEl}
                anchorOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                keepMounted
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                open={Boolean(anchorEl)}
                onClose={handleClose}
              >
                <MenuItem onClick={handleClose} component={RouterLink} to="/">
                  <DashboardIcon sx={{ mr: 1 }} /> Dashboard
                </MenuItem>
                <MenuItem onClick={handleClose} component={RouterLink} to="/orders">
                  <ShoppingCartIcon sx={{ mr: 1 }} /> Orders
                </MenuItem>
                <MenuItem onClick={handleClose} component={RouterLink} to="/account">
                  <AccountCircleIcon sx={{ mr: 1 }} /> Account
                </MenuItem>
              </Menu>
            </>
          ) : (
            <>
              <Button
                component={RouterLink}
                to="/"
                sx={{
                  color: 'white',
                  backgroundColor: 'primary.light',
                  '&:hover': { backgroundColor: 'primary.main' },
                }}
                startIcon={<DashboardIcon />}
              >
                Dashboard
              </Button>
              <Button
                component={RouterLink}
                to="/orders"
                sx={{ color: 'white', borderColor: 'white', ml: 1 }}
                variant="outlined"
                startIcon={<ShoppingCartIcon />}
              >
                Orders
              </Button>
              <Button
                component={RouterLink}
                to="/account"
                sx={{ color: 'white', borderColor: 'white', ml: 1 }}
                variant="outlined"
                startIcon={<AccountCircleIcon />}
              >
                Account
              </Button>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Container component="main" maxWidth={false} sx={{ mt: { xs: 2, sm: 4 }, mb: 10, flexGrow: 1 }}>
        <Outlet />
      </Container>
      <Footer />
    </Box>
  );
};

export default Layout;
