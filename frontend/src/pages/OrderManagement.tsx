import React, { useState, useCallback } from 'react';
import {
  Box, Typography, Tabs, Tab, Grid, Card, CardContent, Fab, Zoom,
  useTheme, useMediaQuery, Backdrop, SpeedDial, SpeedDialAction, SpeedDialIcon
} from '@mui/material';
import {
  Add as AddIcon,
  History as HistoryIcon,
  PlayArrow as ExecuteIcon,
  Bookmark as TemplateIcon,
  Analytics as AnalyticsIcon,
  // Edit as ModifyIcon,
  Schedule as MonitorIcon
} from '@mui/icons-material';

// Import our enhanced components
import CreateOrderForm from '../components/CreateOrderForm';
import OrderHistoryEnhanced from '../components/OrderHistoryEnhanced';
import OrderExecutionMonitor from '../components/OrderExecutionMonitor';
import OrderModification from '../components/OrderModification';
import OrderTemplates from '../components/OrderTemplates';
import BulkOrderOperations from '../components/BulkOrderOperations';

// Import existing components we need
import { useAccountContext } from '../contexts/AccountContext';
import type { Order } from '../types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index} style={{ width: '100%' }}>
      {value === index && <Box sx={{ p: 0 }}>{children}</Box>}
    </div>
  );
};

const OrderManagement: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { selectedAccount } = useAccountContext();
  
  const [tabValue, setTabValue] = useState(0);
  const [showCreateOrder, setShowCreateOrder] = useState(false);
  const [showModifyOrder, setShowModifyOrder] = useState(false);
  const [selectedOrderForModification, setSelectedOrderForModification] = useState<Order | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Handle template usage in order creation
  const handleUseTemplate = useCallback((_template: any) => {
    // We could pre-fill the CreateOrderForm with template data
    // For now, we'll just switch to the create order tab and show a message
    setTabValue(0); // Switch to Create Order tab
    setShowCreateOrder(true);
    
    // In a more sophisticated implementation, we would pass the template data
    // to the CreateOrderForm component to pre-fill the form
  }, []);

  // Handle order modification request
  // const handleModifyOrder = useCallback((order: Order) => {
  //   setSelectedOrderForModification(order);
  //   setShowModifyOrder(true);
  // }, []);

  // Handle order lifecycle events that require refresh
  const handleOrderLifecycleEvent = useCallback(() => {
    setRefreshKey(prev => prev + 1);
    setShowCreateOrder(false);
    setShowModifyOrder(false);
    setSelectedOrderForModification(null);
  }, []);

  const speedDialActions = [
    {
      icon: <AddIcon />,
      name: 'New Order',
      action: () => {
        setTabValue(0);
        setShowCreateOrder(true);
      }
    },
    {
      icon: <TemplateIcon />,
      name: 'Templates',
      action: () => setTabValue(3)
    },
    {
      icon: <MonitorIcon />,
      name: 'Monitor',
      action: () => setTabValue(2)
    },
    {
      icon: <AnalyticsIcon />,
      name: 'Analytics',
      action: () => setTabValue(1)
    }
  ];

  const tabContent = [
    {
      label: 'Create Order',
      icon: <AddIcon />,
      component: (
        <Grid container spacing={3}>
          <Grid item xs={12} lg={8}>
            <CreateOrderForm />
          </Grid>
          <Grid item xs={12} lg={4}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <OrderTemplates onUseTemplate={handleUseTemplate} />
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Quick Tips
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    • Use market orders for immediate execution
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    • Set limit orders to control your entry/exit price
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    • Save frequently used configurations as templates
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    • Monitor your orders in real-time after submission
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          </Grid>
        </Grid>
      )
    },
    {
      label: 'Order History',
      icon: <HistoryIcon />,
      component: <OrderHistoryEnhanced key={refreshKey} />
    },
    {
      label: 'Execution Monitor',
      icon: <MonitorIcon />,
      component: (
        <Grid container spacing={3}>
          <Grid item xs={12} lg={8}>
            <OrderExecutionMonitor key={refreshKey} />
          </Grid>
          <Grid item xs={12} lg={4}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Execution Metrics
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Monitor your orders in real-time with:
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    • Price progress indicators
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    • Execution probability analysis
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    • Time-to-fill estimates
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    • Real-time market price comparison
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          </Grid>
        </Grid>
      )
    },
    {
      label: 'Templates',
      icon: <TemplateIcon />,
      component: (
        <Grid container spacing={3}>
          <Grid item xs={12} lg={8}>
            <OrderTemplates onUseTemplate={handleUseTemplate} />
          </Grid>
          <Grid item xs={12} lg={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Template Benefits
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Save time by creating reusable order configurations:
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  • Standard position sizes
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  • Common price levels
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  • Frequent order types
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • Risk management settings
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )
    },
    {
      label: 'Bulk Operations',
      icon: <ExecuteIcon />,
      component: (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <BulkOrderOperations key={refreshKey} onOrdersModified={handleOrderLifecycleEvent} />
          </Grid>
        </Grid>
      )
    }
  ];

  if (!selectedAccount) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Order Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Please select an account to manage orders.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* Header */}
      <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Typography variant="h4" gutterBottom>
          Order Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Account: {selectedAccount.owner} ({selectedAccount.id})
        </Typography>
      </Box>

      {/* Navigation Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Tabs 
          value={tabValue} 
          onChange={(_, newValue) => setTabValue(newValue)}
          variant={isMobile ? 'scrollable' : 'standard'}
          scrollButtons="auto"
        >
          {tabContent.map((tab, index) => (
            <Tab
              key={index}
              label={tab.label}
              icon={tab.icon}
              iconPosition="start"
              sx={{ minWidth: isMobile ? 'auto' : 120 }}
            />
          ))}
        </Tabs>
      </Box>

      {/* Tab Content */}
      <Box sx={{ p: 3 }}>
        {tabContent.map((tab, index) => (
          <TabPanel key={index} value={tabValue} index={index}>
            {tab.component}
          </TabPanel>
        ))}
      </Box>

      {/* Mobile Speed Dial */}
      {isMobile && (
        <SpeedDial
          ariaLabel="Order actions"
          sx={{ position: 'fixed', bottom: 16, right: 16 }}
          icon={<SpeedDialIcon />}
        >
          {speedDialActions.map((action) => (
            <SpeedDialAction
              key={action.name}
              icon={action.icon}
              tooltipTitle={action.name}
              onClick={action.action}
            />
          ))}
        </SpeedDial>
      )}

      {/* Desktop Floating Action Buttons */}
      {!isMobile && (
        <Box sx={{ position: 'fixed', bottom: 16, right: 16, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Zoom in={tabValue !== 0}>
            <Fab
              color="primary"
              aria-label="create order"
              onClick={() => {
                setTabValue(0);
                setShowCreateOrder(true);
              }}
            >
              <AddIcon />
            </Fab>
          </Zoom>
          <Zoom in={tabValue !== 2}>
            <Fab
              color="secondary"
              aria-label="monitor orders"
              onClick={() => setTabValue(2)}
              size="medium"
            >
              <MonitorIcon />
            </Fab>
          </Zoom>
        </Box>
      )}

      {/* Order Modification Dialog */}
      <OrderModification
        order={selectedOrderForModification}
        open={showModifyOrder}
        onClose={() => setShowModifyOrder(false)}
        onOrderModified={handleOrderLifecycleEvent}
      />

      {/* Create Order Backdrop (for better mobile UX) */}
      <Backdrop
        sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
        open={showCreateOrder && isMobile}
        onClick={() => setShowCreateOrder(false)}
      />
    </Box>
  );
};

export default OrderManagement;