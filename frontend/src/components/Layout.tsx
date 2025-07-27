import React from 'react';
import { AppBar, Toolbar, Typography, Button, Container, Box, useMediaQuery, IconButton, Menu, MenuItem } from '@mui/material';
import { Link as RouterLink, Outlet } from 'react-router-dom';
import Footer from './Footer';
import MarketHours from './MarketHours';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import HomeIcon from '@mui/icons-material/Home';
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
          
          {/* Market Hours - Desktop Only */}
          {!isMobile && (
            <Box sx={{ mr: 2 }}>
              <MarketHours compact={true} />
            </Box>
          )}
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
                  <HomeIcon sx={{ mr: 1 }} /> Accounts
                </MenuItem>
                <MenuItem onClick={handleClose} component={RouterLink} to="/dashboard">
                  <DashboardIcon sx={{ mr: 1 }} /> Dashboard
                </MenuItem>
                <MenuItem onClick={handleClose} component={RouterLink} to="/research">
                  <SearchIcon sx={{ mr: 1 }} /> Research
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
                startIcon={<HomeIcon />}
              >
                Accounts
              </Button>
              <Button
                component={RouterLink}
                to="/dashboard"
                sx={{ color: 'white', borderColor: 'white', ml: 1 }}
                variant="outlined"
                startIcon={<DashboardIcon />}
              >
                Dashboard
              </Button>
              <Button
                component={RouterLink}
                to="/research"
                sx={{ color: 'white', borderColor: 'white', ml: 1 }}
                variant="outlined"
                startIcon={<SearchIcon />}
              >
                Research
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
      <Container component="main" maxWidth={false} sx={{ mt: { xs: 2, sm: 4 }, pb: 2, flexGrow: 1 }}>
        <Outlet />
      </Container>
      <Box sx={{ 
        position: 'sticky', 
        bottom: 0, 
        width: '100%', 
        zIndex: 1000,
        borderTop: '1px solid',
        borderColor: 'divider',
        backgroundColor: 'background.paper'
      }}>
        <Footer />
      </Box>
    </Box>
  );
};

export default Layout;
